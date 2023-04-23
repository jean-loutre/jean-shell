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

    async def link(self, target: str | Path, path: str | Path) -> None:
        await self._sh(f"link {target} {path}")

    async def set_permissions(
        self,
        path: str | Path,
        user: str | None = None,
        group: str | None = None,
        mode: str | None = None,
    ) -> None:
        await self._sh(f"permissions {path} {user} {group} {mode}")


async def test_manifest_content_string() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("write /etc/otters", expected_stdin=b"Kweek kweek\n")

    manifest = """
    files:
      /etc/otters:
        content: |
          Kweek kweek
    """

    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_content_base64() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("write /etc/otters", expected_stdin=b"Kweek kweek\n")

    manifest = """
    files:
      /etc/otters:
        content: !base64 S3dlZWsga3dlZWsK
    """

    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_content_directory() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("mkdir /etc/otters")
        yield check_process("permissions /etc/otters/peter_file peter None None")
        yield check_process("permissions /etc/otters/steven_file steven None None")

    manifest = """
    files:
      /etc/otters:
        content: !dir
          peter_file:
            user: peter
          steven_file:
            user: steven
    """
    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_link_content() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("link /peter /steven")

    manifest = """
    files:
      /steven:
        content: !link /peter
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


async def test_manifest_multiple_target() -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        yield check_process("permissions /etc/wubba steven otters 0755")
        yield check_process("permissions /etc/lubba steven otters 0755")

    manifest = """
    files:
      [/etc/wubba, /etc/lubba]:
        user: steven
        group: otters
        mode: 0755
    """
    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)
