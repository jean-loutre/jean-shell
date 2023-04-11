"""LXD Cli unit tests."""
from typing import AsyncIterator

from jshell.systems.lxd.cli import LxcCli
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


async def test_run() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("lxc badebliblu")
        yield check_process("/usr/bin/lxc badebliblu")
        yield check_process("lxc --project otters badebliblu")

    async with MockShell(_mock_cli()) as sh:
        cli = LxcCli(sh)
        await cli("badebliblu")

        cli = LxcCli(sh, lxc_path="/usr/bin/lxc")
        await cli("badebliblu")

        cli = LxcCli(sh, project="otters")
        await cli("badebliblu")
