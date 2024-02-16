from typing import AsyncIterator

from jtoto.systems.incus.cli import IncusCli
from jtoto.testing import MockProcess, MockShell, check_process


async def test_run() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process("incus badebliblu")
        yield check_process("/usr/bin/incus badebliblu")
        yield check_process("incus --project otters badebliblu")

    async with MockShell(_mock_cli()) as sh:
        cli = IncusCli(sh)
        await cli("badebliblu")

        cli = IncusCli(sh, incus_path="/usr/bin/incus")
        await cli("badebliblu")

        cli = IncusCli(sh, project="otters")
        await cli("badebliblu")
