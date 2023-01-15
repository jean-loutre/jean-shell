"""Connectors are usable to send commands to a target."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger
from typing import Any, AsyncIterator

from asyncssh import SSHClientConnection, SSHClientConnectionOptions, SSHWriter, connect
from asyncssh.logging import SSHLogger

from jshell.core.pipe import PipeWriter, Process
from jshell.core.shell import Shell


@dataclass(frozen=True, kw_only=True)
class SshSettings:
    """Settings for an SSH connection."""

    host: str
    """Host to connect to."""

    user: str | None = None
    """User to connect with."""

    @asynccontextmanager
    async def connect(self, log: Logger | None = None) -> AsyncIterator[Shell]:
        """Open an ssh connection using this settings.

        :return: A `Shell` object usable to interact with the remote host.
        """
        async with connect(
            self.host, options=SSHClientConnectionOptions(username=self.user)
        ) as connection:
            yield _SshShell(connection, log=log)


class _SshPipeWriter:
    def __init__(self, writer: SSHWriter[bytes]):
        self._writer = writer

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()


class _SshShell(Shell):
    def __init__(
        self, connection: SSHClientConnection, log: Logger | None = None
    ) -> None:
        super().__init__(log=log)
        self._connection = connection
        if log:
            self._connection._logger = SSHLogger(parent=log.getChild("ssh"))

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> Process[Any, int]:
        process = await self._connection.create_process(
            command, stdout=out, stderr=err, env=env
        )

        async def _wait(_: Any) -> int:
            await process.wait_closed()
            return_code = process.returncode
            if return_code is None:
                # TODO: Handle this better, None value is when process
                # exits due to a signal.
                return -1
            return return_code

        return _SshPipeWriter(process.stdin), err, _wait
