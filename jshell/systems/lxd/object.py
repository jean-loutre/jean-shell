"""LXD Configuration and shell helper."""
from asyncio import gather
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Iterable,
    Type,
    TypeVar,
    cast,
)

from jshell.core.pipe import Pipe, dump_json, parse_json
from jshell.core.shell import ShellPipe

Config = dict[str, Any]

Self = TypeVar("Self", bound="Object")

LxcCommand = Callable[[str], ShellPipe]


class Object:
    """Base class for LXD objects (project, instances, networks...)"""

    subcommand: ClassVar[str]
    ignore_keys: ClassVar[tuple[str]]

    def __init__(self, name: str, **kwargs: Any) -> None:
        self._config = dict(name=name, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return self._config.get(name, None)

    async def create(self, lxc: LxcCommand) -> None:
        await lxc(f"{self.subcommand} create {self.name}")

    async def save(self, lxc: LxcCommand) -> None:
        await (self._dump() | lxc(f"{self.subcommand} edit {self.name}"))

    async def delete(self, lxc: LxcCommand) -> None:
        await lxc(f"{self.subcommand} delete {self.name}")

    @classmethod
    @asynccontextmanager
    async def synchronize(
        cls: Type[Self], lxc: LxcCommand, objects: Iterable[Self]
    ) -> AsyncGenerator[None, None]:
        local_objects = {it.name: it for it in objects}
        remote = await cls._load_remotes(lxc)

        dangling = remote.keys() - local_objects.keys()
        await gather(*(remote[name].delete(lxc) for name in dangling))

        yield

        new = local_objects.keys() - remote.keys()

        # Update remote configuration with newly created objects
        # TODO: update only modified objects, by comparing remote and local_objects config
        if new:
            await gather(*(local_objects[name].create(lxc) for name in new))
            remote = await cls._load_remotes(lxc)

        updated = [cls(**(remote[it.name]._config | it._config)) for it in objects]
        await gather(*(it.save(lxc) for it in updated))

    @classmethod
    async def _load_remotes(cls: Type[Self], lxc: LxcCommand) -> dict[str, Self]:
        return {
            it["name"]: cls(**it)
            for it in cast(
                list[dict[str, Any]],
                await (lxc(f"{cls.subcommand} list -f json") | parse_json()),
            )
        }

    def _dump(self) -> Pipe[Any, Any]:
        ignore_keys = self.ignore_keys or []
        return dump_json(
            {
                key: value
                for key, value in self._config.items()
                if key not in ignore_keys
            }
        )
