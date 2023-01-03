"""Layer on top of asyncio to handle command piping.

This module defines PipeWriter and PipeReader interfaces, meant to unify
asynchronous access to streams used in command piping in Jean-Shell.
"""
from asyncio import gather
from io import BytesIO
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from aiofile import BinaryFileWrapper, async_open


@runtime_checkable
class PipeWriter(Protocol):
    """A stream writer, used in command pipes."""

    async def write(self, data: bytes) -> None:
        """Write given bytes to the underlying stream.

        :param data: Data to write.
        """

    async def close(self) -> None:
        """Closes the underlying stream."""


class MemoryPipeWriter:
    """A pipe writer writing to memory.

    When closing, content written to the stream will be available via the
    `value` property . Used to collect stdout and stderr of commands for further
    processing.
    """

    def __init__(self) -> None:
        self._stream = BytesIO()
        self._bytes: bytes | None = None

    @property
    def value(self) -> bytes:
        """Get the data that was written to this PipeWriter once it's closed."""
        assert self._bytes is not None
        return self._bytes

    async def write(self, data: bytes) -> None:
        """Write given bytes to the underlying memory stream.

        :param data: Bytes to write.
        """
        self._stream.write(data)

    async def close(self) -> None:
        """Saves the underlying BytesIO buffer, then closes it."""
        if not self._stream.closed:
            self._bytes = self._stream.getvalue()
            self._stream.close()


class CompoundPipeWriter:
    """A pipe writer forwarding data to a list of child writers.

    Used by commands to forward stdout to multiple processes and files.
    """

    def __init__(self, *children: PipeWriter) -> None:
        self._children: set[PipeWriter] = set(children)

    async def write(self, data: bytes) -> None:
        """Write given bytes to the underlying memory stream.

        :param data: Bytes to write.
        """
        await gather(*[child.write(data) for child in self._children])

    async def close(self) -> None:
        """Saves the underlying BytesIO buffer, then closes it."""
        await gather(*[child.close() for child in self._children])


class FilePipeWriter:
    def __init__(self, wrapper: BinaryFileWrapper):
        self._wrapper = wrapper

    @staticmethod
    async def open(path: Path) -> "FilePipeWriter":
        wrapper = cast(BinaryFileWrapper, await async_open(path, "wb"))
        return FilePipeWriter(wrapper)

    async def write(self, data: bytes) -> None:
        """Writes bytes to the underlying file."""
        await self._wrapper.write(data)

    async def close(self) -> None:
        """Close the underlying file."""
        await self._wrapper.close()
