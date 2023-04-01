"""Config unit tests."""
from jshell.core.config import load


def test_load_from_module() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("tests._fixtures.inventories.inventory_module")
    assert list(inventory.targets)[0].name == "peter"


def test_load_from_object() -> None:
    """load_from_python should load a class from a python file."""
    inventory = load("tests._fixtures.inventories:INVENTORY_OBJECT")
    assert list(inventory.targets)[0].name == "peter"
