from pathlib import Path
from typing import AsyncIterator

from jshell.core.shell import ShellPipe
from jshell.systems.os import Os
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


class MockOs(Os):
    def make_directory(self, path: str | Path) -> ShellPipe:
        """Create a directory."""
        return self._sh(f"mkdir {path}")

    def write_file(self, path: str | Path) -> ShellPipe:
        return self._sh(f"write {path}")

    async def set_permissions(
        self,
        path: str | Path,
        user: str | None = None,
        group: str | None = None,
        mode: str | None = None,
    ) -> None:
        await self._sh(f"permissions {path} {user} {group} {mode}")


async def test_sync_batch_write_file() -> None:
    """Sync batch should create directories and write to files"""

    async def _mock_system() -> AsyncIterator[MockProcess]:
        yield check_process("mkdir /etc/otter")
        yield check_process(
            "write /etc/otter/otter.cfg", expected_stdin="kweek = kweek kweek"
        )

    async with MockShell(_mock_system()) as sh:
        os = MockOs(sh)
        async with os.sync() as batch:
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
        os = MockOs(sh)
        async with os.sync() as batch:
            batch.add("/etc/hosts", b"")
            batch.add("/etc/otters/peter.cfg", b"")
            batch.add("/etc/otters/steven.cfg", b"")
            batch.add("/etc/resolv.conf", b"")


async def test_manifest_directory_source() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("mkdir /etc/otters")
        yield check_process("permissions /etc/otters/peter_file peter None None")
        yield check_process("permissions /etc/otters/steven_file steven None None")

    manifest = """
    files:
      /etc/otters:
        source: !dir
          peter_file:
            user: peter
          steven_file:
            user: steven
    """
    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_default_source(tmp_path: Path) -> None:
    test_path = tmp_path / "peter"
    test_content = b"Kweek kweek"
    with open(test_path, "wb") as test_file:
        test_file.write(test_content)

    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("write /etc/otters", expected_stdin=test_content)

    manifest = f"""
    files:
      /etc/otters:
        source: {test_path}
    """

    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_file_mode() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("permissions /etc/otters peter peter 0755")

    manifest = """
    files:
      /etc/otters:
        user: peter
        group: peter
        mode: 0755
    """
    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)
