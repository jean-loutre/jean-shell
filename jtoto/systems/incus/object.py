from typing import Any, ClassVar, TypeVar

from jtoto.shell import Command, echo
from json import dumps
from jtoto.systems.incus.cli import IncusCli

Config = dict[str, Any]

Self = TypeVar("Self", bound="Object")


class Object:
    """Base class for Incus objects (project, instances, networks...)"""

    subcommand: ClassVar[str]
    config_subcommand: ClassVar[str]
    ignore_keys: ClassVar[tuple[str]]

    def __init__(self, cli: IncusCli, name: str, **kwargs: Any) -> None:
        self._cli = cli
        self._full_config: dict[str, Any] = {"name": name}
        self._full_config.update(**kwargs)
        self._remote_full_config = dict(self._full_config)

    def __getattr__(self, name: str) -> Any:
        return self._full_config.get(name, None)

    def __setattr__(self, name: str, value: Any) -> Any:
        if name not in ["_cli", "_full_config", "_remote_full_config"]:
            self._full_config[name] = value
        else:
            object.__setattr__(self, name, value)

    async def save(self, **config: Any) -> None:
        new_full_config = dict(self._full_config) | dict(config)
        if new_full_config == self._remote_full_config:
            return

        self._full_config = new_full_config

        await (self._dump() | self._cli(f"{self.config_subcommand} edit {self.name}"))
        self._remote_full_config = dict(self._full_config)

    async def load(self) -> None:
        # backup name as it's not returned by show commands, only by list
        name = self.name
        configs = await self._cli.parse_stdout(
            f"{self.subcommand} list {self.name} --format json"
        )
        assert len(configs) == 1
        self._full_config = configs[0]

        self._full_config["name"] = name
        self._remote_full_config = dict(self._full_config)

    def _dump(self) -> Command:
        ignore_keys = self.ignore_keys or []
        return echo(
            dumps(
                {
                    key: value
                    for key, value in self._full_config.items()
                    if key not in ignore_keys
                }
            )
        )
