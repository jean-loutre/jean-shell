"""Config unit tests."""
from logging import Logger
from typing import cast
from unittest.mock import Mock

from jshell.command import Process
from jshell.shells import Shell


class MockShell(Shell):
    """An shell usable to run commands on hosts."""

    def __init__(self, log: Logger | None = None) -> None:
        super().__init__(log=log)
        self.create_process = Mock()

    def _create_process(self, command: str, env: dict[str, str]) -> Process:
        return cast(Process, self.create_process(command, env))


async def test_env() -> None:
    """Shell should set environment variables."""
    shell = MockShell()
    shell.run("power-weasel")
    shell.create_process.assert_called_once_with("power-weasel", {})

    with shell.env(POWER_LEVEL="3"):
        shell.create_process.reset_mock()
        shell.run("power-weasel")
        shell.create_process.assert_called_once_with(
            "power-weasel", {"POWER_LEVEL": "3"}
        )

        with shell.env(WEASER_ANGER="55"):
            shell.create_process.reset_mock()
            shell.run("power-weasel")
            shell.create_process.assert_called_once_with(
                "power-weasel", {"POWER_LEVEL": "3", "WEASER_ANGER": "55"}
            )

        shell.create_process.reset_mock()
        shell.run("power-weasel")
        shell.create_process.assert_called_once_with(
            "power-weasel", {"POWER_LEVEL": "3"}
        )

    shell.create_process.reset_mock()
    shell.run("power-weasel")
    shell.create_process.assert_called_once_with("power-weasel", {})
