from abc import ABC, abstractmethod
from base64 import b64decode
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Mapping, Type, TypeVar, cast

from yaml import Loader, MappingNode, Node, ScalarNode, SequenceNode, compose

from jshell.core.pipe import cat, echo
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

    @property
    def is_scalar(self) -> bool:
        return isinstance(self._yaml_node, ScalarNode)

    def items(self) -> Iterable[tuple["ManifestNode", "ManifestNode"]]:
        self.check_node_type(MappingNode)
        for key_node, value_node in self._yaml_node.value:
            yield (ManifestNode(key_node), ManifestNode(value_node))

    def iter(self) -> Iterable["ManifestNode"]:
        self.check_node_type(SequenceNode)
        for node in self._yaml_node.value:
            yield ManifestNode(node)

    def get(self, key: str) -> "ManifestNode | None":
        self.check_node_type(MappingNode)
        for key_node, value_node in self._yaml_node.value:
            if ManifestNode(key_node).as_scalar() == key:
                return ManifestNode(value_node)

        return None

    def as_scalar(self) -> str:
        self.check_node_type(ScalarNode)
        return cast(str, self._yaml_node.value)

    def get_scalar(self, key: str) -> str | None:
        node = self.get(key)
        if node:
            return node.as_scalar()

        return None

    def check_node_type(self, *node_types: Type[TNode]) -> None:
        if not isinstance(self._yaml_node, tuple(node_types)):
            node_type_names = [
                {
                    MappingNode: "mapping",
                    ScalarNode: "scalar",
                    SequenceNode: "sequence",
                }[it]
                for it in node_types
            ]
            raise ManifestException(
                f"Expected one of {' '.join(node_type_names)} node."
            )


ContentHandler = Callable[[Path, ManifestNode], Awaitable[None]]


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

    async def sync_manifest(
        self, manifest: str, content_handlers: dict[str, ContentHandler] | None = None
    ) -> None:
        async def _sync_file(path: Path, node: ManifestNode) -> None:
            source_path = node.as_scalar()
            await (cat(source_path) | self.write_file(path))

        async def _sync_content(path: Path, node: ManifestNode) -> None:
            content = node.as_scalar()
            await (echo(content) | self.write_file(path))

        async def _base64_source(path: Path, node: ManifestNode) -> None:
            content = b64decode(node.as_scalar())
            await (echo(content) | self.write_file(path))

        extended_content_handlers = content_handlers or {}

        async def _sync_dir(path: Path, node: ManifestNode) -> None:
            await self.make_directory(path)
            await self._sync_files(node, path, extended_content_handlers)

        extended_content_handlers = extended_content_handlers | {
            "tag:yaml.org,2002:str": _sync_content,
            "!base64": _base64_source,
            "!file": _sync_file,
            "!dir": _sync_dir,
        }

        root_node = ManifestNode(compose(manifest, Loader=Loader))

        files_node = root_node.get("files")
        if files_node is not None:
            await self._sync_files(files_node, Path("/"), extended_content_handlers)

    async def _sync_files(
        self,
        files_node: ManifestNode,
        root_path: Path,
        content_handlers: Mapping[str, ContentHandler],
    ) -> None:
        for path_node, file_manifest in files_node.items():
            path_node.check_node_type(ScalarNode, SequenceNode)
            if path_node.is_scalar:
                paths = [path_node.as_scalar()]
            else:
                paths = [it.as_scalar() for it in path_node.iter()]

            for path in paths:
                expanded_path = root_path / path
                content = file_manifest.get("content")
                if content:
                    await content_handlers[content.tag](expanded_path, content)

                user = file_manifest.get_scalar("user")
                group = file_manifest.get_scalar("group")
                mode = file_manifest.get_scalar("mode")
                if user or group or mode:
                    await self.set_permissions(
                        expanded_path, user=user, group=group, mode=mode
                    )
