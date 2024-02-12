from jiac import MemoryStream


async def test_memory_stream() -> None:
    stream = MemoryStream()
    await stream.write(b"Wubba lubba")
    assert stream.buffer == b"Wubba lubba"

    buffer = bytearray()
    stream = MemoryStream(buffer)
    await stream.write(b"Wubba lubba")
    assert buffer == b"Wubba lubba"
