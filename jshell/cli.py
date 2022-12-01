"""Jean-Shell CLI wrapper."""
from asyncio import run

from click import argument, command

from jshell.config import load
from jshell.inventory import Inventory


@command()
@argument("inventory")
@argument("operation")
def main(inventory: str, operation: str) -> None:
    """Jean-Shell CLI entry point point."""
    return run(load(inventory, Inventory).run(operation))
