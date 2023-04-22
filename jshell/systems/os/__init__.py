from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Iterable, Type, TypeVar, cast

from yaml import Loader, MappingNode, Node, ScalarNode, compose

from jshell.core.pipe import echo
from jshell.core.shell import Shell, ShellPipe

TNode = TypeVar("TNode", bound=Node)


class ManifestException(Exception):
    pass


def _check_node_type(node: Node, node_type: Type[TNode]) -> TNode:
    if not isinstance(node, node_type):
        node_type_name = {MappingNode: "mapping", ScalarNode: "scalar"}[type]
        raise ManifestException(f"Expected a {node_type_name} node.")
    return node


def _yaml_get(
    mapping: MappingNode, key: str, expected_type: Type[TNode]
) -> TNode | None:
    for key_node, value_node in mapping.value:
        key_node = _check_node_type(key_node, ScalarNode)
        if key_node.value == key:
            return _check_node_type(value_node, expected_type)

    return None


def _yaml_get_scalar(mapping: MappingNode, key: str) -> str | None:
    scalar_node = _yaml_get(mapping, key, ScalarNode)
    if scalar_node:
        return cast(str, scalar_node.value)

    return None


def _yaml_items(
    node: MappingNode, expected_value_type: Type[TNode]
) -> Iterable[tuple[str, TNode]]:
    for key_node, value_node in node.value:
        yield (
            _check_node_type(key_node, ScalarNode).value,
            _check_node_type(value_node, expected_value_type),
        )


class Os(ABC):
    """Abstraction over os-specific operations."""

    def __init__(self, sh: Shell) -> None:
        self._sh = sh

    def sync(self) -> "SyncBatch":
        """Start a batch to synchronize files.

        Limits the number of commands needed to send the files,
        by aggregating directory creation.
        """
        return SyncBatch(self)

    @abstractmethod
    def make_directory(self, path: str | Path) -> ShellPipe:
        """Create a directory."""

    @abstractmethod
    def write_file(self, path: str | Path) -> ShellPipe:
        """Write a file."""

    @abstractmethod
    async def set_permissions(
        self,
        path: str,
        user: str | None = None,
        group: str | None = None,
        mode: str | None = None,
    ) -> None:
        """Change a file or directory owner, group and permissions."""

    async def sync_manifest(self, manifest: str) -> None:
        root_node = compose(manifest, Loader=Loader)
        _check_node_type(root_node, MappingNode)

        files_node = _yaml_get(root_node, "files", MappingNode)
        if files_node is not None:
            await self._sync_files(files_node)

    async def _sync_files(self, files_node: MappingNode) -> None:
        for path, file_manifest in _yaml_items(files_node, MappingNode):
            user = _yaml_get_scalar(file_manifest, "user")
            group = _yaml_get_scalar(file_manifest, "group")
            mode = _yaml_get_scalar(file_manifest, "mode")
            if user or group or mode:
                await self.set_permissions(path, user=user, group=group, mode=mode)


class _PendingFile:
    def __init__(self, path: Path, content: bytes) -> None:
        self._path = path
        self._content = content

    @property
    def path(self) -> Path:
        return self._path

    @property
    def directory(self) -> Path:
        return self._path.parent

    @property
    def content(self) -> bytes:
        return self._content


class SyncBatch:
    """Batch synchronizing files to a remote host"""

    def __init__(self, os: Os) -> None:
        self._os = os
        self._pending_files: list[_PendingFile] = []

    def add(self, destination: str | Path, content: bytes | str) -> None:
        destination = Path(destination)
        if isinstance(content, str):
            content = content.encode("utf-8")
        pending_file = _PendingFile(destination, content)
        self._pending_files.append(pending_file)

    async def __aenter__(self) -> "SyncBatch":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        directories_to_create: set[Path] = set()
        for file in self._pending_files:
            target_directory = file.directory
            # Remove directories that are a parent of target directory,
            # as they will be created when creating the child one
            duplicated_parent = next(
                (it for it in directories_to_create if it in target_directory.parents),
                None,
            )
            if duplicated_parent is not None:
                directories_to_create.remove(duplicated_parent)

            child = next(
                (it for it in directories_to_create if target_directory in it.parents),
                None,
            )
            if child is None:
                directories_to_create.add(target_directory)

        for directory in directories_to_create:
            await self._os.make_directory(directory)

        for file in self._pending_files:
            await (echo(file.content) | self._os.write_file(file.path))
