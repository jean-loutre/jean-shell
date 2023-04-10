"""Config unit tests."""
from jshell.core.config import load
from jshell.core.inventory import Inventory


def test_load_from_module() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("tests._fixtures.inventories.inventory_module")
    assert isinstance(inventory, Inventory)


def test_load_from_object() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("tests._fixtures.inventories:INVENTORY_OBJECT")
    assert isinstance(inventory, Inventory)
