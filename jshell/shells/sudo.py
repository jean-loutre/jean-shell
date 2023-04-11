"""Shell wrapping all commands in sudo calls."""
from shlex import quote
from typing import Any

from jshell.core.pipe import PipeWriter
from jshell.core.shell import Shell, ShellProcess


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

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        if self._user is not None:
            command = f"sudo -u {self._user} sh -c {quote(command)}"
        else:
            command = f"sudo sh -c {quote(command)}"

        return await self._inner._start_process(  # pylint: disable=protected-access
            out, err, command, env
        )
