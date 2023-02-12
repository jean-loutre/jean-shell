"""Config unit tests."""
from logging import Logger
from typing import Any
from unittest.mock import AsyncMock, Mock

from pytest import raises

from jshell.core.pipe import PipeWriter, echo
from jshell.core.shell import Shell, ShellProcess, ShellProcessException


class MockShell(Shell):
    """An shell usable to run commands on hosts."""

    def __init__(self, logger: Logger | None = None) -> None:
        super().__init__(logger=logger)
        self.start = AsyncMock()
        self.start.return_value = (AsyncMock(), AsyncMock(), AsyncMock())

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        await self.start(command, env)

        if command == "echo":
            await out.write(b"Yodeldidoo\n")

        async def _wait(_: Any) -> int:
            return 0

        return out, err, _wait


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
    stdout_logger = Mock()
    logger.getChild = Mock(return_value=stdout_logger)
    sh = MockShell(logger=logger)

    await sh("echo")
    stdout_logger.info.assert_called_with("Yodeldidoo")

    stdout_logger.reset_mock()
    with sh.log(None):
        await sh("echo")
        stdout_logger.info.assert_not_called()

    logger_override = Mock()
    stdout_logger_override = Mock()
    logger_override.getChild = Mock(return_value=stdout_logger_override)
    with sh.log(logger_override):
        await (echo("Yodeldidoo\n") | sh(""))
        stdout_logger.info.assert_not_called()
        stdout_logger_override.info.assert_called_with("Yodeldidoo")

    stdout_logger_override.reset_mock()
    await (echo("Yodeldidoo\n") | sh(""))
    stdout_logger.info.assert_called_with("Yodeldidoo")
    stdout_logger_override.info.assert_not_called()


async def test_raise_on_error() -> None:
    """Shell should raise an error when a process fails if it's configured to."""

    class _FailShell(Shell):
        async def _start_process(
            self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
        ) -> ShellProcess:
            await err.write(b"Wubba Lubba\n")

            async def _wait(_: Any) -> int:
                await err.write(b"Dub Dub\n")
                return 1

            return out, err, _wait

    sh = _FailShell(raise_on_error=False)
    await sh("fail")

    sh = _FailShell()
    with raises(
        ShellProcessException,
        match=r"fail returned code 1. Last stderr output:\nWubba Lubba\nDub Dub",
    ):
        await sh("fail")

    with sh.raise_on_error(False):
        await sh("fail")

    with raises(ShellProcessException):
        await sh("fail")
