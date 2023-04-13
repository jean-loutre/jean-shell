"""Config unit tests."""
from typing import AsyncIterator

from jshell.shells.sudo import sudo_shell
from tests._mocks.mock_shell import MockProcess, check_process, mock_shell


async def test_run() -> None:
    """Sudo should call inner shell with modified command."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("sudo sh -c 'wubba luba dub dub'")

    sh = mock_shell(_mock_cli())
    async with sudo_shell(sh) as sudo:
        await sudo("wubba luba dub dub")


async def test_run_with_user() -> None:
    """Sudo should forward configured user to inner shell."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("sudo -u jean-marc sh -c 'wubba luba dub dub'")

    sh = mock_shell(_mock_cli())
    async with sudo_shell(sh, user="jean-marc") as sudo:
        await sudo("wubba luba dub dub")
