from asyncio import Event, Queue, Task, create_task, gather
from re import Pattern
from types import TracebackType
from typing import Any, AsyncIterator, Callable, Coroutine, Iterable

from jtoto.shell import Process, Shell, Stderr, Stdout
from jtoto.stream import Stream


class MockStdin(Stream):
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._data_available = Event()
        self._closed = Event()

    async def write(self, data: bytes) -> None:
        self._buffer.extend(data)
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


MockProcess = Callable[
    [str, Stdout, Stderr, MockStdin, dict[str, str]], Coroutine[Any, None, int]
]


async def _write_stream(content: bytes, stream: Stream) -> None:
    await stream.write(content)
    await stream.close()


def check_process(
    expected_command: str | Pattern[str] = ".*",
    stdout: str | bytes = "",
    stderr: str | bytes = "",
    expected_stdin: str | bytes | Callable[[bytes], None] = "",
    return_code: int = 0,
) -> MockProcess:
    def _encode(value: str | bytes) -> bytes:
        if isinstance(value, str):
            return value.encode("utf-8")
        return value

    encoded_stdout = _encode(stdout)
    encoded_stderr = _encode(stderr)
    if isinstance(expected_stdin, (str, bytes)):
        expected_stdin = _encode(expected_stdin)

    async def _run(
        command: str,
        out: Stdout,
        err: Stderr,
        stdin: MockStdin,
        env: dict[str, str],
    ) -> int:
        if isinstance(expected_command, str):
            assert (
                command == expected_command
            ), f"Unexpected command : {command}, expected {expected_command}"
        else:
            assert expected_command.match(
                command
            ), f"Unexpected command : {command}, expected {expected_command}"

        async def _check_stdin() -> None:
            stdin_content = await stdin.read()
            if callable(expected_stdin):
                expected_stdin(stdin_content)
            else:
                assert (
                    stdin_content == expected_stdin
                ), f"Unexpected stdin: {stdin_content!r}, expected {expected_stdin!r}"

        def _tasks() -> Iterable[Coroutine[Any, Any, None]]:
            if expected_stdin:
                yield _check_stdin()
            if encoded_stdout and out:
                yield _write_stream(encoded_stdout, out)
            if encoded_stderr and err:
                yield _write_stream(encoded_stderr, err)

        await gather(*_tasks())

        return return_code

    return _run


class MockShell(Shell):
    def __init__(self, system_mock: AsyncIterator[MockProcess]) -> None:
        super().__init__()
        self._processes: Queue[MockProcess] = Queue()

        async def _run() -> None:
            async for process in system_mock:
                self._processes.put_nowait(process)

        self._system_mock = create_task(_run())

    async def __aenter__(self) -> "MockShell":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self._system_mock
            assert self._processes.empty()

    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        if self._system_mock.done():
            exception = self._system_mock.exception()
            if exception:
                raise exception

        process = await self._processes.get()  # TODO: exception on timeout
        stdin = MockStdin()

        async def _run() -> int:
            process_task: Task[int] = create_task(
                process(command, out, err, stdin, env)
            )
            return await process_task

        return stdin, err, create_task(_run())
