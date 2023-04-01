"""Configuration loading"""
from importlib import import_module
from typing import Callable, cast

from jshell.core.inventory import Inventory

ConfigLoader = Callable[[str], Inventory]


class ConfigError(Exception):
    """Raised when loading configuration fails."""


def load(source: str) -> Inventory:
    """Loads an object from a variety of source.

    :param source:      The config source, as a python object qualified name.
    :return:            The loaded object.
    """

    module_name, separator, qualified_name = source.partition(":")
    result = import_module(module_name)
    if separator:
        for attribute in qualified_name.split("."):
            result = getattr(result, attribute)
        return cast(Inventory, result)

    return cast(Inventory, result.INVENTORY)
