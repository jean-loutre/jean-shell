from typing import AsyncIterator

from json import loads
from jtoto.systems.incus import Instance
from jtoto.systems.incus.cli import IncusCli
from jtoto.testing import MockProcess, MockShell, check_process


async def test_start_stop() -> None:
    async def _mock_default() -> AsyncIterator[MockProcess]:
        yield check_process("incus start peter")
        yield check_process("incus stop peter")

    async with MockShell(_mock_default()) as sh:
        cli = IncusCli(sh)
        instance = Instance(cli, "peter")
        await instance.start()
        await instance.stop()


async def test_get_shell() -> None:
    async def _mock_default() -> AsyncIterator[MockProcess]:
        yield check_process("incus exec peter -- sh -c 'kweek kweek'")
        yield check_process("incus exec peter --env OTTER_KEY='kw33k kw33k' -- sh -c 'kweek kweek'")
        yield check_process("incus --project otters exec peter -- sh -c 'kweek kweek'")

    async with MockShell(_mock_default()) as sh:
        cli = IncusCli(sh)
        instance_sh = Instance(cli, "peter").get_shell()
        await instance_sh("kweek kweek")

        overlay_sh = instance_sh.overlay(env=dict(OTTER_KEY="kw33k kw33k"))
        await overlay_sh("kweek kweek")

        cli = IncusCli(sh, project="otters")
        instance_sh = Instance(cli, "peter").get_shell()
        await instance_sh("kweek kweek")


async def test_save() -> None:
    def _check_sent_config(stdin: bytes) -> None:
        new_config = loads(stdin.decode("utf-8"))
        assert new_config == {
            "name": "peter",
            "config": {
                "security.privileged": True,
                "volatile.volatile_var": "initial-volatile-value",
                "image.image_var": "initial-image-value",
            },
        }

    async def _mock_default() -> AsyncIterator[MockProcess]:
        yield check_process(
            "incus config edit peter",
            expected_stdin=_check_sent_config,
        )

    async with MockShell(_mock_default()) as sh:
        cli = IncusCli(sh)
        instance = Instance(
            cli,
            "peter",
            config={
                "security.privileged": False,
                "volatile.volatile_var": "initial-volatile-value",
                "image.image_var": "initial-image-value",
            },
        )

        assert instance.config["volatile.volatile_var"] == "initial-volatile-value"
        assert instance.config["image.image_var"] == "initial-image-value"
        assert instance.config["security.privileged"] is False

        await instance.save(config={"security.privileged": True})
        assert instance.config["volatile.volatile_var"] == "initial-volatile-value"
        assert instance.config["image.image_var"] == "initial-image-value"
        assert instance.config["security.privileged"] is True
