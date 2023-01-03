"""Connectors are usable to send commands to a target."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from logging import Logger
from typing import AsyncIterator

from asyncssh import (
    SSHClientConnection,
    SSHClientConnectionOptions,
    SSHClientProcess,
    SSHWriter,
    connect,
)
from asyncssh.logging import SSHLogger

from jshell.core.command import Process
from jshell.core.pipe import PipeWriter
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


class _SshShell(Shell):
    def __init__(
        self, connection: SSHClientConnection, log: Logger | None = None
    ) -> None:
        super().__init__(log=log)
        self._connection = connection
        if log:
            self._connection._logger = SSHLogger(parent=log.getChild("ssh"))

    def _create_process(self, command: str, env: dict[str, str]) -> Process:
        return _SshProcess(self._connection, command, env)


class _SshPipeWriter:
    def __init__(self, writer: SSHWriter[bytes]):
        self._writer = writer

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()


class _SshProcess:
    def __init__(
        self, connection: SSHClientConnection, command: str, env: dict[str, str]
    ):
        self._connection = connection
        self._command = command
        self._env = env
        self._process: SSHClientProcess[bytes] | None = None

    async def start(self, stdout: PipeWriter) -> PipeWriter:
        """Start the given SSH process.

        :return: The returncode.
        """
        self._process = await self._connection.create_process(
            self._command, stdout=stdout, env=self._env
        )
        return _SshPipeWriter(self._process.stdin)

    async def wait(self) -> int:
        """Wait for the underlying SSHProcess to finish.

        :return: The returncode.
        """
        assert self._process is not None
        await self._process.wait_closed()
        return_code = self._process.returncode
        if return_code is None:
            # TODO: Handle this better, None value is when process
            # exits due to a signal.
            return -1
        return return_code
