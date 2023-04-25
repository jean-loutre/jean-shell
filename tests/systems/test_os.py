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


async def _check_manifest(manifest: str, *processes: MockProcess) -> None:
    async def _system_mock() -> AsyncIterator[MockProcess]:
        for process in processes:
            yield process

    async with MockShell(_system_mock()) as sh:
        os = MockOs(sh)
        await os.sync_manifest(manifest)


async def test_manifest_content_string() -> None:
    await _check_manifest(
        """
        files:
          /etc/otters:
            content: |
              Kweek kweek
        """,
        check_process("write /etc/otters", expected_stdin=b"Kweek kweek\n"),
    )


async def test_manifest_content_base64() -> None:
    await _check_manifest(
        """
        files:
          /etc/otters:
            content: !base64 S3dlZWsga3dlZWsK
        """,
        check_process("write /etc/otters", expected_stdin=b"Kweek kweek\n"),
    )


async def test_manifest_content_directory() -> None:
    await _check_manifest(
        """
        files:
          /etc/otters:
            content: !dir
              peter_file:
                user: peter
              steven_file:
                user: steven
        """,
        check_process("mkdir /etc/otters"),
        check_process("permissions /etc/otters/peter_file peter None None"),
        check_process("permissions /etc/otters/steven_file steven None None"),
    )


async def test_manifest_link_content() -> None:
    await _check_manifest(
        """
        files:
          /steven:
            content: !link /peter
        """,
        check_process("link /peter /steven"),
    )


async def test_manifest_file_mode() -> None:
    await _check_manifest(
        """
        files:
          /etc/otters:
            user: peter
            group: peter
            mode: 0755
        """,
        check_process("permissions /etc/otters peter peter 0755"),
    )


async def test_manifest_multiple_target() -> None:
    await _check_manifest(
        """
        files:
          [/etc/wubba, /etc/lubba]:
            user: steven
            group: otters
            mode: 0755
        """,
        check_process("permissions /etc/wubba steven otters 0755"),
        check_process("permissions /etc/lubba steven otters 0755"),
    )
