"""Connectors are usable to send commands to a target."""
from logging import Logger
from typing import Any, AsyncIterator

from asyncssh import SSHClientConnection, SSHClientConnectionOptions, SSHWriter, connect
from asyncssh.logging import SSHLogger

from jshell.core.pipe import PipeWriter, Process
from jshell.core.resource import resource
from jshell.core.shell import Shell


@resource
async def ssh(
    host: str, user: str | None = None, logger: Logger | None = None
) -> AsyncIterator[Shell]:
    """Open an ssh connection.

    :return: A `Shell` object usable to interact with the remote host.
    """
    async with connect(
        host, options=SSHClientConnectionOptions(username=user)
    ) as connection:
        yield _SshShell(connection, logger=logger)


class _SshPipeWriter:
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
            self._connection._logger = SSHLogger(parent=logger.getChild("ssh"))

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> Process[Any, int]:
        process = await self._connection.create_process(
            command, stdout=out, stderr=err, env=env, encoding=None
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
