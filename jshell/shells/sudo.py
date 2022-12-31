"""Shell wrapping all commands in sudo calls."""
from typing import Any

from jshell.command import Process
from jshell.shells import Shell


class SudoShell(Shell):
    """Shell wrapping another so all commands are executed using sudo."""

    def __init__(self, inner: Shell, user: str | None = None, **kwargs: Any) -> None:
        """Wraps a shell so all commands are executed using sudo.

        :param inner: The shell to wrap.
        :param user: The user to give as -u flag to sudo.
        :return: A shell executing all commands with sudo.
        """
        super().__init__(**kwargs)
        self._inner = inner
        self._user = user

    def _create_process(self, command: str) -> Process:
        if self._user is not None:
            command = f"-u {self._user} command"
        return self._inner._create_process(  # pylint: disable=protected-access
            f"sudo {command}"
        )
