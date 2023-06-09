"""Config unit tests."""
from typing import AsyncIterator
from unittest.mock import AsyncMock, Mock

from jshell.systems.unix import Unix
from tests._mocks.mock_shell import MockProcess, MockShell, check_process


def test_make_directories() -> None:
    sh_mock = Mock()
    unix = Unix(sh_mock)
    unix.make_directory("/etc/otters")
    sh_mock.assert_called_once_with("mkdir -p /etc/otters", raise_on_error=False)


def test_write_files() -> None:
    sh_mock = Mock()
    unix = Unix(sh_mock)
    unix.write_file("/etc/otters")
    sh_mock.assert_called_once_with("cat > /etc/otters")


async def test_link() -> None:
    sh_mock = AsyncMock()
    unix = Unix(sh_mock)
    await unix.link("/link", "/target")
    sh_mock.assert_awaited_once_with("ln -sfn /link /target")


async def test_set_permissions() -> None:
    async def _mock_system() -> AsyncIterator[MockProcess]:
        yield check_process("chown peter /etc/otter")
        yield check_process("chgrp peter /etc/otter")
        yield check_process("chmod 0755 /etc/otter")
        yield check_process("chown peter /etc/otter")
        yield check_process("chgrp peter /etc/otter")
        yield check_process("chmod 0755 /etc/otter")

    async with MockShell(_mock_system()) as sh:
        os = Unix(sh)
        await os.set_permissions("/etc/otter", user="peter")
        await os.set_permissions("/etc/otter", group="peter")
        await os.set_permissions("/etc/otter", mode="0755")
        await os.set_permissions("/etc/otter", user="peter", group="peter", mode="0755")
