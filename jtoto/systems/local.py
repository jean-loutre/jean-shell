from asyncio import StreamReader, StreamWriter, create_subprocess_shell, create_task
from logging import Logger
from subprocess import PIPE

from jtoto.shell import Process, Shell, Stderr, Stdout
from jtoto.stream import Stream


class LocalShell(Shell):
    def __init__(
        self, logger: Logger | None = None, raise_on_error: bool = True
    ) -> None:
        super().__init__(logger=logger, raise_on_error=raise_on_error)

    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        process = await create_subprocess_shell(
            command,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
            env=env,
        )

        async def _pipe(src: StreamReader, dst: Stdout | Stderr) -> None:
            if dst is None:
                return
            while True:
                data = await src.read(1024)
                if not data:
                    break
                await dst.write(data)

        stdout = process.stdout
        assert stdout is not None

        stderr = process.stderr
        assert stderr is not None

        stdin = process.stdin
        assert stdin is not None

        pipe_stdout = create_task(_pipe(stdout, out))
        pipe_stderr = create_task(_pipe(stderr, err))

        async def _wait() -> int:
            return_code = await process.wait()
            await pipe_stdout
            await pipe_stderr
            return return_code

        return _ProcessStream(stdin), err, _wait()


class _ProcessStream(Stream):
    def __init__(self, writer: StreamWriter) -> None:
        self._writer = writer

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()
