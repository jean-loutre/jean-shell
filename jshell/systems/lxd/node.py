from asyncio import gather
from shlex import quote
from typing import Any, Callable, Iterable, Type, TypeVar

from jshell.core.pipe import PipeWriter
from jshell.core.shell import Shell, ShellPipe, ShellProcess
from jshell.systems.lxd.instance import Instance
from jshell.systems.lxd.network import Network
from jshell.systems.lxd.object import Object
from jshell.systems.lxd.profile import Profile
from jshell.systems.lxd.project import Project
from jshell.systems.lxd.storage import Storage

Self = TypeVar("Self", bound="Object")


class Node:
    """LXDConfiguration settings."""

    def __init__(
        self,
        lxc_path: str = "lxc",
        project: Project | None = None,
        storages: Iterable[Storage] | None = None,
        instances: Iterable[Instance] | None = None,
        networks: Iterable[Network] | None = None,
        profiles: Iterable[Profile] | None = None,
    ) -> None:
        self._lxc_path = lxc_path
        self._project = project
        self._storages = list(storages or [])
        self._instances = list(instances or [])
        self._networks = list(networks or [])
        self._profiles = list(profiles or [])

    async def configure(self, sh: Shell) -> None:
        if not self._instances:
            return

        lxc = self._get_lxc_runner(sh)

        async def _sync(cls: Type[Self], objects: Iterable[Self]) -> None:
            async with cls.synchronize(lxc, objects):
                pass

        if self._project is not None:
            await _sync(Project, [self._project])

        async with Instance.synchronize(lxc, self._instances):
            await gather(
                _sync(Network, self._networks),
                _sync(Profile, self._profiles),
                _sync(Storage, self._storages),
            )

    async def get_container_shell(
        self, host_shell: Shell, name: str, **kwargs: Any
    ) -> Shell:
        return _ContainerShell(self._lxc_path, host_shell, name, project=self._project**kwargs)

    def _get_lxc_runner(self, host_shell: Shell) -> Callable[[str], ShellPipe]:
        def _run(command: str) -> ShellPipe:
            if self._project is None:
                return host_shell(f"{self._lxc_path} {command}")
            else:
                return host_shell(
                    f"{self._lxc_path} --project {self._project.name} {command}"
                )

        return _run


class _ContainerShell(Shell):
    def __init__(
            self, lxc_path: str, host_shell: Shell, container_name: str, project: Project | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._lxc_path = lxc_path
        self._project = project
        self._host_shell = host_shell
        self._name = container_name

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        env_parameters = " ".join(
            [f"--env {key}={quote(value)}" for key, value in env.items()]
        )

        return await self._host_shell._start_process(  # pylint: disable=protected-access
            out,
            err,
            f"{self._lxc_path} exec {self._name} {env_parameters} -- sh -c {quote(command)}",
            env={},
        )
