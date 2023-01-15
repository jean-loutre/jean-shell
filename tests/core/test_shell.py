"""Config unit tests."""
from logging import Logger
from typing import Any
from unittest.mock import AsyncMock, Mock

from jshell.core.pipe import PipeWriter, echo
from jshell.core.shell import Shell, ShellProcess


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
    sh = MockShell(logger=logger)

    await (echo("Yodeldidoo\n") | sh(""))
    logger.info.assert_called_with("Yodeldidoo")

    logger.reset_mock()
    with sh.log(None):
        await (echo("Yodeldidoo\n") | sh(""))
        logger.info.assert_not_called()

    logger_override = Mock()
    with sh.log(logger_override):
        await (echo("Yodeldidoo\n") | sh(""))
        logger.info.assert_not_called()
        logger_override.info.assert_called_with("Yodeldidoo")

    logger_override.reset_mock()
    await (echo("Yodeldidoo\n") | sh(""))
    logger.info.assert_called_with("Yodeldidoo")
    logger_override.info.assert_not_called()
