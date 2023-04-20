"""Layer on top of asyncio to handle pipe piping.

This module defines PipeWriter and PipeReader interfaces, meant to unify
asynchronous access to streams used in pipe piping in Jean-Shell.
"""
from abc import ABC, abstractmethod
from asyncio import create_task, gather
from collections import deque
from io import BufferedIOBase, BytesIO, RawIOBase
from itertools import chain
from json import dumps, loads
from logging import Logger, getLogger
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Final,
    Generator,
    Generic,
    Iterable,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

from aiofile import BinaryFileWrapper, async_open
from yaml import Dumper, Loader
from yaml import dump as yaml_dump
from yaml import load as yaml_load


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
    `value` property . Used to collect out and err of pipes for further
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


class CombinedPipeWriter:
    """A pipe writer forwarding data to a list of child writers."""

    def __init__(self, *children: PipeWriter) -> None:
        self._children: set[PipeWriter] = set(children)

    @property
    def children(self) -> Iterable[PipeWriter]:
        return self._children

    async def write(self, data: bytes) -> None:
        """Write given bytes to the underlying memory stream.

        :param data: Bytes to write.
        """
        await gather(*[child.write(data) for child in self.children])

    async def close(self) -> None:
        """Saves the underlying BytesIO buffer, then closes it."""
        await gather(*[child.close() for child in self.children])


def combine_pipes(first: PipeWriter, second: PipeWriter) -> PipeWriter:
    """Merge two pipe writers."""

    if isinstance(first, _NullPipeWriter):
        return second
    if isinstance(second, _NullPipeWriter):
        return first

    children: set[PipeWriter] = set()

    if isinstance(first, CombinedPipeWriter) and isinstance(second, CombinedPipeWriter):
        children = set(chain.from_iterable([first.children, second.children]))
    elif isinstance(first, CombinedPipeWriter):
        children = set(first.children)
        children.add(second)
    elif isinstance(second, CombinedPipeWriter):
        children = set(second.children)
        children.add(first)
    else:
        children = set([first, second])

    return CombinedPipeWriter(*children)


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


# Here starts the generic mayem

In = TypeVar("In")
Out = TypeVar("Out", contravariant=True)
Next = TypeVar("Next")

Wait = Callable[[In], Awaitable[Out]]
Process = tuple[PipeWriter, PipeWriter, Wait[In, Out]]
ProcessFactory = Callable[[PipeWriter, PipeWriter], Awaitable[Process[In, Out]]]


class _NullPipeWriter:
    async def write(self, data: bytes) -> None:
        pass

    async def close(self) -> None:
        pass


class PipeStart:
    pass


PIPE_START = PipeStart()

T = TypeVar("T")
U = TypeVar("U")


class Pipe(Generic[In, Out]):
    def __init__(
        self,
        previous: "Pipe[In, Any] | None",
        start: ProcessFactory[Any, Out],
        logger: Logger | None = None,
    ) -> None:
        self._previous = previous
        self._start = start
        self._logger = logger

    def __await__(self: "Pipe[PipeStart, Out]") -> Generator[None, None, Out]:
        logger: Logger | None = self._logger
        previous = self._previous
        while logger is None and previous is not None:
            logger = previous._logger
            previous = previous._previous

        if logger is None:
            out: PipeWriter = _NullPipeWriter()
            err: PipeWriter = _NullPipeWriter()
        else:
            out = _LogPipeWriter(logger.getChild("stdout"))
            err = _LogPipeWriter(logger.getChild("stderr"))

        return self.run(out, err).__await__()

    def __or__(self, right: "Pipable[Out, Next]") -> "Pipe[In, Next]":
        # Due to the dropping of PipeStart from the right pipe input and output
        # types, the code is correct only if any pipe receiving anything else
        # than PIPE_START as input must not return PIPE_START as output.
        if isinstance(right, Pipe):
            if right._previous is None:
                return Pipe(self, right._start, logger=right._logger)

            return Pipe(self | right._previous, right._start, logger=right._logger)

        async def _wait(result: Out) -> Next:
            assert not isinstance(right, Pipe)
            return await right(result)

        async def _start(out: PipeWriter, err: PipeWriter) -> Process[Out, Next]:
            return out, err, _wait

        return Pipe(self, _start)

    async def run(
        self: "Pipe[PipeStart, Out]", out: PipeWriter, err: PipeWriter
    ) -> Out:
        stdin, err, wait = await self._start(out, err)

        previous = self._previous
        if previous is None:
            # As self type is constrained so that only pipes that can accept
            # PIPE_START as input can be awaited, having previous == None
            # here means that self is the first of the pipe chain thus, accepts
            # PipeStart as input.
            result = await wait(PIPE_START)
        else:
            previous_result = await previous.run(stdin, err)
            result = await wait(previous_result)
        return result


Pipable = Pipe[Out, Next] | Callable[[Out], Awaitable[Next]]

P = ParamSpec("P")


def pipe(
    func: Callable[Concatenate[PipeWriter, PipeWriter, P], Awaitable[Process[In, Next]]]
) -> Callable[P, Pipe[In, Next]]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> Pipe[In, Next]:
        async def start(out: PipeWriter, err: PipeWriter) -> Process[In, Next]:
            return await func(out, err, *args, **kwargs)

        return Pipe(None, start)

    return inner


async def forward_result(result: T | PipeStart) -> T | PipeStart:
    return result


