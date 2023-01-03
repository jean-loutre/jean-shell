from asyncio import Event, Queue, Task, create_task, wait_for
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Coroutine

from jshell.command import Process
from jshell.shells import Shell
from jshell.streams import PipeWriter


class _Stdin:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._data_available = Event()
        self._closed = Event()

    async def write(self, data: bytes) -> None:
        self._buffer = self._buffer + data
        self._data_available.set()

    async def read(self, n: int = -1) -> bytes:
        if n == -1:
            await self._closed.wait()
        else:
            while len(self._buffer) < n:
                self._data_available.clear()
                await self._data_available.wait()

        if n == -1:
            data = self._buffer
            self._buffer = bytearray()
        else:
            data = self._buffer[0:n]
            self._buffer = self._buffer[n:]

        if len(self._buffer) == 0:
            self._data_available.clear()

        return data

    async def close(self) -> None:
        self._closed.set()


class _Process:
    def __init__(self) -> None:
        self.stdin = _Stdin()
        self.stdout: PipeWriter | None = None
        self.terminated = Event()
        self.waiting_exit = Event()
        self.return_code: int = 0

    async def start(self, stdout: PipeWriter) -> PipeWriter:
        self.stdout = stdout
        return self.stdin

    async def wait(self) -> int:
        self.waiting_exit.set()
        await self.stdin.close()
        await self.terminated.wait()
        return self.return_code


class ProcessHandle:
    def __init__(self, process: _Process, command: str, env: dict[str, str]):
        self._process = process
        self._command = command
        self._env = env

    @property
    def command(self) -> str:
        return self._command

    @property
    def env(self) -> dict[str, str]:
        return self._env

    async def read_stdin(self, n: int = -1) -> bytes:
        return await self._process.stdin.read(n)

    async def write_stdout(self, data: bytes) -> None:
        stdout = self._process.stdout
        assert stdout is not None
        await stdout.write(data)

    async def exit(self, return_code: int) -> None:
        await self._process.waiting_exit.wait()
        self._process.return_code = return_code

        stdout = self._process.stdout
        assert stdout is not None
        await stdout.close()

        self._process.terminated.set()


class MockShell(Shell):
    def __init__(self, processes: Queue[ProcessHandle]) -> None:
        super().__init__()
        self._processes = processes

    async def next(self) -> ProcessHandle:
        return await self._processes.get()

    def _create_process(self, command: str, env: dict[str, str]) -> Process:
        process = _Process()
        self._processes.put_nowait(ProcessHandle(process, command, env))
        return process


@asynccontextmanager
async def mock_shell(
    handler: Callable[[Shell], Coroutine[Any, Any, None]]
) -> AsyncIterator[MockShell]:
    processes: Queue[ProcessHandle] = Queue()
    shell = MockShell(processes)
    task: Task[None] = create_task(handler(shell))
    yield shell
    await wait_for(task, 1.0)
    assert processes.empty()
