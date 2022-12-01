"""Config unit tests."""
from pathlib import Path

from jshell.config import load
from jshell.inventory import Inventory


def test_load_from_python(datadir: Path) -> None:
    """load_from_python should load a class from a python file."""
    inventory = load(f"py://{str(datadir / 'inventory.py')}", Inventory)
    assert list(inventory.targets)[0].name == "peter"


def test_load_from_module() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("ref://tests.fixtures.inventories.inventory_module", Inventory)
    assert list(inventory.targets)[0].name == "peter"


def test_load_from_object() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("ref://tests.fixtures.inventories:INVENTORY_OBJECT", Inventory)
    assert list(inventory.targets)[0].name == "peter"
