"""LXD Cli unit tests."""
from typing import AsyncIterator

from jshell.systems.lxd import Instance
from jshell.systems.lxd.cli import LxcCli
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


async def test_start_stop() -> None:
    async def _mock_default() -> AsyncIterator[MockProcess]:
        yield check_process("lxc start peter")
        yield check_process("lxc stop peter")

    async with MockShell(_mock_default()) as sh:
        cli = LxcCli(sh)
        instance = Instance(cli, "peter")
        await instance.start()
        await instance.stop()


async def test_get_shell() -> None:
    async def _mock_default() -> AsyncIterator[MockProcess]:
        yield check_process("lxc exec peter -- sh -c 'kweek kweek'")
        yield check_process(
            "lxc exec peter --env OTTER_KEY='kw33k kw33k' -- sh -c 'kweek kweek'"
        )
        yield check_process("lxc --project otters exec peter -- sh -c 'kweek kweek'")

    async with MockShell(_mock_default()) as sh:
        cli = LxcCli(sh)
        instance_sh = Instance(cli, "peter").get_shell()
        await instance_sh("kweek kweek")

        with instance_sh.env(OTTER_KEY="kw33k kw33k"):
            await instance_sh("kweek kweek")

        cli = LxcCli(sh, project="otters")
        instance_sh = Instance(cli, "peter").get_shell()
        await instance_sh("kweek kweek")
