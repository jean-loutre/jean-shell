"""LXD Configuration and shell helper."""
from typing import Any, ClassVar, TypeVar

from jshell.core.pipe import Pipe, dump_yaml, parse_yaml
from jshell.systems.lxd.cli import LxcCli

Config = dict[str, Any]

Self = TypeVar("Self", bound="Object")


class Object:
    """Base class for LXD objects (project, instances, networks...)"""

    subcommand: ClassVar[str]
    ignore_keys: ClassVar[tuple[str]]

    def __init__(self, cli: LxcCli, name: str, **kwargs: Any) -> None:
        self._cli = cli
        self._config = {"name": name}
        self._config.update(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return self._config.get(name, None)

    async def save(self, **override: Any) -> None:
        self._config.update(**override)
        await (self._dump() | self._cli(f"{self.subcommand} edit {self.name}"))

    async def load(self) -> None:
        # backup name as it's not returned by show commands, only by list
        name = self.name
        self._config = await (
            self._cli(f"{self.subcommand} show {self.name}") | parse_yaml()
        )
        self._config["name"] = name

    def _dump(self) -> Pipe[Any, Any]:
        ignore_keys = self.ignore_keys or []
        return dump_yaml(
            {
                key: value
                for key, value in self._config.items()
                if key not in ignore_keys
            }
        )
