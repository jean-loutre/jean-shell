"""Base classe & utilities for Commands returned by shell."""
from pathlib import Path
from typing import Generator, Protocol, Union

from jshell.streams import (
    CompoundPipeWriter,
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

    def __init__(self, process: Process):
        self._process = process
        self._pipe: "Command" | None = None
        self._output_redirects: list[OutputRedirect] = []
        self._stdout_capture: MemoryPipeWriter | None = None

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
        stdout: PipeWriter = await self._get_stdout()
        command: Command | None = self
        while command is not None:
            stdout = await command._process.start(  # pylint: disable=protected-access
                stdout
            )
            command = command._pipe  # pylint: disable=protected-access

        return_code = await self._process.wait()

        stdout_capture = b""
        if self._stdout_capture is not None:
            stdout_capture = self._stdout_capture.value

        return CommandResult(return_code, stdout_capture)

    async def _get_stdout(self) -> PipeWriter:
        redirects = self._output_redirects
        if not redirects:
            assert self._stdout_capture is None
            self._stdout_capture = MemoryPipeWriter()
            return self._stdout_capture

        if len(redirects) == 1:
            return await self._get_output_redirect(redirects[0])

        return CompoundPipeWriter(
            *[await self._get_output_redirect(redirect) for redirect in redirects]
        )

    @staticmethod
    async def _get_output_redirect(redirect: OutputRedirect) -> PipeWriter:
        if isinstance(redirect, Path):
            return await FilePipeWriter.open(redirect)
        if isinstance(redirect, PipeWriter):
            return redirect

        raise AssertionError()
