from json import dumps, loads
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol, TypeVar

from jtoto.systems.incus import Instance, Network, Node, Profile, Project, Storage, incus_node
from jtoto.systems.incus.object import Object
from jtoto.testing import MockProcess, MockShell, check_process


async def test_load_with_project() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("incus --project peter project list --format json", stdout="[]")
        yield check_process("incus --project peter project create peter")
        yield check_process(
            "incus --project peter project list --format json",
            stdout=dumps([{"name": "peter"}]),
        )

    sh = MockShell(_mock_cli())
    await incus_node(sh, project="peter")


T = TypeVar("T", bound=Object)


class CreateCallback(Protocol):
    def __call__(self, node: Node, name: str, **config: Any) -> Awaitable[Object]:
        ...


def _check_json_stdin(expected_object: Any) -> Callable[[bytes], None]:
    def _check(content: bytes) -> None:
        assert loads(content.decode("utf-8")) == expected_object

    return _check


async def _test_init_object(
    type_: type[Object],
    create: CreateCallback,
    expected_create_command: str,
) -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            f"incus {type_.subcommand} list --format json",
            stdout=dumps([{"name": "peter", "description": "description"}]),
        )
        yield check_process(expected_create_command % "steven")
        yield check_process(
            f"incus {type_.subcommand} list --format json",
            stdout=dumps(
                [
                    {"name": "peter", "description": "description"},
                    {"name": "steven", "description": "description"},
                ]
            ),
        )
        yield check_process(
            f"incus {type_.config_subcommand} edit steven",
            expected_stdin=_check_json_stdin(
                {"description": "description", "name": "steven", "power": "10KW"}
            ),
        )

    node = await incus_node(MockShell(_mock_cli()))
    obj = await create(node, "peter")
    assert obj.name == "peter"
    assert obj.description == "description"

    obj = await create(node, "steven")
    assert obj.name == "steven"
    assert obj.description == "description"

    # Shouldn't call anything, as everything is in cache
    obj = await create(node, "steven")
    assert obj.name == "steven"
    assert obj.description == "description"

    obj = await create(node, "steven", power="10KW")
    assert obj.name == "steven"
    assert obj.description == "description"


async def test_init_instance() -> None:
    async def _create(node: Node, name: str, **config: Any) -> Object:
        return await node.init_instance(name, "debian", **config)

    await _test_init_object(Instance, _create, "incus init debian %s")


async def test_init_network() -> None:
    async def _create(node: Node, name: str, **config: Any) -> Object:
        return await node.init_network(name)

    await _test_init_object(Network, _create, "incus network create %s")


async def test_init_profile() -> None:
    async def _create(node: Node, name: str, **config: Any) -> Object:
        return await node.init_profile(name)

    await _test_init_object(Profile, _create, "incus profile create %s")


async def test_init_project() -> None:
    async def _create(node: Node, name: str, **config: Any) -> Object:
        return await node.init_project(name)

    await _test_init_object(Project, _create, "incus project create %s")


async def test_init_storage() -> None:
    async def _create(node: Node, name: str, **config: Any) -> Storage:
        return await node.init_storage(name, "btrfs", **config)

    await _test_init_object(Storage, _create, "incus storage create %s btrfs")
