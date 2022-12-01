"""A shell is the entry point to run commands."""
from typing import Callable

from jshell.command import Command, Process

ProcessFactory = Callable[[str], Process]


class Shell:
    """An shell usable to run commands on hosts."""

    def __init__(self, process_factory: ProcessFactory):
        """Initialize a `Shell` instance.

        :param process_factory: Callable that must return a concrete `Process`
                                instance for the given command each time it's
                                called. The process must not be started yet
                                when returned.
        """
        self._process_factory = process_factory

    def run(self, command: str) -> Command:
        """Return a `Command` ready to be run.

        :param command: The command to run in this shell.

        :return: A `Command` instance that can be awaited to actually execute
                 the given command.
        """
        process = self._process_factory(command)
        return Command(process)
