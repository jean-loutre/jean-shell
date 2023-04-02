"""Config unit tests."""
from unittest.mock import Mock

from jshell.systems.unix import Unix


def test_make_directories() -> None:
    """Unix should call correct commands to create a directory."""
    unix = Unix()
    sh_mock = Mock()
    unix.make_directory(sh_mock, "/etc/otters")
    sh_mock.assert_called_once_with("mkdir -p /etc/otters", raise_on_error=False)


def test_write_files() -> None:
    """Unix should call correct commands to write a file."""
    unix = Unix()
    sh_mock = Mock()
    unix.write_file(sh_mock, "/etc/otters")
    sh_mock.assert_called_once_with("cat > /etc/otters")
