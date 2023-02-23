"""Jean-Shell CLI wrapper."""
from asyncio import run
from logging import INFO, basicConfig, getLogger

from click import argument, command

from jshell.core.config import load
from jshell.core.shell import ShellProcessException

_LOG = getLogger(__name__)


@command()
@argument("inventory")
@argument("operation")
def main(inventory: str, operation: str) -> None:
    """Jean-Shell CLI entry point point."""
    basicConfig(level=INFO)
    try:
        return run(load(inventory).run(operation))
    except ShellProcessException as ex:
        _LOG.error("%s", ex)
