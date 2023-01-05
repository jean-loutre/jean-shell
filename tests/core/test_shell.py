"""Config unit tests."""
from logging import Logger
from typing import cast
from unittest.mock import Mock

from jshell.core.command import Process
from jshell.core.shell import Shell


class MockShell(Shell):
    """An shell usable to run commands on hosts."""

    def __init__(self, log: Logger | None = None) -> None:
        super().__init__(log=log)
        self.create_process = Mock()

    def _create_process(self, command: str, env: dict[str, str]) -> Process:
        return cast(Process, self.create_process(command, env))


async def test_env() -> None:
    """Shell should set environment variables."""
    sh = MockShell()
    sh("power-weasel")
    sh.create_process.assert_called_once_with("power-weasel", {})

    with sh.env(POWER_LEVEL="3"):
        sh.create_process.reset_mock()
        sh("power-weasel")
        sh.create_process.assert_called_once_with("power-weasel", {"POWER_LEVEL": "3"})

        with sh.env(WEASER_ANGER="55"):
            sh.create_process.reset_mock()
            sh("power-weasel")
            sh.create_process.assert_called_once_with(
                "power-weasel", {"POWER_LEVEL": "3", "WEASER_ANGER": "55"}
            )

        sh.create_process.reset_mock()
        sh("power-weasel")
        sh.create_process.assert_called_once_with("power-weasel", {"POWER_LEVEL": "3"})

    sh.create_process.reset_mock()
    sh("power-weasel")
    sh.create_process.assert_called_once_with("power-weasel", {})
