"""A shell is the entry point to run commands."""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from logging import Logger
from typing import Any, Iterator

from jshell.core.pipe import (
    Pipe,
    PipeWriter,
    Process,
    TailPipeWriter,
    combine_pipes,
    pipe,
)

ShellProcess = Process[Any, int]
ShellPipe = Pipe[Any, int]


class ShellProcessException(Exception):
    def __init__(self, command: str, return_code: int, stderr_tail: str) -> None:
        super().__init__(
            f"{command} returned code {return_code}. Last stderr output:\n{stderr_tail}"
        )
        self.command = command
        self.return_code = return_code
        self.stderr_tail = stderr_tail


@pipe
async def _raise_on_error(
    out: PipeWriter, err: PipeWriter, command: str
) -> ShellProcess:
    stderr_tail = TailPipeWriter()

    async def _wait(result: int) -> int:
        if result != 0:
            raise ShellProcessException(command, result, "\n".join(stderr_tail.tail))
        return result

    return out, combine_pipes(err, stderr_tail), _wait


class Shell(ABC):
    """An shell usable to run commands on hosts."""

    def __init__(
        self, logger: Logger | None = None, raise_on_error: bool = True
    ) -> None:
        self._logger = logger
        self._env: dict[str, str] = {}
        self._raise_on_error = raise_on_error

    def __call__(self, command: str, raise_on_error: bool | None = None) -> ShellPipe:
        """Return a `Command` ready to be run.

        :param command: The command to run in this shell.

        :return: A `Command` instance that can be awaited to actually execute
                 the given command.
        """

        async def _start(out: PipeWriter, err: PipeWriter) -> ShellProcess:
            return await self._start_process(out, err, command, env=self._env)

        pipe: ShellPipe = Pipe(None, start=_start, logger=self._logger)

        if (raise_on_error is None and self._raise_on_error) or raise_on_error:
            pipe = pipe | _raise_on_error(command)

        return pipe

    @contextmanager
    def env(self, **kwargs: str) -> Iterator[None]:
        old_env = self._env.copy()
        for key, value in dict(**kwargs).items():
            self._env[key] = value
        yield
        self._env = old_env

    @contextmanager
    def log(self, logger: Logger | None) -> Iterator[None]:
        old_logger = self._logger
        self._logger = logger
        yield
        self._logger = old_logger

    @contextmanager
    def raise_on_error(self, raise_on_error: bool) -> Iterator[None]:
        old_value = self._raise_on_error
        self._raise_on_error = raise_on_error
        yield
        self._raise_on_error = old_value

    @abstractmethod
    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> Process[Any, int]:
        """Create a new process using this shell.

        :param command: The command to run in this shell.

        :return: A `Process` instance usable as a Command parameter.
        """
