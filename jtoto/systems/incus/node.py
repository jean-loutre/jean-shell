from logging import Logger
from typing import Any, Type, TypeVar, cast, Awaitable, Callable

from json import dumps
from jtoto.shell import Shell, echo
from jtoto.task import task
from jtoto.systems.incus.cli import IncusCli
from jtoto.systems.incus.instance import Instance
from jtoto.systems.incus.network import Network
from jtoto.systems.incus.object import Object
from jtoto.systems.incus.profile import Profile
from jtoto.systems.incus.project import Project
from jtoto.systems.incus.storage import Storage

TObject = TypeVar("TObject", bound="Object")


@task()
async def incus_node(
    sh: Shell,
    incus_path: str = "incus",
    project: str | None = None,
    logger: Logger | None = None,
) -> "Node":
    node = Node(sh, incus_path, project, logger)
    if project is not None:
        await node.init_project(project)
    return node


class Node:
    def __init__(
        self,
        sh: Shell,
        incus_path: str,
        project: str | None,
        logger: Logger | None = None,
    ) -> None:
        self._objects: dict[Type[Object], list[Object]] = {}
        self._cli = IncusCli(sh, incus_path, project=project, logger=logger)

    async def init_instance(self, name: str, image: str, **config: Any) -> Instance:
        async def _create() -> None:
            await (echo(dumps(config)) | self._cli(f"init {image} {name}"))

        return await self._init_object(name, Instance, _create, **config)

    async def init_network(
        self, name: str, type: str | None = None, **config: Any
    ) -> Network:
        async def _create() -> None:
            if type:
                await self._cli(f"network create {name} --type {type}")
            else:
                await self._cli(f"network create {name}")

        return await self._init_object(name, Network, _create, **config)

    async def init_profile(self, name: str, **config: Any) -> Profile:
        async def _create() -> None:
            await self._cli(f"profile create {name}")

        return await self._init_object(name, Profile, _create, **config)

    async def init_project(self, name: str, **config: Any) -> Project:
        async def _create() -> None:
            await self._cli(f"project create {name}")

        return await self._init_object(name, Project, _create, **config)

    async def init_storage(self, name: str, driver: str, **config: Any) -> Storage:
        async def _create() -> None:
            await self._cli(f"storage create {name} {driver}")

        return await self._init_object(name, Storage, _create, **config)

    async def _init_object(
        self,
        name: str,
        object_type: Type[TObject],
        create_callback: Callable[[], Awaitable[None]],
        **config: Any,
    ) -> TObject:
        for it in await self._get_objects(object_type):
            if it.name == name:
                await it.save(**config)
                return it

        await create_callback()

        for it in await self._get_objects(object_type, refresh=True):
            if it.name == name:
                await it.save(**config)
                return it

        assert False, "Creation of object failed, but without raising any error"

    async def _get_objects(
        self, cls: Type[TObject], refresh: bool = False
    ) -> list[TObject]:
        if refresh and cls in self._objects:
            del self._objects[cls]
        object_list = cast(list[TObject] | None, self._objects.get(cls, None))
        if object_list is None:
            object_list = [
                cls(self._cli, **it)  # name argument is retrieved when calling list
                for it in cast(
                    list[dict[str, Any]],
                    await self._cli.parse_stdout(
                        f"{cls.subcommand} list --format json"
                    ),
                )
            ]
            self._objects[cls] = cast(list[Object], object_list)
        return object_list
