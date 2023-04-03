from jshell.core.shell import Shell
from jshell.systems.systemd.nspawn import NSpawn
from tests._mocks.mock_shell import MockShell


async def test_create_machine() -> None:
    """A new machine should be created if it doesn't exists."""

    async def _task(sh: Shell) -> None:
        nspawn = NSpawn(sh)
        async with nspawn.configure() as config:
            config.add_machine("peter", "https://otter-os.tar", "config content")

    async with MockShell(_task) as sh:
        p = await sh.next()
        assert p.command == "machinectl --output json list-images"
        await p.write_stdout(b"[]")
        await p.exit(0)

        p = await sh.next()
        assert p.command == "machinectl --output json list"
        await p.write_stdout(b"[]")
        await p.exit(0)

        p = await sh.next()
        assert (
            p.command
            == "machinectl pull-tar --verify=checksum https://otter-os.tar peter"
        )
        await p.write_stdout(b"[]")
        await p.exit(0)

        p = await sh.next()
        assert p.command == "mkdir -p /etc/systemd/nspawn"
        await p.write_stdout(b"[]")
        await p.exit(0)

        p = await sh.next()
        assert p.command == "cat > /etc/systemd/nspawn/peter.nspawn"
        assert await p.read_stdin() == b"config content"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "machinectl enable peter"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "systemctl daemon-reload"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "systemctl restart machines.target"
        await p.exit(0)
