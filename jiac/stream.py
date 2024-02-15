"""Abstract output and input stream interfaces and common implementations.

Declares classes Stream, an output stream with async write and close methods,
and InputStream with a single read method. These interface are used by the
shell and common system to handle stdin, stderr and stdout, piping between
commands, to a file, to a logging.Logger...
"""
from abc import ABC, abstractmethod
from typing import Iterable
from asyncio import gather, Event
from logging import Logger, DEBUG
from typing import Self, IO
from types import TracebackType


class Stream(ABC):
    """Interface for writable streams.

    Object of this class can be used as a async context manager. When the
    manager exits, the close method will be automatically called.

    """

    @abstractmethod
    async def write(self, data: bytes) -> None:
        """Write given bytes to the stream.

        Args:
            data: Data to write to the stream.
        """

    @abstractmethod
    async def close(self) -> None:
        """Close the stream."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()


class InputStream(ABC):
    """Interface for readable streams."""

    @abstractmethod
    async def read(self, n: int = -1) -> bytes:
        """Read bytes from the stream.

        Implementers should block until the given n bytes are available, or
        until the stream is closed.

        Args:
            n: Number of bytes to read. If -1 is given, read all data to the
            stream's end.
        """


class NullStream(Stream):
    """No-op stream.

    This class can be used where a stream is expected, but nothing has to be
    done with it.
    """

    async def write(self, _: bytes) -> None:
        ...

    async def close(self) -> None:
        ...


class MemoryStream(Stream):
    """Stream implementation writing to a bytarray"""

    def __init__(self, buffer: bytearray | None = None) -> None:
        """Initialize the memory stream.

        Args:
            buffer: The bytarray to write to. If none, a new bytearray will be
                    created.
        """
        self._buffer = buffer if buffer is not None else bytearray()

    @property
    def buffer(self) -> bytearray:
        return self._buffer

    async def write(self, data: bytes) -> None:
        self._buffer.extend(data)

    async def close(self) -> None:
        ...


class LineStream(Stream):
    """Stream writing lines at a time."""

    def __init__(self) -> None:
        self._pending_line = ""

    async def write(self, data: bytes) -> None:
        string_content = self._pending_line + data.decode("utf-8", errors="ignore")
        self._pending_line = ""
        lines = string_content.split("\n")

        if string_content[-1] != "\n":
            self._pending_line = lines.pop()

        if len(lines) > 1 and lines[-1] == "":
            lines.pop()

        for line in lines:
            self.write_line(line)

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Method called each time a full line is written to stream.

        Args:
            line: The line to write.
        """

    async def close(self) -> None:
        if self._pending_line:
            self.write_line(self._pending_line)


class LogStream(LineStream):
    """Stream sending each received line to a python Logger.

    Uses the standard python logging facility, from module "logging".
    """

    def __init__(self, logger: Logger, level: int = DEBUG) -> None:
        """Initialize the log stream.

        Args:
            logger: The logging.Logger to use to log messages.
            level: The logging level to use for each sent log message.
        """
        super().__init__()
        self._logger = logger
        self._level = level

    def write_line(self, line: str) -> None:
        self._logger.log(self._level, line)


class _MultiplexStream(Stream):
    def __init__(self, *children: Stream) -> None:
        self._children = set(children)

    async def write(self, data: bytes) -> None:
        await gather(*[child.write(data) for child in self._children])

    async def close(self) -> None:
        await gather(*[child.close() for child in self._children])


def _unfold_multiplex_streams(*streams: Stream | None) -> Iterable[Stream]:
    for stream in streams:
        if stream is None:
            continue
        if isinstance(stream, _MultiplexStream):
            yield from _unfold_multiplex_streams(*stream._children)
        else:
            yield stream


def multiplex(*streams: Stream | None) -> Stream | None:
    """Aggregate multiple streams into a single one.

    Return a stream that, when wrote, will write to all streams given to the
    function. Writes to children streams are done in parallel, expect no order.
    If the given list of streams contains a multiplexed stream, it will be
    unfolded : it's children will be added to the returned stream as direct
    children.

    When the multiplexed stream is closed, it will close all it's children, in
    parallel.

    Args:
        *streams: Streams to aggregate, or None. If an element is None, it will
            simply be ignored.

            If all given children are None, None is returned. Things are made
            this way to work nicely with stdout and stderr streams of shell
            commands that can be set to None to be disabled.

            If the same stream is passed multiple times, it will be anyway
            called only once when writing / closing the multiplex stream

    Return:
        A stream forwarding writes to all agregatted streams.
    """
    children = set(_unfold_multiplex_streams(*streams))
    if not children:
        return None

    return _MultiplexStream(*children)


class _PipeStreamBase:
    def __init__(self, buffer: bytearray, data_available: Event, closed: Event) -> None:
        self._buffer = buffer
        self._data_available = data_available
        self._data_available.clear()
        self._closed = closed


class _PipeStream(_PipeStreamBase, Stream):
    async def write(self, data: bytes) -> None:
        self._buffer.extend(data)
        self._data_available.set()

    async def close(self) -> None:
        self._closed.set()
        self._data_available.set()


class _PipeInputStream(_PipeStreamBase, InputStream):
    async def read(self, n: int = -1) -> bytes:
        if n == -1:
            await self._closed.wait()
            data = self._buffer
            self._buffer = bytearray()
        else:
            while len(self._buffer) < n:
                await self._data_available.wait()
                if self._closed.is_set():
                    break
                self._data_available.clear()
            read_size = min(n, len(self._buffer))
            data = self._buffer[0:read_size]
            self._buffer = self._buffer[n:]

        if len(self._buffer) == 0:
            self._data_available.clear()

        return data


def pipe() -> tuple[Stream, InputStream]:
    """Create a pipe between two streams.

    Return:
        A tuple (in, out), such as data written to "in" is readable from "out".
    """
    buffer = bytearray()
    data_available = Event()
    closed = Event()
    return _PipeStream(buffer, data_available, closed), _PipeInputStream(
        buffer, data_available, closed
    )


Streamable = bytearray | Stream | None


def stream_to(streamable: Streamable) -> Stream:
    """Wraps an object in a stream.

    Return a stream that wraps various python types:
      * If streamable is None, return None
      * If streamable is already a Stream, return it
      * If streamable is a bytearray, return a MemoryStream that writes into the given bytearray

    Args:
        streamable : The object to convert to a stream.

    Returns:
        A stream that encapsulates the given streamable.
    """
    if streamable is None:
        return NullStream()
    if isinstance(streamable, Stream):
        return streamable
    if isinstance(streamable, bytearray):
        return MemoryStream(streamable)

    raise NotImplementedError()


async def copy_stream(in_: InputStream, out: Stream, buffer_size: int = 1024) -> None:
    """Copy a stream to another.

    Args:
        in_ : Input stream
        out: Output stream
        buffer_size: size of chunks used when reading from source and writing
                     to destination.
    """
    while True:
        buffer = await in_.read(buffer_size)
        await out.write(buffer)
        if len(buffer) < buffer_size:
            return


class FileInputStream(InputStream):
    def __init__(self, file: IO[bytes]) -> None:
        self._file = file

    async def read(self, n: int = -1) -> bytes:
        return self._file.read(n)
