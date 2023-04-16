from logging import Logger
from typing import Any, AsyncIterator, Iterable, Type, TypeVar, cast

from jshell.core.pipe import dump_yaml, parse_yaml
from jshell.core.resource import Resource, resource
from jshell.core.shell import Shell
from jshell.systems.lxd.cli import LxcCli
from jshell.systems.lxd.instance import Instance
from jshell.systems.lxd.network import Network
from jshell.systems.lxd.object import Object
from jshell.systems.lxd.profile import Profile
from jshell.systems.lxd.project import Project
from jshell.systems.lxd.storage import Storage

TObject = TypeVar("TObject", bound="Object")


@resource
async def lxd_node(
    sh: Resource[Shell],
    lxc_path: str = "lxc",
    project: str | None = None,
    logger: Logger | None = None,
) -> AsyncIterator["Node"]:
    async with sh as loaded_sh:
        node = Node(loaded_sh, lxc_path, project, logger)
        if project is not None:
            await node.ensure_project(project)
        yield node


class Node:
    """LXDConfiguration settings."""

    def __init__(
        self,
        sh: Shell,
        lxc_path: str,
        project: str | None,
        logger: Logger | None = None,
    ) -> None:
        self._objects: dict[Type[Object], list[Object]] = {}
        self._cli = LxcCli(sh, lxc_path, project=project, logger=logger)

    async def ensure_instance(self, name: str, image: str, **config: Any) -> Instance:
        instance = await self.get_object(Instance, name)
        config_dict = dict(**config)
        if instance is None:
            await (dump_yaml(config_dict) | self._cli(f"init {image} {name}"))
            instances = await self._get_objects(Instance)
            instance = Instance(self._cli, name)
            await instance.load()
            instances.append(instance)
        elif config_dict:
            await instance.save(**config_dict)

        return instance

    async def ensure_network(self, name: str, type: str | None = None) -> Network:
        network = await self.get_object(Network, name)
        if network is None:
            if type:
                await self._cli(f"network create {name} --type {type}")
            else:
                await self._cli(f"network create {name}")
            networks = await self._get_objects(Network)
            network = Network(self._cli, name, type=type)
            await network.load()
            networks.append(network)

        return network

    async def ensure_profile(self, name: str) -> Profile:
        profile = await self.get_object(Profile, name)
        if profile is None:
            await self._cli(f"profile create {name}")
            profiles = await self._get_objects(Profile)
            profile = Profile(self._cli, name)
            await profile.load()
            profiles.append(profile)

        return profile

    async def ensure_project(self, name: str) -> Project:
        project = await self.get_object(Project, name)
        if project is None:
            await self._cli(f"project create {name}")
            projects = await self._get_objects(Project)
            project = Project(self._cli, name)
            await project.load()
            projects.append(project)

        return project

    async def ensure_storage(self, name: str, driver: str) -> Storage:
        storage = await self.get_object(Storage, name)
        if storage is None:
            await self._cli(f"storage create {name} {driver}")
            storages = await self._get_objects(Storage)
            storage = Storage(self._cli, name)
            await storage.load()
            storages.append(storage)

        return storage

    async def get_objects(self, cls: Type[TObject]) -> Iterable[TObject]:
        return await self._get_objects(cls)

    async def get_object(self, object_type: Type[TObject], name: str) -> TObject | None:
        for it in await self.get_objects(object_type):
            if it.name == name:
                return it

        return None

    async def delete(self, obj: TObject) -> None:
        objects = await self._get_objects(obj.__class__)
        await self._cli(f"{obj.subcommand} delete {obj.name}")
        objects.remove(obj)

    async def _get_objects(self, cls: Type[TObject]) -> list[TObject]:
        object_list = cast(list[TObject] | None, self._objects.get(cls, None))
        if object_list is None:
            object_list = [
                cls(self._cli, **it)  # name argument is retrieved when calling list
                for it in cast(
                    list[dict[str, Any]],
                    await (
                        self._cli(f"{cls.subcommand} list --format yaml") | parse_yaml()
                    ),
                )
            ]
            self._objects[cls] = cast(list[Object], object_list)
        return object_list
