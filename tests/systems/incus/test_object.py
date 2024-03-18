from json import dumps, loads
from typing import Any, AsyncIterator, Callable
from unittest.mock import AsyncMock

from jtoto.systems.incus.cli import IncusCli
from jtoto.systems.incus.object import Object
from jtoto.testing import MockProcess, MockShell, check_process


def _check_json_stdin(expected_object: Any) -> Callable[[bytes], None]:
    def _check(content: bytes) -> None:
        assert loads(content.decode("utf-8")) == expected_object

    return _check


class _MockObject(Object):
    subcommand = "mock"
    config_subcommand = "mockedit"
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
            "incus mock list peter --format json",
            stdout=dumps([{"power": "3W"}]),
        )

    async with MockShell(_mock_cli()) as sh:
        cli = IncusCli(sh)
        obj = _MockObject(cli, name="peter", power="12GW")
        await obj.load()
        assert obj.name == "peter"
        assert obj.power == "3W"


async def test_save() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "incus mockedit edit peter",
            expected_stdin=_check_json_stdin({"mood": "happy", "name": "peter", "power": "3W"}),
        )
        yield check_process(
            "incus mockedit edit peter",
            expected_stdin=_check_json_stdin({"mood": "angry", "name": "peter", "power": "3W"}),
        )

    async with MockShell(_mock_cli()) as sh:
        cli = IncusCli(sh)
        obj = _MockObject(cli, name="peter", power="3W", ignore_me="M2GABASSINE")
        obj.mood = "happy"
        await obj.save()

        # Shouldn't do anything, as nothing changed
        await obj.save()

        obj.mood = "angry"
        await obj.save()
