from pathlib import Path
from typing import AsyncIterator

from jshell.core.shell import Shell, ShellPipe
from jshell.systems.os import Os
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


class MockOs(Os):
    def make_directory(self, sh: Shell, path: str | Path) -> ShellPipe:
        """Create a directory."""
        return sh(f"mkdir {path}")

    def write_file(self, sh: Shell, path: str | Path) -> ShellPipe:
        return sh(f"write {path}")


async def test_sync_batch_write_file() -> None:
    """Sync batch should create directories and write to files"""

    async def _mock_system() -> AsyncIterator[MockProcess]:
        yield check_process("mkdir /etc/otter")
        yield check_process(
            "write /etc/otter/otter.cfg", expected_stdin="kweek = kweek kweek"
        )

    async with MockShell(_mock_system()) as sh:
        os = MockOs()
        async with os.sync(sh) as batch:
            batch.add("/etc/otter/otter.cfg", b"kweek = kweek kweek")


async def test_sync_batch_create_directories() -> None:
    """Sync batch should create directories only once"""

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("mkdir /etc/otter")
        yield check_process("write /etc/hosts")
        yield check_process("write /etc/otters/peter.cfg")
        yield check_process("write /etc/otters/steven.cfg")
        yield check_process("write /etc/resolv.conf")

    async with MockShell(_system_mock()) as sh:
        os = MockOs()
        async with os.sync(sh) as batch:
            batch.add("/etc/hosts", b"")
            batch.add("/etc/otters/peter.cfg", b"")
            batch.add("/etc/otters/steven.cfg", b"")
            batch.add("/etc/resolv.conf", b"")
