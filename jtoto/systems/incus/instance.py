from shlex import quote
from typing import Any

from jtoto.shell import Process, Shell, Stderr, Stdout
from jtoto.systems.incus.cli import IncusCli
from jtoto.systems.incus.object import Object


class Instance(Object):
    subcommand = ""
    config_subcommand = "config"
    ignore_keys = ("image",)

    async def save(self, **full_config: Any) -> None:
        new_full_config = dict(**full_config)
        if "config" in self._full_config and "config" in new_full_config:
            for key, value in self._full_config["config"].items():
                if key.startswith("image") or key.startswith("volatile"):
                    new_full_config["config"][key] = value
        return await super().save(**new_full_config)

    async def start(self) -> None:
        await self._cli(f"start {self.name}")

    async def stop(self) -> None:
        await self._cli(f"stop {self.name}")

    def get_shell(self, **kwargs: Any) -> Shell:
        return _InstanceShell(self._cli, self.name, **kwargs)


class _InstanceShell(Shell):
    def __init__(
        self,
        cli: IncusCli,
        container_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cli = cli
        self._name = container_name

    async def _start_process(
        self, out: Stdout, err: Stderr, command: str, env: dict[str, str]
    ) -> Process:
        env_parameters = "".join(
            [f" --env {key}={quote(value)}" for key, value in env.items()]
        )

        return await self._cli._start_process(  # pylint: disable=protected-access
            out,
            err,
            f"exec {self._name}{env_parameters} -- sh -c {quote(command)}",
            env={},
        )
