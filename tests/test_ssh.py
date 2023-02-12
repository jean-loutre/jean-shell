"""Config unit tests."""
from unittest.mock import ANY, AsyncMock, patch

from asyncssh import SSHClientConnectionOptions

from jshell.core.pipe import PipeWriter
from jshell.ssh import SshSettings


@patch("jshell.ssh.connect")
async def test_connect(connect_mock: AsyncMock) -> None:
    """SshSettings should forward correct arguments to asyncssh."""
    settings = SshSettings(host="otters.org", user="gilbert")

    async with settings.connect():
        pass

    connect_mock.return_value.__aenter__.assert_awaited_once()
    connect_mock.return_value.__aexit__.assert_awaited_once()

    connect_mock.assert_called_once()
    args, kwargs = connect_mock.call_args_list[0]
    assert args == ("otters.org",)

    options = kwargs["options"]
    assert isinstance(options, SSHClientConnectionOptions)
    assert options.username == "gilbert"


@patch("jshell.ssh.connect")
async def test_run(connect_mock: AsyncMock) -> None:
    """SshSettings should forward correct arguments to asyncssh."""
    settings = SshSettings(host="otters.org", user="gilbert")

    async with settings.connect() as ssh:

        async def create_process(
            _: str,
            stdout: PipeWriter,
            stderr: PipeWriter,
            env: dict[str, str],  # pylint: disable=unused-argument
            encoding: str,  # pylint: disable=unused-argument
        ) -> AsyncMock:
            await stdout.close()
            await stderr.close()
            process_mock = AsyncMock()
            process_mock.returncode = 0
            return process_mock

        create_process_mock = (
            connect_mock.return_value.__aenter__.return_value.create_process
        )
        create_process_mock.side_effect = create_process

        await ssh("tickle otter")
        create_process_mock.assert_awaited_once_with(
            "tickle otter", stdout=ANY, stderr=ANY, env={}, encoding=None
        )
