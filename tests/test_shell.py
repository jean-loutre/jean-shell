"""Config unit tests."""
from logging import DEBUG, INFO, Logger, getLogger
from unittest.mock import AsyncMock, Mock, call, patch

from pytest import raises

from jiac import (
    FROM_STDERR,
    LogLevel,
    Process,
    Shell,
    ProcessFailedError,
    Stderr,
    Stdout,
    command,
    echo,
    redirect,
    LogStream,
    MemoryStream,
    multiplex,
)


class MockShell(Shell):
    """An shell usable to run commands on hosts."""

    def __init__(self, logger: Logger | None = None) -> None:
        super().__init__(logger=logger)
        self.start = AsyncMock()
        self.start.return_value = (AsyncMock(), AsyncMock(), AsyncMock())

    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        await self.start(command, env)

        async def _wait() -> int:
            return 0

        if command == "echo" and out is not None:
            await out.write(b"Yodeldidoo\n")
            return None, err, _wait()

        return out, err, _wait()


async def test_env() -> None:
    """Shell should set environment variables."""
    sh = MockShell()
    await sh("power-weasel")
    sh.start.assert_called_once_with("power-weasel", {})

    with sh.env(POWER_LEVEL="3"):
        sh.start.reset_mock()
        await sh("power-weasel")
        sh.start.assert_called_once_with("power-weasel", {"POWER_LEVEL": "3"})

        with sh.env(WEASER_ANGER="55"):
            sh.start.reset_mock()
            await sh("power-weasel")
            sh.start.assert_called_once_with(
                "power-weasel", {"POWER_LEVEL": "3", "WEASER_ANGER": "55"}
            )

        sh.start.reset_mock()
        await sh("power-weasel")
        sh.start.assert_called_once_with("power-weasel", {"POWER_LEVEL": "3"})

    sh.start.reset_mock()
    await sh("power-weasel")
    sh.start.assert_called_once_with("power-weasel", {})


async def test_log() -> None:
    """Shell should setup logging correctly."""
    logger = Mock()
    sh = MockShell(logger=logger)

    await sh("echo")
    logger.log.assert_called_with(LogLevel.STDOUT, "Yodeldidoo")

    logger.reset_mock()
    with sh.raise_on_error(False):
        await sh("echo")
    logger.log.assert_called_with(LogLevel.STDOUT, "Yodeldidoo")

    logger.reset_mock()
    with sh.log(None):
        await sh("echo")
        logger.log.assert_not_called()

    logger_override = Mock()
    with sh.log(logger_override):
        await (echo("Yodeldidoo\n") | sh(""))
        logger.log.assert_not_called()
        logger_override.log.assert_called_with(LogLevel.STDOUT, "Yodeldidoo")

    logger_override.reset_mock()
    await (echo("Yodeldidoo\n") | sh(""))
    logger.log.assert_called_with(LogLevel.STDOUT, "Yodeldidoo")
    logger_override.log.assert_not_called()


async def test_command_log() -> None:
    logger = Mock()
    logger = Mock()
    sh = MockShell(logger=logger)

    # Only last command should be logged
    await (echo("Wubba lubba\n") | sh("echo") | sh(""))
    logger.log.assert_called_once_with(LogLevel.STDOUT, "Yodeldidoo")

    # Redirecting output should disable logging
    logger.reset_mock()
    await (sh("echo") >> None)
    logger.log.assert_not_called()


async def test_raise_on_error() -> None:
    """Shell should raise an error when a process fails if it's configured to."""

    class _FailShell(Shell):
        async def _start_process(
            self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
        ) -> Process:
            if err is not None:
                await err.write(b"Wubba Lubba\n")

            async def _run() -> int:
                if err is not None:
                    await err.write(b"Dub Dub\n")
                return 1

            return out, err, _run()

    sh = _FailShell(raise_on_error=False)
    await sh("fail")

    sh = _FailShell()
    with raises(
        ProcessFailedError,
        match=r"fail returned code 1.\nLast stderr output:\nWubba Lubba\nDub Dub",
    ):
        await sh("fail")

    with sh.raise_on_error(False):
        await sh("fail")

    with raises(ProcessFailedError):
        await sh("fail")


@command
async def mock_echo(out: Stdout, err: Stderr) -> Process:
    async def _run() -> int:
        assert out is not None
        await out.write(b"Youpi")
        return 0

    return out, err, _run()


@command
async def mock_echo_err(out: Stdout, err: Stderr) -> Process:
    async def _run() -> int:
        assert err is not None
        await err.write(b"Youpi")
        return 0

    return out, err, _run()


async def test_memory_stream() -> None:
    stream = MemoryStream()
    await stream.write(b"Kweek kweek")
    assert stream.buffer == b"Kweek kweek"

    buffer = bytearray()
    stream = MemoryStream(buffer)
    await stream.write(b"Kweek kweek")
    assert buffer == b"Kweek kweek"


async def test_multiplex_stream() -> None:
    _1 = AsyncMock()
    _2 = AsyncMock()
    _3 = AsyncMock()

    child_stream = multiplex(_1, _2)
    assert child_stream is not None

    stream = multiplex(child_stream, _2, _3)
    assert stream is not None

    with patch.object(child_stream, "write") as mock:
        await stream.write(b"Kweek kweek")

        _1.write.assert_awaited_once_with(b"Kweek kweek")
        _2.write.assert_awaited_once_with(b"Kweek kweek")
        _3.write.assert_awaited_once_with(b"Kweek kweek")
        mock.assert_not_awaited()

    with patch.object(child_stream, "close") as mock:
        await stream.close()

        _1.close.assert_awaited_once()
        _2.close.assert_awaited_once()
        _3.close.assert_awaited_once()
        mock.assert_not_awaited()

    null_stream = multiplex(None, None)
    assert null_stream is None


async def test_pipe_command() -> None:
    result = MemoryStream()

    @command
    async def _cat(out: Stdout, err: Stderr) -> Process:
        async def _run() -> int:
            return 1

        return result, err, _run()

    await (mock_echo() | _cat())

    assert result.buffer == b"Youpi"


async def test_bytearray_redirection() -> None:
    buffer_1 = bytearray()
    buffer_2 = bytearray()
    await (mock_echo() >> buffer_1 >> buffer_2)
    assert buffer_1 == b"Youpi"
    assert buffer_2 == b"Youpi"

    buffer_1 = bytearray()
    buffer_2 = bytearray()
    await (mock_echo_err() | redirect(stdout=FROM_STDERR) >> buffer_1 >> buffer_2)
    assert buffer_1 == b"Youpi"
    assert buffer_2 == b"Youpi"


async def test_logger_redirection() -> None:
    logger = getLogger()
    with patch.object(logger, "log") as mock:
        await (echo("Peter\nSteven") >> LogStream(logger))
        mock.assert_has_calls([call(DEBUG, "Peter"), call(DEBUG, "Steven")])
        mock.reset_mock()

        await (echo("Peter\nSteven") >> LogStream(logger, level=INFO))
        mock.assert_has_calls([call(INFO, "Peter"), call(INFO, "Steven")])


async def test_write_stdin() -> None:
    stdout = bytearray()
    sh = MockShell()
    async with (sh("anyway") >> stdout).write_stdin() as stdin:
        assert stdin is not None
        await stdin.write(b"Yodeldidoo")

    assert stdout == b"Yodeldidoo"
