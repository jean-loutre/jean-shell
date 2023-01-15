"""A shell is the entry point to run commands."""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from logging import Logger
from typing import Any, Iterator

from jshell.core.pipe import Pipe, PipeWriter, Process

ShellProcess = Process[Any, int]
ShellPipe = Pipe[Any, int]


class Shell(ABC):
    """An shell usable to run commands on hosts."""

    def __init__(self, logger: Logger | None = None) -> None:
        self._logger = logger
        self._env: dict[str, str] = {}

    def __call__(self, command: str) -> ShellPipe:
        """Return a `Command` ready to be run.

        :param command: The command to run in this shell.

        :return: A `Command` instance that can be awaited to actually execute
                 the given command.
        """

        async def _start(out: PipeWriter, err: PipeWriter) -> ShellProcess:
            return await self._start_process(out, err, command, env=self._env)

        return Pipe(None, start=_start, logger=self._logger)

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

    @abstractmethod
    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> Process[Any, int]:
        """Create a new process using this shell.

        :param command: The command to run in this shell.

        :return: A `Process` instance usable as a Command parameter.
        """
