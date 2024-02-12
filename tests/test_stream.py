from jiac import MemoryStream, LineStream


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
