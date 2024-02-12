from jiac import MemoryStream, LineStream, LogStream, multiplex
from logging import INFO
from unittest.mock import Mock, AsyncMock


async def test_memory_stream() -> None:
    stream = MemoryStream()
    await stream.write(b"Wubba lubba")
    assert stream.buffer == b"Wubba lubba"

    buffer = bytearray()
    stream = MemoryStream(buffer)
    await stream.write(b"Wubba lubba")
    assert buffer == b"Wubba lubba"


async def test_line_stream() -> None:
    lines: list[str] = []

    class _TestLineStream(LineStream):
        def write_line(self, line: str) -> None:
            lines.append(line)

    async with _TestLineStream() as stream:
        await stream.write(b"Yodel")
        assert lines == []

        await stream.write(b"Yodel\nDee doo")
        assert lines == ["YodelYodel"]

    assert lines == ["YodelYodel", "Dee doo"]


async def test_log_stream() -> None:
    logger = Mock()
    async with LogStream(logger, INFO) as stream:
        await stream.write(b"Yodel")
        logger.log.assert_not_called()

        await stream.write(b"Yodel\nDee doo")
        logger.log.assert_called_once_with(INFO, "YodelYodel")
        logger.log.reset_mock()

    logger.log.assert_called_once_with(INFO, "Dee doo")


async def test_multiplex_stream() -> None:
    peter = AsyncMock()
    steven = AsyncMock()

    stream = multiplex(peter, steven, None)
    assert stream is not None
    async with stream:
        await stream.write(b"Wubba lubba")
        peter.write.assert_awaited_once_with(b"Wubba lubba")
        steven.write.assert_awaited_once_with(b"Wubba lubba")

    peter.close.assert_awaited_once()
    steven.close.assert_awaited_once()

    assert multiplex(None, None, None) is None
