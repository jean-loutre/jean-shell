"""Configuration loading"""
from importlib import import_module
from importlib.metadata import entry_points
from typing import Any, Callable, cast

from jshell.core.inventory import Inventory

ConfigLoader = Callable[[str], Inventory]


class ConfigError(Exception):
    """Raised when loading configuration fails."""


def load(url: str) -> Inventory:
    """Loads an object from a variety of source.

    :param source:      Config source.
    :param object_type: Type of the object to load.
    :return:            The loaded object.
    """
    [scheme, source] = url.split("://", 1)

    (entry_point,) = entry_points(group="jshell_config_loaders", name=scheme)
    loader = cast(ConfigLoader, entry_point.load())
    return loader(source)


def py_loader(file_name: str) -> Inventory:
    """Load a python file."""

    with open(file_name, "rb") as file:
        content = file.read()

    code = compile(content, file_name, "exec")
    local: dict[str, Any] = {}
    exec(code, {}, local)  # pylint: disable=exec-used
    return cast(Inventory, local["INVENTORY"])


def ref_loader(reference: str) -> Inventory:
    """Load config from a python ref (path.to.module:path.to.object)."""

    module_name, separator, qualified_name = reference.partition(":")
    result = import_module(module_name)
    if separator:
        for attribute in qualified_name.split("."):
            result = getattr(result, attribute)
        return cast(Inventory, result)

    return cast(Inventory, result.INVENTORY)
