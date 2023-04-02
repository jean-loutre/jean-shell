from pathlib import Path

from jshell.core.shell import Shell, ShellPipe
from jshell.systems.os import Os
from tests._mocks.mock_shell import MockShell


class MockOs(Os):
    def make_directory(self, sh: Shell, path: str | Path) -> ShellPipe:
        """Create a directory."""
        return sh(f"mkdir {path}")

    def write_file(self, sh: Shell, path: str | Path) -> ShellPipe:
        return sh(f"write {path}")


async def test_sync_batch_write_file() -> None:
    """Sync batch should create directories and write to files"""
    os = MockOs()

    async def _task(sh: Shell) -> None:
        async with os.sync(sh) as batch:
            batch.add("/etc/otter/otter.cfg", b"kweek = kweek kweek")

    async with MockShell(_task) as sh:
        p = await sh.next()
        assert p.command == "mkdir /etc/otter"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "write /etc/otter/otter.cfg"
        assert await p.read_stdin() == b"kweek = kweek kweek"
        await p.exit(0)


async def test_sync_batch_create_directories() -> None:
    """Sync batch should create directories only once"""
    os = MockOs()

    async def _task(sh: Shell) -> None:
        async with os.sync(sh) as batch:
            batch.add("/etc/hosts", b"")
            batch.add("/etc/otters/peter.cfg", b"")
            batch.add("/etc/otters/steven.cfg", b"")
            batch.add("/etc/resolv.conf", b"")

    async with MockShell(_task) as sh:
        p = await sh.next()
        assert p.command == "mkdir /etc/otters"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "write /etc/hosts"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "write /etc/otters/peter.cfg"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "write /etc/otters/steven.cfg"
        await p.exit(0)

        p = await sh.next()
        assert p.command == "write /etc/resolv.conf"
        await p.exit(0)
