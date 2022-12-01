"""Configuration loading"""
from dataclasses import fields
from importlib import import_module
from importlib.metadata import entry_points
from typing import Any, Callable, Type, TypeVar, cast

ObjectType = TypeVar("ObjectType")

ConfigLoader = Callable[[str, Type[ObjectType]], ObjectType]


class ConfigError(Exception):
    """Raised when loading configuration fails."""


def load(url: str, cls: Type[ObjectType]) -> ObjectType:
    """Loads an object from a variety of source.

    :param source:      Config source.
    :param object_type: Type of the object to load.
    :return:            The loaded object.
    """
    [scheme, source] = url.split("://", 1)

    (entry_point,) = entry_points(group="jshell_config_loaders", name=scheme)
    loader = cast(ConfigLoader[ObjectType], entry_point.load())
    return loader(source, cls)


def py_loader(file_name: str, cls: Type[ObjectType]) -> ObjectType:
    """Load a python file."""

    with open(file_name, "rb") as file:
        content = file.read()

    code = compile(content, file_name, "exec")
    local: dict[str, Any] = {}
    exec(code, {}, local)  # pylint: disable=exec-used
    parameters = {
        field.name: local[field.name] for field in fields(cls) if field.name in local
    }
    return cls(**parameters)


def ref_loader(reference: str, cls: Type[ObjectType]) -> ObjectType:
    """Load config from a python ref (path.to.module:path.to.object)."""

    module_name, separator, qualified_name = reference.partition(":")
    result = import_module(module_name)
    if separator:
        for attribute in qualified_name.split("."):
            result = getattr(result, attribute)
        assert isinstance(result, cls)
        return result

    parameters = {
        field.name: getattr(result, field.name)
        for field in fields(cls)
        if hasattr(result, field.name)
    }
    return cls(**parameters)
