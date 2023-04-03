from json import dumps
from typing import AsyncIterator

from jshell.systems.systemd.nspawn import NSpawn
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


async def test_create_machine() -> None:
    """A new machine should be created if it doesn't exists."""

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("machinectl --output json list-images", stdout="[]")
        yield check_process("machinectl --output json list", stdout="[]")
        yield check_process(
            "machinectl pull-tar --verify=checksum https://otter-os.tar peter"
        )
        yield check_process("mkdir -p /etc/systemd/nspawn")
        yield check_process(
            "cat > /etc/systemd/nspawn/peter.nspawn", expected_stdin="config content"
        )
        yield check_process("machinectl enable peter")
        yield check_process("systemctl daemon-reload")
        yield check_process("systemctl restart machines.target")

    async with MockShell(_system_mock()) as sh:
        nspawn = NSpawn(sh)
        async with nspawn.configure() as config:
            config.add_machine("peter", "https://otter-os.tar", "config content")


async def test_reuse_existing_machine() -> None:
    """A new machine should be created if it doesn't exists."""

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process(
            "machinectl --output json list-images", stdout=dumps([{"name": "peter"}])
        )
        yield check_process("machinectl --output json list", stdout="[]")
        yield check_process("mkdir -p /etc/systemd/nspawn")
        yield check_process(
            "cat > /etc/systemd/nspawn/peter.nspawn", expected_stdin="config content"
        )
        yield check_process("machinectl enable peter")
        yield check_process("systemctl daemon-reload")
        yield check_process("systemctl restart machines.target")

    async with MockShell(_system_mock()) as sh:
        nspawn = NSpawn(sh)
        async with nspawn.configure() as config:
            config.add_machine("peter", "https://otter-os.tar", "config content")


async def test_delete_machine() -> None:
    """A new machine should be created if it doesn't exists."""

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process(
            "machinectl --output json list-images", stdout=dumps([{"name": "steven"}])
        )
        yield check_process("machinectl --output json list", stdout="[]")
        yield check_process("machinectl remove steven")
        yield check_process("systemctl daemon-reload")
        yield check_process("systemctl restart machines.target")

    async with MockShell(_system_mock()) as sh:
        nspawn = NSpawn(sh)
        async with nspawn.configure():
            pass


async def test_stop_and_delete_machine() -> None:
    """A new machine should be created if it doesn't exists."""

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process(
            "machinectl --output json list-images", stdout=dumps([{"name": "steven"}])
        )
        yield check_process(
            "machinectl --output json list", stdout=dumps([{"machine": "steven"}])
        )
        yield check_process("machinectl poweroff steven")
        yield check_process("machinectl remove steven")
        yield check_process("systemctl daemon-reload")
        yield check_process("systemctl restart machines.target")

    async with MockShell(_system_mock()) as sh:
        nspawn = NSpawn(sh)
        async with nspawn.configure():
            pass
