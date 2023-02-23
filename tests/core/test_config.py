"""Config unit tests."""
from pathlib import Path

from jshell.core.config import load


def test_load_from_python(datadir: Path) -> None:
    """load_from_python should load a class from a python file."""
    inventory = load(f"py://{str(datadir / 'inventory.py')}")
    assert list(inventory.targets)[0].name == "peter"


def test_load_from_module() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("ref://tests._fixtures.inventories.inventory_module")
    assert list(inventory.targets)[0].name == "peter"


def test_load_from_object() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("ref://tests._fixtures.inventories:INVENTORY_OBJECT")
    assert list(inventory.targets)[0].name == "peter"
