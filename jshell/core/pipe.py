"""Layer on top of asyncio to handle pipe piping.

This module defines PipeWriter and PipeReader interfaces, meant to unify
asynchronous access to streams used in pipe piping in Jean-Shell.
"""
from asyncio import gather
from io import BytesIO
from logging import Logger
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Generator,
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

from aiofile import BinaryFileWrapper, async_open


@runtime_checkable
class PipeWriter(Protocol):
    """A stream writer, used in pipe pipes."""

    async def write(self, data: bytes) -> None:
        """Write given bytes to the underlying stream.

        :param data: Data to write.
        """

    async def close(self) -> None:
        """Closes the underlying stream."""


class MemoryPipeWriter:
    """A pipe writer writing to memory.

    When closing, content written to the stream will be available via the
    `value` property . Used to collect stdout and stderr of pipes for further
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

    Used by pipes to forward stdout to multiple processes and files.
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


class LogPipeWriter:
    def __init__(self, log: Logger) -> None:
        self._log = log
        self._pending_line = ""

    async def write(self, data: bytes) -> None:
        string_content = self._pending_line + data.decode("utf-8")
        self._pending_line = ""
        lines = string_content.split("\n")

        if string_content[-1] != "\n":
            self._pending_line = lines.pop()

        if len(lines) > 1 and lines[-1] == "":
            lines.pop()

        for line in lines:
            self._log.info(line)

    async def close(self) -> None:
        pass


# Here starts the generic mayem

In = TypeVar("In")
Out = TypeVar("Out")

Wait = Callable[[In], Awaitable[Out]]
Process = tuple[PipeWriter, Wait[In, Out]]
ProcessFactory = Callable[[PipeWriter], Awaitable[Process[In, Out]]]


class _NullPipeWriter:
    async def write(self, data: bytes) -> None:
        pass

    async def close(self) -> None:
        pass


class PipeStart:
    pass


PIPE_START = PipeStart()

T = TypeVar("T")


class Pipe(Generic[In, Out]):
    def __init__(
        self, previous: "Pipe[In, T] | None", start: ProcessFactory[T, Out]
    ) -> None:
        self._previous = previous
        self._start = start

    def __await__(self: "Pipe[PipeStart, T]") -> Generator[None, None, T]:
        return self.run(_NullPipeWriter()).__await__()

    def __or__(
        self, right: "Pipe[Out, T] | Pipe[Out | PipeStart, T | PipeStart]"
    ) -> "Pipe[In, T]":
        # Due to the dropping of PipeStart from the right pipe input and output
        # types, the code is correct only if any pipe receiving anything else
        # than PIPE_START as input must not return PIPE_START as output.
        start_stack: list[Any] = []
        previous: Any = right
        while previous is not None:
            start_stack.append(right._start)
            previous = previous._previous

        new_pipe = self
        for start in reversed(start_stack):
            new_pipe = Pipe(self, start)

        return cast(Pipe[In, T], new_pipe)

    async def run(self: "Pipe[PipeStart, Out]", stdout: PipeWriter) -> Out:
        stdin, wait = await self._start(stdout)
        previous = self._previous
        if previous is None:
            # As self type is constrained so that only pipes that can accept
            # PIPE_START as input can be awaited, having previous == None
            # here means that self is the first of the pipe chain thus, accepts
            # PipeStart as input.
            result = await wait(PIPE_START)  # type: ignore
        else:
            previous_result = await previous.run(stdin)
            result = await wait(previous_result)
        return result


P = ParamSpec("P")
R = TypeVar("R")


def pipe(
    func: Callable[Concatenate[PipeWriter, P], Awaitable[Process[In, Out]]]
) -> Callable[P, Pipe[In, Out]]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> Pipe[In, Out]:
        async def start(stdout: PipeWriter) -> Process[In, Out]:
            return await func(stdout, *args, **kwargs)

        return Pipe(None, start)

    return inner
