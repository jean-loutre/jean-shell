"""LXD Object unit tests."""

from typing import AsyncIterator
from unittest.mock import AsyncMock

from jshell.systems.lxd.cli import LxcCli
from jshell.systems.lxd.object import Object
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


class _MockObject(Object):
    subcommand = "mock"
    ignore_keys = ("ignore_me",)


async def test_get_attr() -> None:
    obj = _MockObject(AsyncMock(), name="peter", power="12GW")
    assert obj.name == "peter"
    assert obj.power == "12GW"


async def test_set_attr() -> None:
    obj = _MockObject(AsyncMock(), name="peter")
    obj.power = "12GW"
    assert obj.power == "12GW"


async def test_load() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "lxc mock show peter",
            stdout="power: 3W\n",
        )

    async with MockShell(_mock_cli()) as sh:
        cli = LxcCli(sh)
        obj = _MockObject(cli, name="peter", power="12GW")
        await obj.load()
        assert obj.name == "peter"
        assert obj.power == "3W"


async def test_save() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "lxc mock edit peter",
            expected_stdin="mood: happy\nname: peter\npower: 3W\n",
        )

    async with MockShell(_mock_cli()) as sh:
        cli = LxcCli(sh)
        obj = _MockObject(cli, name="peter", power="3W", ignore_me="M2GABASSINE")
        obj.mood = "happy"
        await obj.save()
