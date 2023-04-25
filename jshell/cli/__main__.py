"""Jean-Shell CLI wrapper."""
from asyncio import run
from logging import INFO, basicConfig, getLogger
from typing import Any

from click import argument, command

from jshell.cli import jshell_run_arguments
from jshell.core.config import load
from jshell.core.shell import ShellProcessException

_LOG = getLogger(__name__)


@command()
@argument("inventory")
@jshell_run_arguments
def main(inventory: str, *args: Any, **kwargs: Any) -> None:
    """Jean-Shell CLI entry point point."""
    basicConfig(level=INFO)
    try:
        return run(load(inventory).run(*args, **kwargs))
    except ShellProcessException as ex:
        _LOG.error("%s", ex)
