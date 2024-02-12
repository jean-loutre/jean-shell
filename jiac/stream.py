from abc import ABC, abstractmethod
from typing import Iterable
from asyncio import gather
from logging import Logger, DEBUG
from typing import Self
from types import TracebackType


class Stream(ABC):
    @abstractmethod
    async def write(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

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
    @abstractmethod
    async def read(self, n: int = -1) -> bytes:
        ...


class NullStream:
    async def write(self, _: bytes) -> None:
        ...

    async def close(self) -> None:
        ...


class MemoryStream:
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
                  simply be ignored. If all given children are None, None is
                  returned. Things are made this way to work nicely with stdout
                  and stderr streams of shell commands that can be set to None
                  to be disabled.

    Return:
        A stream forwarding writes to all agregatted streams.
    """
    children = set(_unfold_multiplex_streams(*streams))
    if not children:
        return None

    return _MultiplexStream(*children)
