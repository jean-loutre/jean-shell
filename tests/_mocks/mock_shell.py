from asyncio import FIRST_COMPLETED, Event, Queue, create_task, wait
from types import TracebackType
from typing import Any, Callable, Coroutine, cast

from jshell.core.pipe import PipeWriter
from jshell.core.shell import Shell, ShellProcess


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


class MockProcess:
    def __init__(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ):
        self._command = command
        self._env = env
        self._return_code: int = 0
        self._stdin = _Stdin()
        self._stdout: PipeWriter = out
        self._stderr: PipeWriter = err
        self._terminated = Event()
        self._waiting_exit = Event()

    @property
    def command(self) -> str:
        return self._command

    @property
    def env(self) -> dict[str, str]:
        return self._env

    @property
    def stdin(self) -> _Stdin:
        return self._stdin

    async def read_stdin(self, n: int = -1) -> bytes:
        return await self._stdin.read(n)

    async def write_stdout(self, data: bytes) -> None:
        await self._stdout.write(data)

    async def write_stderr(self, data: bytes) -> None:
        await self._stderr.write(data)

    async def wait(self, _: Any) -> int:
        self._waiting_exit.set()
        await self._stdin.close()
        await self._terminated.wait()
        return self._return_code

    async def exit(self, return_code: int) -> None:
        await self._waiting_exit.wait()
        self._return_code = return_code

        await self._stdout.close()
        await self._stderr.close()

        self._terminated.set()


class MockShell(Shell):
    def __init__(
        self, consumer: Callable[[Shell], Coroutine[None, None, None]]
    ) -> None:
        super().__init__()
        self._processes: Queue[MockProcess] = Queue()
        self._consumer = create_task(consumer(self))

    async def __aenter__(self) -> "MockShell":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self._consumer
        assert self._processes.empty()

    async def next(self) -> MockProcess:
        next_process_task = create_task(self._processes.get())
        tasks = [next_process_task, self._consumer]
        done, _ = await wait(tasks, return_when=FIRST_COMPLETED)
        while len(done) > 0:
            task_done = done.pop()
            if task_done.exception():
                raise cast(Exception, task_done.exception())
            if task_done == next_process_task:
                return cast(MockProcess, task_done.result())

        assert False, "MockShell consumer ended while waiting for it to launch process"

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        process = MockProcess(out, err, command, env)
        self._processes.put_nowait(process)
        return process.stdin, err, process.wait
