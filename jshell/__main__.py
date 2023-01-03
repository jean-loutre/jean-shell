"""Jean-Shell CLI wrapper."""
from asyncio import run
from logging import INFO, basicConfig

from click import argument, command

from jshell.core.config import load
from jshell.core.inventory import Inventory


@command()
@argument("inventory")
@argument("operation")
def main(inventory: str, operation: str) -> None:
    """Jean-Shell CLI entry point point."""
    basicConfig(level=INFO)
    return run(load(inventory, Inventory).run(operation))
