"""Jean-Shell CLI wrapper."""
from asyncio import run
from logging import INFO, basicConfig, getLogger

from click import argument, command, option

from jshell.core.config import load
from jshell.core.shell import ShellProcessException

_LOG = getLogger(__name__)


@command()
@argument("inventory")
@argument("operation")
@option("-i", "--include", multiple=True, type=str)
def main(inventory: str, operation: str, include: list[str]) -> None:
    """Jean-Shell CLI entry point point."""
    basicConfig(level=INFO)
    try:
        return run(load(inventory).run(operation, include=include))
    except ShellProcessException as ex:
        _LOG.error("%s", ex)
