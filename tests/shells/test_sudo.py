"""Config unit tests."""
from typing import AsyncIterator

from jshell.shells.sudo import SudoShell
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


async def test_run() -> None:
    """Sudo should call inner shell with modified command."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("sudo sh -c 'wubba luba dub dub'")

    async with MockShell(_mock_cli()) as sh:
        sudo = SudoShell(sh)
        await sudo("wubba luba dub dub")


async def test_run_with_user() -> None:
    """Sudo should forward configured user to inner shell."""

    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("sudo -u jean-marc sh -c 'wubba luba dub dub'")

    async with MockShell(_mock_cli()) as sh:
        sudo = SudoShell(sh, user="jean-marc")
        await sudo("wubba luba dub dub")