class _ConcatenatePipeWriter:
    def __init__(self, start: RawIOBase | BufferedIOBase, out: PipeWriter) -> None:
        self._write_start_task = create_task(self._write_start(start))
        self._out = out

    async def write(self, data: bytes) -> None:
        await self._write_start_task
        await self._out.write(data)

    async def close(self) -> None:
        await self._write_start_task
        await self._out.close()

    async def _write_start(self, start: RawIOBase | BufferedIOBase) -> None:
        buffer = bytearray(1024)
        n = start.readinto(buffer)

        while n != 0:
            await self._out.write(buffer[0:n])
            n = start.readinto(buffer)

        start.close()


def _concatenate(
    start: RawIOBase | BufferedIOBase, out: PipeWriter, err: PipeWriter
) -> Process[T | PipeStart, T | PipeStart]:
    writer = _ConcatenatePipeWriter(start, out)

    async def _wait(result: T | PipeStart) -> T | PipeStart:
        await writer.close()
        return result

    return writer, err, _wait


@pipe
async def cat(
    out: PipeWriter, err: PipeWriter, source: Path | str
) -> Process[T | PipeStart, T | PipeStart]:
    if isinstance(source, str):
        source = Path(source)
    return _concatenate(open(source, "rb"), out, err)


@pipe
async def echo(
    out: PipeWriter,
    err: PipeWriter,
    content: bytes | str,
    encoding: str = "utf-8",
) -> Process[T | PipeStart, T | PipeStart]:
    if isinstance(content, str):
        byte_content = content.encode(encoding)
    else:
        byte_content = content

    return _concatenate(BytesIO(byte_content), out, err)


class LinePipeWriter(ABC):
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
        pass

    async def close(self) -> None:
        if self._pending_line:
            self.write_line(self._pending_line)


class _LogPipeWriter(LinePipeWriter):
    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._logger = logger

    def write_line(self, line: str) -> None:
        self._logger.info(line)


class TailPipeWriter(LinePipeWriter):
    def __init__(self) -> None:
        super().__init__()
        self._tail: deque[str] = deque(maxlen=10)

    @property
    def tail(self) -> Iterable[str]:
        return self._tail

    def write_line(self, line: str) -> None:
        self._tail.append(line)


@pipe
async def log(
    out: PipeWriter,
    err: PipeWriter,
    logger: Logger | str,
    stdout: bool = True,  # pylint: disable=redefined-outer-name
    stderr: bool = True,  # pylint: disable=redefined-outer-name
) -> Process[T | PipeStart, T | PipeStart]:
    if isinstance(logger, str):
        logger = getLogger(logger)

    if stdout:
        out = combine_pipes(_LogPipeWriter(logger), out)
    if stderr:
        err = combine_pipes(_LogPipeWriter(logger), err)
    return out, err, forward_result


class Redirect:
    pass


STDOUT: Final[Redirect] = Redirect()
STDERR: Final[Redirect] = Redirect()
NULL: Final[Redirect] = Redirect()


@pipe
async def redirect(
    out: PipeWriter,
    err: PipeWriter,
    stdout: Redirect = STDOUT,  # pylint: disable=redefined-outer-name
    stderr: Redirect = STDERR,  # pylint: disable=redefined-outer-name
) -> Process[T | PipeStart, T | PipeStart]:
    if stdout == STDOUT and stderr == STDOUT:
        return (
            combine_pipes(out, err),
            _NullPipeWriter(),
            forward_result,
        )
    if stdout == STDERR and stderr == STDERR:
        return (
            _NullPipeWriter(),
            combine_pipes(out, err),
            forward_result,
        )
    if stdout == STDERR and stderr == STDOUT:
        return err, out, forward_result
    if stdout == NULL:
        out = _NullPipeWriter()
    if stderr == NULL:
        err = _NullPipeWriter()

    return out, err, forward_result


@pipe
async def stdout(out: PipeWriter, err: PipeWriter) -> Process[Any, bytes]:
    content = MemoryPipeWriter()

    async def _wait(_: Any) -> bytes:
        await content.close()
        return content.value

    return content, err, _wait


@pipe
async def decode(
    out: PipeWriter, err: PipeWriter, encoding: str = "utf-8"
) -> Process[bytes, str]:
    async def _wait(result: bytes) -> str:
        return result.decode(encoding)

    return out, err, _wait


@pipe
async def dump_json(
    out: PipeWriter, err: PipeWriter, obj: Any
) -> Process[T | PipeStart, T | PipeStart]:
    json = dumps(obj).encode("utf-8")
    return _concatenate(BytesIO(json), out, err)


@pipe
async def parse_json(out: PipeWriter, err: PipeWriter) -> Process[Any, object]:
    capture = MemoryPipeWriter()

    async def _wait(_: Any) -> Any:
        await capture.close()
        return loads(capture.value.decode("utf-8"))

    return capture, err, _wait


@pipe
async def dump_yaml(
    out: PipeWriter, err: PipeWriter, obj: Any
) -> Process[T | PipeStart, T | PipeStart]:
    yaml_content = yaml_dump(obj, Dumper=Dumper).encode("utf-8")
    return _concatenate(BytesIO(yaml_content), out, err)


@pipe
async def parse_yaml(out: PipeWriter, err: PipeWriter) -> Process[Any, object]:
    capture = MemoryPipeWriter()

    async def _wait(_: Any) -> Any:
        await capture.close()
        return yaml_load(capture.value.decode("utf-8"), Loader=Loader)

    return capture, err, _wait
