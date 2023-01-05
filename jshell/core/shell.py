"""A shell is the entry point to run commands."""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from logging import Logger
from typing import Callable, Iterator

from jshell.core.command import Command, Process

ProcessFactory = Callable[[str], Process]


class Shell(ABC):
    """An shell usable to run commands on hosts."""

    def __init__(self, log: Logger | None = None) -> None:
        self._log = log
        self._env: dict[str, str] = {}

    def __call__(self, command: str) -> Command:
        """Return a `Command` ready to be run.

        :param command: The command to run in this shell.

        :return: A `Command` instance that can be awaited to actually execute
                 the given command.
        """
        process = self._create_process(command, env=self._env)
        return Command(process, log=self._log)

    @contextmanager
    def env(self, **kwargs: str) -> Iterator[None]:
        old_env = self._env.copy()
        for key, value in dict(**kwargs).items():
            self._env[key] = value
        yield
        self._env = old_env

    @abstractmethod
    def _create_process(self, command: str, env: dict[str, str]) -> Process:
        """Create a new process using this shell.

        :param command: The command to run in this shell.

        :return: A `Process` instance usable as a Command parameter.
        """
