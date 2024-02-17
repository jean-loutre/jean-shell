"""Connectors are usable to send commands to a target."""
from logging import Logger
from typing import Any, AsyncIterator
from contextlib import asynccontextmanager

from asyncssh import (
    SSHClientConnection,
    SSHClientConnectionOptions,
    SSHClientProcess,
    SSHWriter,
    connect,
)
from asyncssh.logging import SSHLogger

from jtoto.shell import Process, Shell, Stderr, Stdout
from jtoto.stream import Stream


@asynccontextmanager
async def ssh_shell(
    host: str, port: int = 22, logger: Logger | None = None, **kwargs: Any
) -> AsyncIterator[Shell]:
    async with connect(
        host, port=port, options=SSHClientConnectionOptions(**kwargs)
    ) as connection:
        yield _SshShell(connection, logger=logger)


class _SshStream(Stream):
    def __init__(self, writer: SSHWriter[bytes]):
        self._writer = writer

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.write_eof()
        await self._writer.drain()
        await self._writer.wait_closed()


class _SshShell(Shell):
    def __init__(
        self, connection: SSHClientConnection, logger: Logger | None = None
    ) -> None:
        super().__init__(logger=logger)
        self._connection = connection
        if logger:
            ssh_logger = logger.getChild("ssh")
            self._connection._logger = SSHLogger(parent=ssh_logger)

    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        process: SSHClientProcess[Any] = await self._connection.create_process(
            command, stdout=out, stderr=err, env=env, encoding=None
        )

        async def _wait() -> int:
            await process.wait_closed()
            return_code = process.returncode
            if return_code is None:
                # TODO: Handle this better, None value is when process
                # exits due to a signal.
                return -1
            return return_code

        return _SshStream(process.stdin), err, _wait()
