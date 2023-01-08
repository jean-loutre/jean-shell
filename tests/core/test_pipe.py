"""Streams test method."""
from typing import Any
from unittest.mock import AsyncMock

from pytest import raises

from jshell.core.pipe import (
    PIPE_START,
    AggregatePipeWriter,
    ConcurrentPipeWriter,
    MemoryPipeWriter,
    PipeWriter,
    Process,
    _NullPipeWriter,
    pipe,
)


async def test_memory_pipe_writer() -> None:
    """A memory pipe writer should allow to access written bytes once closed."""
    writer = MemoryPipeWriter()
    await writer.write(b"Kweek kweek")

    with raises(AssertionError):
        print(writer.value)

    await writer.close()
    assert writer.value == b"Kweek kweek"


async def test_aggregate_pipe_writer_merge() -> None:
    """A compound pipe writer merge function should drop useless writers."""

    class _DummyPipeWriter(AggregatePipeWriter):
        async def write(self, data: bytes) -> None:
            pass

        async def close(self) -> None:
            pass

    _1: PipeWriter = _NullPipeWriter()
    _2: PipeWriter = _NullPipeWriter()
    merged: PipeWriter = _DummyPipeWriter.merge(_1, _2)
    assert merged == _2

    _1 = MemoryPipeWriter()
    _2 = _NullPipeWriter()
    merged = _DummyPipeWriter.merge(_1, _2)
    assert merged == _1

    _1 = _DummyPipeWriter(MemoryPipeWriter())
    _2 = _DummyPipeWriter(MemoryPipeWriter())
    merged = _DummyPipeWriter.merge(_1, _2)
    assert isinstance(merged, _DummyPipeWriter)
    children = list(merged.children)
    assert isinstance(children[0], MemoryPipeWriter)
    assert isinstance(children[1], MemoryPipeWriter)

    _1 = _DummyPipeWriter(MemoryPipeWriter())
    _2 = MemoryPipeWriter()
    merged = _DummyPipeWriter.merge(_1, _2)
    assert isinstance(merged, _DummyPipeWriter)
    children = list(merged.children)
    assert len(children) == 2
    assert isinstance(children[0], MemoryPipeWriter)
    assert isinstance(children[1], MemoryPipeWriter)

    _1 = MemoryPipeWriter()
    _2 = _DummyPipeWriter(MemoryPipeWriter())
    merged = _DummyPipeWriter.merge(_1, _2)
    assert isinstance(merged, _DummyPipeWriter)
    children = list(merged.children)
    assert isinstance(children[0], MemoryPipeWriter)
    assert isinstance(children[1], MemoryPipeWriter)

    _1 = MemoryPipeWriter()
    _2 = MemoryPipeWriter()
    merged = _DummyPipeWriter.merge(_1, _2)
    assert isinstance(merged, _DummyPipeWriter)
    children = list(merged.children)
    assert isinstance(children[0], MemoryPipeWriter)
    assert isinstance(children[1], MemoryPipeWriter)


async def test_concurrent_pipe_writer() -> None:
    """A compound pipe writer should forward data to it's children."""
    jean_jacques = AsyncMock()
    denise = AsyncMock()
    writer = ConcurrentPipeWriter(jean_jacques, denise)

    await writer.write(b"Kweek kweek")

    jean_jacques.write.assert_awaited_once_with(b"Kweek kweek")
    denise.write.assert_awaited_once_with(b"Kweek kweek")

    await writer.close()
    jean_jacques.close.assert_awaited_once()
    denise.close.assert_awaited_once()


async def test_await_pipe() -> None:
    """Awaiting a pipe should start and wait for it to exit."""
    result = object()

    async def _wait(previous_result: Any) -> object:
        assert previous_result == PIPE_START
        return result

    wait = AsyncMock(side_effect=_wait)

    @pipe
    async def _pipe(stdout: PipeWriter) -> Process[Any, object]:
        await stdout.write(b"")
        return stdout, wait

    assert result == await _pipe()
    wait.assert_awaited_once()


async def test_pipe_combination() -> None:
    """Combining pipes should pipe result and stdout through the pipe chain."""

    @pipe
    async def _oh_shit(stdout: PipeWriter) -> Process[Any, str]:
        await stdout.write(b"no.")

        async def wait(_: Any) -> str:
            return "oh shit"

        return stdout, wait

    @pipe
    async def _exclaim(stdout: PipeWriter) -> Process[str, str]:
        await stdout.write(b"oh.")

        async def wait(result: str) -> str:
            return f"{result} !!1"

        return stdout, wait

    @pipe
    async def _yell(_: PipeWriter) -> Process[str, str]:
        async def wait(result: str) -> str:
            return f"{result}".upper()

        return out, wait

    out = MemoryPipeWriter()

    result = await (_oh_shit() | _exclaim() | _yell())

    assert result == "OH SHIT !!1"
    await out.close()
    assert out.value == b"oh.no."


async def test_pipe_to_function() -> None:
    """Combining pipe to function should pipe result of the command through it."""

    @pipe
    async def _oh_shit(stdout: PipeWriter) -> Process[Any, str]:
        async def wait(value: Any) -> str:
            return "oh shit"

        return stdout, wait

    async def _yell(result: str) -> str:
        return f"{result} !!1".upper()

    assert await (_oh_shit() | _yell) == "OH SHIT !!1"
