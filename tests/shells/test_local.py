"""Config unit tests."""
from asyncio import StreamReader
from contextlib import contextmanager
from subprocess import PIPE
from typing import Iterator
from unittest.mock import AsyncMock, patch

from jshell.core.pipe import STDERR, STDOUT, echo, redirect, stdout
from jshell.shells.local import local_shell


class _StreamWriterMock:
    def __init__(self) -> None:
        self._data = b""

    @property
    def data(self) -> bytes:
        return self._data

    def write(self, data: bytes) -> None:
        self._data = self._data + data

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


class _ProcessMock:
    def __init__(
        self,
        stdin: _StreamWriterMock,
        stdout_data: bytes,
        stderr_data: bytes,
        return_code: int = 0,
    ) -> None:
        self._stdout = StreamReader()
        self._stdout.feed_data(stdout_data)
        self._stdout.feed_eof()

        self._stderr = StreamReader()
        self._stderr.feed_data(stderr_data)
        self._stderr.feed_eof()

        self._stdin = stdin
        self._return_code = return_code

    @property
    def stdout(self) -> StreamReader:
        return self._stdout

    @property
    def stderr(self) -> StreamReader:
        return self._stderr

    @property
    def stdin(self) -> _StreamWriterMock:
        return self._stdin

    async def wait(self) -> int:
        return self._return_code


@contextmanager
def mock_create_process(
    stdout_data: bytes | None = None,
    stderr_data: bytes | None = None,
    stdin: _StreamWriterMock | None = None,
    return_code: int = 0,
) -> Iterator[AsyncMock]:
    stdout_data = stdout_data or b""
    stderr_data = stderr_data or b""
    stdin = stdin or _StreamWriterMock()
    process_mock = _ProcessMock(stdin, stdout_data, stderr_data, return_code)

    async def create_process(
        command: str,
        stdout: int,
        stderr: int,
        env: dict[str, str],  # pylint: disable=unused-argument
    ) -> _ProcessMock:
        assert command == "tickle otter"
        assert stdout == PIPE
        assert stderr == PIPE
        return process_mock

    with patch(
        "jshell.shells.local.create_subprocess_shell",
        return_value=process_mock,
        autospec=True,
    ) as mock:
        yield mock


async def test_run() -> None:
    with mock_create_process(return_code=1) as mock:
        async with local_shell() as sh:
            with sh.raise_on_error(False):
                with sh.env(OTTER_SENSITIVITY="low"):
                    assert (await sh("tickle otter")) == 1
                    mock.assert_awaited_once_with(
                        "tickle otter",
                        stdout=PIPE,
                        stderr=PIPE,
                        stdin=PIPE,
                        env={"OTTER_SENSITIVITY": "low"},
                    )


async def test_stdout() -> None:
    with mock_create_process(stdout_data=b"kweek kweek"):
        async with local_shell() as sh:
            out = await (sh("tickle otter") | stdout())
            assert out == b"kweek kweek"


async def test_stderr() -> None:
    with mock_create_process(stderr_data=b"kweek kweek"):
        async with local_shell() as sh:
            out = await (
                sh("tickle otter") | redirect(stdout=STDERR, stderr=STDOUT) | stdout()  # type: ignore
            )
            assert out == b"kweek kweek"


async def test_stdin() -> None:
    """LocalShell should write to subprocess stdin."""
    with mock_create_process(stderr_data=b"kweek kweek") as mock:
        async with local_shell() as sh:
            await (echo(b"kweek kweek") | sh("tickle otter"))
            assert mock.return_value.stdin.data == b"kweek kweek"
