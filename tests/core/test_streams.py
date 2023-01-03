"""Streams test method."""
from unittest.mock import AsyncMock

from pytest import raises

from jshell.core.pipe import CompoundPipeWriter, MemoryPipeWriter


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
    jean_jacques = AsyncMock()
    denise = AsyncMock()
    writer = CompoundPipeWriter(jean_jacques, denise)

    await writer.write(b"Kweek kweek")

    jean_jacques.write.assert_awaited_once_with(b"Kweek kweek")
    denise.write.assert_awaited_once_with(b"Kweek kweek")

    await writer.close()
    jean_jacques.close.assert_awaited_once()
    denise.close.assert_awaited_once()
