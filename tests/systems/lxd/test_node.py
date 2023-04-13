"""LXD Object unit tests."""
from typing import AsyncIterator

from jshell.systems.lxd import lxd_node
from jshell.systems.lxd.object import Object
from tests._mocks.mock_shell import MockProcess, check_process, mock_shell


async def test_load_with_project() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            "lxc --project peter project list --format yaml", stdout="[]"
        )
        yield check_process("lxc --project peter project create peter")
        yield check_process("lxc --project peter project show peter", stdout="{}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh, project="peter"):
        pass


async def test_ensure_instance() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            "lxc  list --format yaml", stdout="[{name: peter, status: sad}]"
        )
        yield check_process(
            "lxc config edit peter",
            expected_stdin="name: peter\npower: 12GW\nstatus: sad\n",
        )
        yield check_process(
            "lxc config edit peter",
            expected_stdin="name: peter\npower: 12GW\nstatus: sad\n",
        )
        yield check_process(
            "lxc init debian steven",
            expected_stdin="power: 12GW\n",
        )
        yield check_process("lxc config show steven", stdout="{status: happy}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        instance = await node.ensure_instance("peter", "debian", power="12GW")
        assert instance.name == "peter"
        assert instance.status == "sad"

        instance = await node.ensure_instance("peter", "debian", power="12GW")
        assert instance.name == "peter"
        assert instance.status == "sad"

        instance = await node.ensure_instance("steven", "debian", power="12GW")
        assert instance.name == "steven"
        assert instance.status == "happy"


async def test_ensure_network() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            "lxc network list --format yaml", stdout="[{name: peter, status: online}]"
        )
        yield check_process("lxc network create steven --type nic")
        yield check_process("lxc network show steven", stdout="{status: online}")
        yield check_process("lxc network create roger")
        yield check_process("lxc network show roger", stdout="{status: online}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        network = await node.ensure_network("peter")
        assert network.name == "peter"
        assert network.status == "online"

        network = await node.ensure_network("steven", type="nic")
        assert network.name == "steven"
        assert network.status == "online"

        # shouldn't do any call if network already exists
        network = await node.ensure_network("steven", type="nic")
        assert network.name == "steven"
        assert network.status == "online"

        # test creation with default type
        network = await node.ensure_network("roger")
        assert network.name == "roger"
        assert network.status == "online"


async def test_ensure_profile() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # profile is ignored in commands not using it
        yield check_process(
            "lxc profile list --format yaml",
            stdout="[{name: peter, description: otters}]",
        )
        yield check_process("lxc profile create steven")
        yield check_process("lxc profile show steven", stdout="{description: otters}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        profile = await node.ensure_profile("peter")
        assert profile.name == "peter"
        assert profile.description == "otters"

        profile = await node.ensure_profile("steven")
        assert profile.name == "steven"
        assert profile.description == "otters"

        profile = await node.ensure_profile("steven")
        assert profile.name == "steven"
        assert profile.description == "otters"


async def test_ensure_project() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            "lxc project list --format yaml",
            stdout="[{name: peter, description: otters}]",
        )
        yield check_process("lxc project create steven")
        yield check_process("lxc project show steven", stdout="{description: otters}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        project = await node.ensure_project("peter")
        assert project.name == "peter"
        assert project.description == "otters"

        project = await node.ensure_project("steven")
        assert project.name == "steven"
        assert project.description == "otters"

        project = await node.ensure_project("steven")
        assert project.name == "steven"
        assert project.description == "otters"


async def test_ensure_storage() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        # project is ignored in commands not using it
        yield check_process(
            "lxc storage list --format yaml",
            stdout="[{name: peter, description: otters}]",
        )
        yield check_process("lxc storage create steven btrfs")
        yield check_process("lxc storage show steven", stdout="{description: otters}")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        storage = await node.ensure_storage("peter", "btrfs")
        assert storage.name == "peter"
        assert storage.description == "otters"

        storage = await node.ensure_storage("steven", "btrfs")
        assert storage.name == "steven"
        assert storage.description == "otters"

        storage = await node.ensure_storage("steven", "btrfs")
        assert storage.name == "steven"
        assert storage.description == "otters"


class _MockObject(Object):
    subcommand = "mock"
    ignore_keys = ("ignore_me",)


async def test_get_objects() -> None:
    """LXC Object should correctly create instances from LXC cli."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "lxc mock list --format yaml",
            stdout="[{name: peter, power: 3W}, {name: steven, power: 12GW}]",
        )

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        objects = list(await node.get_objects(_MockObject))
        assert len(objects) == 2
        peter = objects[0]
        steven = objects[1]

        assert isinstance(peter, _MockObject)
        assert peter.name == "peter"
        assert peter.power == "3W"

        assert isinstance(steven, _MockObject)
        assert steven.name == "steven"
        assert steven.power == "12GW"


async def test_get_object() -> None:
    """LXC Object should correctly return an object if it exists."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "lxc mock list --format yaml",
            stdout=("- name: peter\n" + "  power: 3W\n"),
        )

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        peter = await node.get_object(_MockObject, "peter")
        assert peter is not None
        assert peter.name == "peter"
        assert peter.power == "3W"

        steven = await node.get_object(_MockObject, "steven")
        assert steven is None


async def test_delete() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "lxc mock list --format yaml",
            stdout="[{name: peter, power: 3W}]",
        )
        yield check_process("lxc mock delete peter")

    sh = mock_shell(_mock_cli())
    async with lxd_node(sh) as node:
        peter = await node.get_object(_MockObject, "peter")
        assert peter is not None
        await node.delete(peter)

        peter = await node.get_object(_MockObject, "peter")
        assert peter is None
