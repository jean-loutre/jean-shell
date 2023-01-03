from jshell.apt import set_packages
from jshell.core.shell import Shell
from tests._mocks.mock_shell import mock_shell


async def test_apt() -> None:
    async def _task(shell: Shell) -> None:
        await set_packages(
            shell,
            "python3-otter",
            "caiman-shredder",
            source_list="deb http://debian.org stable main",
        )

    async with mock_shell(_task) as shell:
        p = await shell.next()
        assert p.command == "cat > /etc/apt/sources.list"
        assert await p.read_stdin() == b"deb http://debian.org stable main"
        await p.exit(0)

        p = await shell.next()
        assert p.command == "apt-mark showmanual"
        await p.write_stdout(b"manually\ninstalled\npackages")
        await p.exit(0)

        p = await shell.next()
        assert p.command == "apt-mark auto manually installed packages"
        await p.exit(0)

        p = await shell.next()
        assert p.env == {"DEBIAN_FRONTEND": "noninteractive"}
        assert p.command == "apt-get -yq install python3-otter caiman-shredder"
        await p.exit(0)

        p = await shell.next()
        assert p.env == {"DEBIAN_FRONTEND": "noninteractive"}
        assert p.command == "apt-get -yq dist-upgrade"
        await p.exit(0)

        p = await shell.next()
        assert p.env == {"DEBIAN_FRONTEND": "noninteractive"}
        assert p.command == "apt-get -yq autoremove --purge"
        await p.exit(0)
