"""Config unit tests."""
from unittest.mock import ANY, AsyncMock, patch

from asyncssh import SSHClientConnectionOptions

from jtoto.shell import Stderr, Stdout
from jtoto.systems.ssh import ssh_shell


@patch("jtoto.systems.ssh.connect")
async def test_connect(connect_mock: AsyncMock) -> None:
    async with ssh_shell(host="otters.org", username="gilbert"):
        pass

    connect_mock.return_value.__aenter__.assert_awaited_once()
    connect_mock.return_value.__aexit__.assert_awaited_once()

    connect_mock.assert_called_once()
    args, kwargs = connect_mock.call_args_list[0]
    assert args == ("otters.org",)

    options = kwargs["options"]
    assert isinstance(options, SSHClientConnectionOptions)
    assert options.username == "gilbert"


@patch("jtoto.systems.ssh.connect")
async def test_run(connect_mock: AsyncMock) -> None:
    async with ssh_shell("otters.org", username="gilbert") as sh:

        async def create_process(
            _: str,
            stdout: Stdout,
            stderr: Stderr,
            env: dict[str, str],  # pylint: disable=unused-argument
            encoding: str,  # pylint: disable=unused-argument
        ) -> AsyncMock:
            if stdout:
                await stdout.close()
            if stderr:
                await stderr.close()
            process_mock = AsyncMock()
            process_mock.returncode = 0
            return process_mock

        create_process_mock = (
            connect_mock.return_value.__aenter__.return_value.create_process
        )
        create_process_mock.side_effect = create_process

        await sh("tickle otter")
        create_process_mock.assert_awaited_once_with(
            "tickle otter", stdout=ANY, stderr=ANY, env={}, encoding=None
        )
