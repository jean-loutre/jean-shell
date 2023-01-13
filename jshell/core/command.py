"""Base classe & utilities for Commands returned by shell."""
from asyncio import gather
from logging import Logger
from pathlib import Path
from typing import Generator, Protocol, Union

from jshell.core.pipe import (
    CombinedPipeWriter,
    FilePipeWriter,
    MemoryPipeWriter,
    PipeWriter,
)


class CommandResult:
    """Wrapper around a runt command.

    This class adds syntactic sugar to check for command result :
    ```
    command_result = await shell("echo 'Gilbert'")
    if command_result: # Evaluates to true if return code == 0
        ...

    # Get the command stdout, UTF-8 encoded
    stdout = str(command_result)
    ```
    """

    def __init__(self, return_code: int, stdout: bytes):
        """Initialize a CommandResult.

        :param return_code: The return code of the executed process.
        """
        self._return_code = return_code
        self._stdout = stdout

    @property
    def return_code(self) -> int:
        """Get the return code of the command that was run."""
        return self._return_code

    @property
    def stdout(self) -> bytes:
        """Get the return code of the command that was run."""
        return self._stdout

    def __bool__(self) -> bool:
        """Check for runt command exit status.

        :return: True if process exited with 0 return code.
        """
        return self._return_code == 0

    def __str__(self) -> str:
        """Return content of stdout decoded as UTF-8."""
        return self.stdout.decode("utf-8")


class Process(Protocol):
    """Interface to implement custom processes (ssh, local, ...).

    This interface is handled by the Command class to run, pipe, redirect
    output and input of processes and to return CommandResult object on
    completion.
    """

    async def start(self, stdout: PipeWriter) -> PipeWriter:
        """Start the process, plugin it's stdout to given PipeWriter.

        :param stdout: PipeWriter to use as stdout.
        """

    async def wait(self) -> int:
        """Wait for the process to finish. The process must've been started
        first by calling `start`.

        :return: The exit code of the process.
        """


OutputRedirect = Union[Path, PipeWriter]


class Command:
    """A sh-like command, with piping and file redirection support."""

    def __init__(self, process: Process, log: Logger | None = None):
        self._process = process
        self._pipe: "Command" | None = None
        self._output_redirects: list[OutputRedirect] = []
        self._stdout_capture: MemoryPipeWriter | None = None
        self._log = log

    def __await__(self) -> Generator[None, None, CommandResult]:
        return self._run().__await__()  # pylint: disable=no-member

    def __or__(self, right: Union["Command", OutputRedirect]) -> "Command":
        if isinstance(right, Command):
            assert right._pipe is None
            right._pipe = self
            return right

        self._output_redirects.append(right)
        return self

    async def _run(self) -> CommandResult:
        command: Command | None = self
        processes: list[Process] = []
        while command is not None:
            processes.append(command._process)  # pylint: disable=protected-access
            command = command._pipe  # pylint: disable=protected-access

        stdout: PipeWriter = await self._get_stdout()
        for process in processes:
            stdout = await process.start(stdout)
        return_codes = await gather(*[process.wait() for process in processes])

        return_code = next((code for code in return_codes if code != 0), 0)

        stdout_capture = b""
        if self._stdout_capture is not None:
            stdout_capture = self._stdout_capture.value

        return CommandResult(return_code, stdout_capture)

    async def _get_stdout(self) -> PipeWriter:
        redirects = list(self._output_redirects)

        if not redirects:
            assert self._stdout_capture is None
            self._stdout_capture = MemoryPipeWriter()
            redirects.append(self._stdout_capture)

        if len(redirects) == 1:
            return await self._get_output_redirect(redirects[0])

        return CombinedPipeWriter(
            *[await self._get_output_redirect(redirect) for redirect in redirects]
        )

    @staticmethod
    async def _get_output_redirect(redirect: OutputRedirect) -> PipeWriter:
        if isinstance(redirect, Path):
            return await FilePipeWriter.open(redirect)
        if isinstance(redirect, PipeWriter):
            return redirect

        raise AssertionError()


class _EchoProcess:
    def __init__(self, content: bytes = b""):
        self._content = content
        self._stdout: PipeWriter | None = None
        self._closed = False

    async def start(self, stdout: PipeWriter) -> PipeWriter:
        assert self._stdout is None
        self._stdout = stdout
        await stdout.write(self._content)
        return self

    async def wait(self) -> int:
        await self.close()
        return 0

    async def write(self, data: bytes) -> None:
        assert self._stdout is not None
        await self._stdout.write(data)

    async def close(self) -> None:
        """Saves the underlying BytesIO buffer, then closes it."""
        assert self._stdout is not None
        if not self._closed:
            self._closed = True
            await self._stdout.close()


def echo(content: bytes | str, encoding: str = "utf-8") -> Command:
    """Pipes content to another command.

    If something is piped into the returned command, it is forwarded to the command
    comming after echo.

    :param content: Content to pipe to the next command.
    :param encoding: If content is the string, the encoding to use to encode it.
    :return: A command instance piping the given content to the next.
    """

    if isinstance(content, str):
        content = content.encode(encoding)
    return Command(_EchoProcess(content))
