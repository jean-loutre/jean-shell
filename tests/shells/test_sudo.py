"""Config unit tests."""
from unittest.mock import ANY, Mock

from jshell.shells.sudo import SudoShell


async def test_run() -> None:
    """Sudo should call inner shell with modified command."""
    inner_mock = Mock()
    shell = SudoShell(inner_mock)
    shell.run("tickle otter")
    inner_mock._create_process.called_once_with(  # pylint: disable=protected-access
        "sudo tickle otter", stdout=ANY
    )


async def test_run_with_user() -> None:
    """Sudo should forward configured user to inner shell."""
    inner_mock = Mock()
    shell = SudoShell(inner_mock, user="jean-marc")
    shell.run("tickle otter")
    inner_mock._create_process.called_once_with(  # pylint: disable=protected-access
        "sudo -u jean-marc tickle otter", stdout=ANY
    )
