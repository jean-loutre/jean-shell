"""Streams test method."""
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

from pytest import raises

from jshell.core.pipe import (
    PIPE_START,
    STDERR,
    STDOUT,
    CombinedPipeWriter,
    MemoryPipeWriter,
    Pipe,
    PipeStart,
    PipeWriter,
    Process,
    _NullPipeWriter,
    cat,
    combine_pipes,
    dump_json,
    echo,
    log,
    parse_json,
    pipe,
    redirect,
    stdout,
)


async def test_memory_pipe_writer() -> None:
    """A memory pipe writer should allow to access written bytes once closed."""
    writer = MemoryPipeWriter()
    await writer.write(b"Kweek kweek")

    with raises(AssertionError):
        print(writer.value)

    await writer.close()
    assert writer.value == b"Kweek kweek"


async def test_combined_pipe_writer() -> None:
    """An combined pipe writer should forward data to it's children."""
    _1 = AsyncMock()
    _2 = AsyncMock()
    writer = CombinedPipeWriter(_1, _2)

    await writer.write(b"Kweek kweek")

    _1.write.assert_awaited_once_with(b"Kweek kweek")
    _2.write.assert_awaited_once_with(b"Kweek kweek")

    await writer.close()
    _1.close.assert_awaited_once()
    _2.close.assert_awaited_once()


async def test_combined_pipe_writer_merge() -> None:
    """A compound pipe writer merge function should drop useless writers."""

    null_pipe: PipeWriter = _NullPipeWriter()
    impl_pipe: PipeWriter = MemoryPipeWriter()
    assert combine_pipes(null_pipe, impl_pipe) == impl_pipe
    assert combine_pipes(impl_pipe, null_pipe) == impl_pipe

    for _1, _2 in [
        (
            CombinedPipeWriter(MemoryPipeWriter()),
            CombinedPipeWriter(MemoryPipeWriter()),
        ),
        (CombinedPipeWriter(MemoryPipeWriter()), MemoryPipeWriter()),
        (MemoryPipeWriter(), CombinedPipeWriter(MemoryPipeWriter())),
        (MemoryPipeWriter(), MemoryPipeWriter()),
    ]:
        merged = combine_pipes(cast(PipeWriter, _1), cast(PipeWriter, _2))
        assert isinstance(merged, CombinedPipeWriter)
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
    async def _pipe(out: PipeWriter, err: PipeWriter) -> Process[Any, object]:
        await out.write(b"")
        return out, err, wait

    assert result == await _pipe()
    wait.assert_awaited_once()


async def test_pipe_combination() -> None:
    """Combining pipes should pipe result and out through the pipe chain."""

    @pipe
    async def _oh_shit(out: PipeWriter, err: PipeWriter) -> Process[Any, str]:
        await out.write(b"no.")

        async def wait(_: Any) -> str:
            return "oh shit"

        return out, err, wait

    @pipe
    async def _exclaim(out: PipeWriter, err: PipeWriter) -> Process[str, str]:
        await out.write(b"oh.")

        async def wait(result: str) -> str:
            return f"{result} !!1"

        return out, err, wait

    @pipe
    async def _yell(_: PipeWriter, err: PipeWriter) -> Process[str, str]:
        async def wait(result: str) -> str:
            return f"{result}".upper()

        return out, err, wait

    out = MemoryPipeWriter()

    result = await (_oh_shit() | _exclaim() | _yell())

    assert result == "OH SHIT !!1"
    await out.close()
    assert out.value == b"oh.no."


async def test_pipe_to_function() -> None:
    """Combining pipe to function should pipe result of the command through it."""

    @pipe
    async def _oh_shit(out: PipeWriter, err: PipeWriter) -> Process[Any, str]:
        async def wait(value: Any) -> str:
            return "oh shit"

        return out, err, wait

    async def _yell(result: str) -> str:
        return f"{result} !!1".upper()

    assert await (_oh_shit() | _yell) == "OH SHIT !!1"


async def test_cat(shared_datadir: Path) -> None:
    """echo method should return a pipe writing content to out."""
    path = shared_datadir / "yodeldidoo"
    assert await (cat(path) | stdout()) == b"Yodeldidoo\n"
    assert await (cat(str(path)) | stdout()) == b"Yodeldidoo\n"


async def test_echo() -> None:
    """echo method should return a pipe writing content to out."""
    assert await (echo(b"Yodeldidoo") | stdout()) == b"Yodeldidoo"
    assert await (echo("Yodeldidoo") | stdout()) == b"Yodeldidoo"


async def test_log() -> None:
    """echo method should return a pipe writing content to out."""

    def _out(content: str) -> Pipe[PipeStart, PipeStart]:
        return echo(content)

    def _err(content: str) -> Pipe[PipeStart, PipeStart]:
        return echo(content) | redirect(stdout=STDERR, stderr=STDOUT)

    logger = Mock()
    await (_out("Yodeldidoo\n") | log(logger))
    logger.info.assert_called_once_with("Yodeldidoo")

    logger = Mock()
    await (_err("Yodeldidoo\n") | log(logger))
    logger.info.assert_called_once_with("Yodeldidoo")

    logger = Mock()
    await (_out("Yodeldidoo\n") | log(logger, stdout=False))
    logger.info.assert_not_called()

    logger = Mock()
    await (_err("Yodeldidoo\n") | log(logger, stderr=False))
    logger.info.assert_not_called()


async def test_out() -> None:
    """out should return a pipe returning the content of out."""

    @pipe
    async def _echo(out: PipeWriter, err: PipeWriter) -> Process[Any, Any]:
        async def _wait(_: Any) -> Any:
            await out.write(b"didi")

        await out.write(b"Yodel")
        return out, err, _wait

    assert await (_echo() | stdout()) == b"Yodeldidi"


async def test_parse_json() -> None:
    """parse_json should return decoded object read on stdout."""
    assert await (echo('{"wubba": "lubba"}') | parse_json()) == {"wubba": "lubba"}


async def test_dump_json() -> None:
    """parse_json should return decoded object read on stdout."""
    assert await (dump_json({"wubba": "lubba"}) | stdout()) == b'{"wubba": "lubba"}'
