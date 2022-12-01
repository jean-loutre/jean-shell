"""Streams test method."""
from unittest.mock import AsyncMock

from pytest import raises

from jshell.streams import CompoundPipeWriter, MemoryPipeWriter


async def test_memory_pipe_writer() -> None:
    """A memory pipe writer should allow to access written bytes once closed."""
    writer = MemoryPipeWriter()
    await writer.write(b"Kweek kweek")

    with raises(AssertionError):
        print(writer.value)

    await writer.close()
    assert writer.value == b"Kweek kweek"


async def test_compound_pipe_writer() -> None:
    """A compound pipe writer should forward data to it's children."""
    jshell = AsyncMock()
    denise = AsyncMock()
    writer = CompoundPipeWriter(jshell, denise)

    await writer.write(b"Kweek kweek")

    jshell.write.assert_awaited_once_with(b"Kweek kweek")
    denise.write.assert_awaited_once_with(b"Kweek kweek")

    await writer.close()
    jshell.close.assert_awaited_once()
    denise.close.assert_awaited_once()
