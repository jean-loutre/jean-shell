from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType

from jshell.core.pipe import echo
from jshell.core.shell import Shell, ShellPipe


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
