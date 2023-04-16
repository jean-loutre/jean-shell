from shlex import quote
from typing import Any

from jshell.core.pipe import PipeWriter, parse_yaml
from jshell.core.shell import Shell, ShellProcess
from jshell.systems.lxd.cli import LxcCli
from jshell.systems.lxd.object import Object


class Instance(Object):
    """LXD Project settings"""

    subcommand = ""
    ignore_keys = ("image",)

    async def load(self) -> None:
        name = self.name
        self._config = await (self._cli(f"config show {self.name}") | parse_yaml())
        self._config["name"] = name

    async def save(self, **config: Any) -> None:
        self._config.update(**config)
        await (self._dump() | self._cli(f"config edit {self.name}"))

    async def start(self) -> None:
        await self._cli(f"start {self.name}")

    async def stop(self) -> None:
        await self._cli(f"stop {self.name}")

    def get_shell(self, **kwargs: Any) -> Shell:
        return _InstanceShell(self._cli, self.name, **kwargs)


class _InstanceShell(Shell):
    def __init__(
        self,
        cli: LxcCli,
        container_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cli = cli
        self._name = container_name

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        env_parameters = "".join(
            [f" --env {key}={quote(value)}" for key, value in env.items()]
        )

        return await self._cli._start_process(  # pylint: disable=protected-access
            out,
            err,
            f"exec {self._name}{env_parameters} -- sh -c {quote(command)}",
            env={},
        )
