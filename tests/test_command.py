"""Command unit tests."""
from pathlib import Path

from jshell.command import Command
from jshell.streams import MemoryPipeWriter, PipeWriter


class _Echo:
    def __init__(self, content: bytes = b"", return_code: int = 0):
        self._content = content
        self._return_code = return_code
        self.stdin = MemoryPipeWriter()

    async def start(self, stdout: PipeWriter) -> PipeWriter:
        """start the mock process."""
        await stdout.write(self._content)
        await stdout.close()
        return self.stdin

    async def wait(self) -> int:
        """Stop the mock process."""
        return self._return_code


class _Cat:
    async def start(self, stdout: PipeWriter) -> PipeWriter:
        """start the mock process."""
        return stdout

    async def wait(self) -> int:
        """Stop the mock process."""
        return 0


async def test_result_truth() -> None:
    """Command result should evaluate to true if command succeed, false otherwise."""
    assert await Command(_Echo(return_code=0))
    assert not await Command(_Echo(return_code=-1))


async def test_result_stdout() -> None:
    """Command result to string should return the utf-8 decoded content of stdout."""
    result = await Command(_Echo(b"Kweek kweek"))
    assert result.stdout == b"Kweek kweek"
    assert str(result) == "Kweek kweek"


async def test_pipe_to_command() -> None:
    """stdout of command should be piped stdin of the next."""
    echo = _Echo(b"Kweek kweek")
    cat = _Cat()

    result = await (Command(echo) | Command(cat))
    assert result.stdout == b"Kweek kweek"
    assert str(result) == "Kweek kweek"


async def test_pipe_to_file(tmp_path: Path) -> None:
    """command stdout should be written to a file if piped to a path."""
    echo = _Echo(b"denise")
    otter_vault = tmp_path / "otters"

    result = await (Command(echo) | otter_vault)
    assert str(result) == ""
    with open(otter_vault, "r", encoding="utf-8") as file:
        assert file.read() == "denise"


async def test_pipe_to_pipe_writer() -> None:
    """command stdout should be written to a PipeWriter instance if piped to it."""
    writer = MemoryPipeWriter()
    echo = _Echo(b"odette")

    result = await (Command(echo) | writer)
    assert str(result) == ""
    assert writer.value == b"odette"


async def test_pipe_to_multiple_outputs() -> None:
    """piping to several output should write in each of them."""
    otter_vault = MemoryPipeWriter()
    otter_super_vault = MemoryPipeWriter()

    echo = _Echo(b"gilbert")

    result = await (Command(echo) | otter_vault | otter_super_vault)
    assert str(result) == ""
    assert otter_vault.value == b"gilbert"
    assert otter_super_vault.value == b"gilbert"
