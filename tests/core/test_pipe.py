"""Streams test method."""
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

from pytest import raises

from jshell.core.pipe import (
    PIPE_START,
    STDOUT,
    AggregatePipeWriter,
    MemoryPipeWriter,
    PipeWriter,
    Process,
    _NullPipeWriter,
    cat,
    echo,
    log,
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


async def test_aggregate_pipe_writer() -> None:
    """An aggregate pipe writer should forward data to it's children."""
    _1 = AsyncMock()
    _2 = AsyncMock()
    writer = AggregatePipeWriter(_1, _2)

    await writer.write(b"Kweek kweek")

    _1.write.assert_awaited_once_with(b"Kweek kweek")
    _2.write.assert_awaited_once_with(b"Kweek kweek")

    await writer.close()
    _1.close.assert_awaited_once()
    _2.close.assert_awaited_once()


async def test_aggregate_pipe_writer_merge() -> None:
    """A compound pipe writer merge function should drop useless writers."""

    null_pipe: PipeWriter = _NullPipeWriter()
    impl_pipe: PipeWriter = MemoryPipeWriter()
    assert AggregatePipeWriter.merge(null_pipe, impl_pipe) == impl_pipe
    assert AggregatePipeWriter.merge(impl_pipe, null_pipe) == impl_pipe

    for _1, _2 in [
        (
            AggregatePipeWriter(MemoryPipeWriter()),
            AggregatePipeWriter(MemoryPipeWriter()),
        ),
        (AggregatePipeWriter(MemoryPipeWriter()), MemoryPipeWriter()),
        (MemoryPipeWriter(), AggregatePipeWriter(MemoryPipeWriter())),
        (MemoryPipeWriter(), MemoryPipeWriter()),
    ]:
        merged = AggregatePipeWriter.merge(cast(PipeWriter, _1), cast(PipeWriter, _2))
        assert isinstance(merged, AggregatePipeWriter)
        children = list(merged.children)
        assert isinstance(children[0], MemoryPipeWriter)
        assert isinstance(children[1], MemoryPipeWriter)


async def test_await_pipe() -> None:
    """Awaiting a pipe should start and wait for it to exit."""
    result = object()

    async def _wait(previous_result: Any) -> object:
        assert previous_result == PIPE_START
        return result

    wait = AsyncMock(side_effect=_wait)

    @pipe
    async def _pipe(stdout: PipeWriter, stderr: PipeWriter) -> Process[Any, object]:
        await stdout.write(b"")
        return stdout, stderr, wait

    assert result == await _pipe()
    wait.assert_awaited_once()


async def test_pipe_combination() -> None:
    """Combining pipes should pipe result and stdout through the pipe chain."""

    @pipe
    async def _oh_shit(stdout: PipeWriter, stderr: PipeWriter) -> Process[Any, str]:
        await stdout.write(b"no.")

        async def wait(_: Any) -> str:
            return "oh shit"

        return stdout, stderr, wait

    @pipe
    async def _exclaim(stdout: PipeWriter, stderr: PipeWriter) -> Process[str, str]:
        await stdout.write(b"oh.")

        async def wait(result: str) -> str:
            return f"{result} !!1"

        return stdout, stderr, wait

    @pipe
    async def _yell(_: PipeWriter, stderr: PipeWriter) -> Process[str, str]:
        async def wait(result: str) -> str:
            return f"{result}".upper()

        return out, stderr, wait

    out = MemoryPipeWriter()

    result = await (_oh_shit() | _exclaim() | _yell())

    assert result == "OH SHIT !!1"
    await out.close()
    assert out.value == b"oh.no."


async def test_pipe_to_function() -> None:
    """Combining pipe to function should pipe result of the command through it."""

    @pipe
    async def _oh_shit(stdout: PipeWriter, stderr: PipeWriter) -> Process[Any, str]:
        async def wait(value: Any) -> str:
            return "oh shit"

        return stdout, stderr, wait

    async def _yell(result: str) -> str:
        return f"{result} !!1".upper()

    assert await (_oh_shit() | _yell) == "OH SHIT !!1"


async def test_cat(shared_datadir: Path) -> None:
    """echo method should return a pipe writing content to stdout."""
    path = shared_datadir / "yodeldidoo"
    assert await (cat(path) | STDOUT) == b"Yodeldidoo\n"
    assert await (cat(str(path)) | STDOUT) == b"Yodeldidoo\n"


async def test_echo() -> None:
    """echo method should return a pipe writing content to stdout."""
    assert await (echo(b"Yodeldidoo") | STDOUT) == b"Yodeldidoo"
    assert await (echo("Yodeldidoo") | STDOUT) == b"Yodeldidoo"


async def test_log() -> None:
    """echo method should return a pipe writing content to stdout."""
    logger = Mock()

    assert await (echo(b"Yodeldidoo\n") | log(logger))
    logger.info.assert_called_once_with("Yodeldidoo")


async def test_stdout() -> None:
    """stdout should return a pipe returning the content of stdout."""

    @pipe
    async def _echo(stdout: PipeWriter, stderr: PipeWriter) -> Process[Any, Any]:
        async def _wait(_: Any) -> Any:
            await stdout.write(b"didi")

        await stdout.write(b"Yodel")
        return stdout, stderr, _wait

    assert await (_echo() | STDOUT) == b"Yodeldidi"
