from jiac import MemoryStream, LineStream, LogStream, multiplex, pipe, Stream
from logging import INFO
from asyncio import timeout, gather, sleep
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
    stream = multiplex(peter, steven, stream)
    assert stream is not None
    async with stream:
        await stream.write(b"Wubba lubba")
        peter.write.assert_awaited_once_with(b"Wubba lubba")
        steven.write.assert_awaited_once_with(b"Wubba lubba")

    peter.close.assert_awaited_once()
    steven.close.assert_awaited_once()

    assert multiplex(None, None, None) is None


async def test_pipe_stream() -> None:
    async def _write(in_: Stream) -> None:
        await in_.write(b"Wubba")
        # Found nothing better to force InputStream to read data in two
        # batches, but should work the immense majority of the time.
        await sleep(0.1)
        await in_.write(b" lubba")
        await in_.close()

    async with timeout(1):
        in_, out = pipe()

        async def _read() -> None:
            assert await out.read() == b"Wubba lubba"

        await gather(_write(in_), _read())

        in_, out = pipe()

        async def _read() -> None:
            assert await out.read(64) == b"Wubba lubba"

        await gather(_write(in_), _read())
