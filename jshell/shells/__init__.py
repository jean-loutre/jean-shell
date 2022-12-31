"""A shell is the entry point to run commands."""
from abc import ABC, abstractmethod
from typing import Callable

from jshell.command import Command, Process

ProcessFactory = Callable[[str], Process]


class Shell(ABC):
    """An shell usable to run commands on hosts."""

    def run(self, command: str) -> Command:
        """Return a `Command` ready to be run.

        :param command: The command to run in this shell.

        :return: A `Command` instance that can be awaited to actually execute
                 the given command.
        """
        process = self._create_process(command)
        return Command(process)

    @abstractmethod
    def _create_process(self, command: str) -> Process:
        """Create a new process using this shell.

        :param command: The command to run in this shell.

        :return: A `Process` instance usable as a Command parameter.
        """
