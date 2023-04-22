from abc import ABC, abstractmethod
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Mapping, Type, TypeVar, cast

from yaml import Loader, MappingNode, Node, ScalarNode, compose

from jshell.core.pipe import cat
from jshell.core.shell import Shell, ShellPipe

TNode = TypeVar("TNode", bound=Node)


class ManifestException(Exception):
    pass


class ManifestNode:
    def __init__(self, yaml_node: Node) -> None:
        self._yaml_node = yaml_node

    @property
    def tag(self) -> str:
        return self._yaml_node.tag

    def items(self) -> Iterable[tuple[str, "ManifestNode"]]:
        self._check_node_type(MappingNode)
        for key_node, value_node in self._yaml_node.value:
            yield (ManifestNode(key_node).as_scalar(), ManifestNode(value_node))

    def get(self, key: str) -> "ManifestNode | None":
        self._check_node_type(MappingNode)
        for key_node, value_node in self._yaml_node.value:
            if ManifestNode(key_node).as_scalar() == key:
                return ManifestNode(value_node)

        return None

    def as_scalar(self) -> str:
        self._check_node_type(ScalarNode)
        return cast(str, self._yaml_node.value)

    def get_scalar(self, key: str) -> str | None:
        node = self.get(key)
        if node:
            return node.as_scalar()

        return None

    def _check_node_type(self, node_type: Type[TNode]) -> None:
        if not isinstance(self._yaml_node, node_type):
            node_type_name = {MappingNode: "mapping", ScalarNode: "scalar"}[type]
            raise ManifestException(f"Expected a {node_type_name} node.")


SourceHandler = Callable[[Path, ManifestNode], Awaitable[None]]


class Os(ABC):
    """Abstraction over os-specific operations."""

    def __init__(self, sh: Shell) -> None:
        self._sh = sh

    @abstractmethod
    def make_directory(self, path: str | Path) -> ShellPipe:
        """Create a directory."""

    @abstractmethod
    def write_file(self, path: str | Path) -> ShellPipe:
        """Write a file."""

    @abstractmethod
    async def set_permissions(
        self,
        path: str | Path,
        user: str | None = None,
        group: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Change a file or directory owner, group and permissions."""

    async def sync_manifest(self, manifest: str) -> None:
        async def _sync_file(path: Path, node: ManifestNode) -> None:
            source = node.as_scalar()
            await (cat(source) | self.write_file(path))

        source_handlers: dict[str, SourceHandler] = {}

        async def _sync_dir(path: Path, node: ManifestNode) -> None:
            await self.make_directory(path)
            await self._sync_files(node, path, source_handlers)

        source_handlers = source_handlers | {
            "tag:yaml.org,2002:str": _sync_file,
            "!dir": _sync_dir,
        }

        root_node = ManifestNode(compose(manifest, Loader=Loader))

        files_node = root_node.get("files")
        if files_node is not None:
            await self._sync_files(files_node, Path("/"), source_handlers)

    async def _sync_files(
        self,
        files_node: ManifestNode,
        root_path: Path,
        source_handlers: Mapping[str, SourceHandler],
    ) -> None:
        for path, file_manifest in files_node.items():
            expanded_path = root_path / path
            source = file_manifest.get("source")
            if source:
                source_tag = source.tag
                await source_handlers[source_tag](expanded_path, source)

            user = file_manifest.get_scalar("user")
            group = file_manifest.get_scalar("group")
            mode = file_manifest.get_scalar("mode")
            if user or group or mode:
                await self.set_permissions(
                    expanded_path, user=user, group=group, mode=mode
                )
