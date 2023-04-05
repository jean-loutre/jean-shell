from contextlib import asynccontextmanager
from logging import Logger
from shlex import quote
from typing import Any, AsyncIterator, Iterable, Protocol

from jshell.core.pipe import PipeWriter, parse_json
from jshell.core.shell import Shell, ShellProcess
from jshell.systems.unix import Unix


class NSpawn:
    def __init__(self, sh: Shell) -> None:
        self._sh = sh

    def get_machine_shell(self, name: str, logger: Logger | None = None) -> Shell:
        return _NSpawnMachineShell(self._sh, name, logger=logger)

    @asynccontextmanager
    async def configure(self) -> AsyncIterator["NSpawnConfig"]:
        config = _NSpawnConfig()
        yield config
        os = Unix()
        all_machines = set(it["name"] for it in await self._run("list-images"))
        running_machines = set(it["machine"] for it in await self._run("list"))

        for machine in all_machines - set(it.name for it in config.machines):
            if machine in running_machines:
                await self._sh(f"machinectl poweroff {machine}")
            await self._sh(f"machinectl remove {machine}")

        for machine in [it for it in config.machines if it.name not in all_machines]:
            await self._sh(
                f"machinectl pull-tar --verify=checksum {machine.image_url} {machine.name}"
            )

        async with os.sync(self._sh) as batch:
            for machine in config.machines:
                batch.add(f"/etc/systemd/nspawn/{machine.name}.nspawn", machine.config)

        for machine in config.machines:
            await self._sh(f"machinectl enable {machine.name}")

        await self._sh("systemctl daemon-reload")
        await self._sh("systemctl restart machines.target")

    async def _run(self, command: str) -> Any:
        return await (self._sh(f"machinectl --output json {command}") | parse_json())


class NSpawnConfig(Protocol):
    def add_machine(self, name: str, base_image: str, config: str | bytes) -> None:
        pass


class _MachineConfig:
    def __init__(self, name: str, image_url: str, config: bytes) -> None:
        self._name = name
        self._image_url = image_url
        self._config = config

    @property
    def name(self) -> str:
        return self._name

    @property
    def image_url(self) -> str:
        return self._image_url

    @property
    def config(self) -> bytes:
        return self._config


class _NSpawnConfig:
    def __init__(self) -> None:
        self._machines: list[_MachineConfig] = []

    @property
    def machines(self) -> Iterable[_MachineConfig]:
        return self._machines

    def add_machine(self, name: str, base_image: str, config: str | bytes) -> None:
        if isinstance(config, str):
            config = config.encode("utf-8")
        self._machines.append(_MachineConfig(name, base_image, config))


class _NSpawnMachineShell(Shell):
    def __init__(self, outer: Shell, machine: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._outer = outer
        self._machine = machine

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        return await self._outer._start_process(  # pylint: disable=protected-access
            out,
            err,
            f"systemd-run --pipe --wait --quiet --machine {self._machine} sh -c {quote(command)}",
            env,
        )
