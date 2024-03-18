"""Base types used to batch-copy files.

This module only defines types that can be used to describe a list of file and
directories, their permissions and their content to synchronize them to various
destination.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncContextManager

from jtoto.stream import InputStream


@dataclass(frozen=True)
class SourceFile:
    """Item of a manifest representing a file with a source."""

    path: str
    user: str | None = None
    group: str | None = None
    mode: str | None = None


@dataclass(frozen=True)
class SourceDirectory:
    path: str | None = None
    user: str | None = None
    group: str | None = None
    file_mode: str | None = None
    directory_mode: str | None = None
    clean: bool = False


@dataclass(frozen=True)
class File(ABC):
    """Item of a manifest representing a file with binary content."""

    user: str | None = None
    group: str | None = None
    mode: str | None = None

    @abstractmethod
    def open(self) -> AsyncContextManager[InputStream]:
        """Source path of this file."""


@dataclass(frozen=True)
class Directory:
    """Item of a manifest representing a directory with binary content."""

    user: str | None = None
    group: str | None = None
    mode: str | None = None
    clean: bool = False
