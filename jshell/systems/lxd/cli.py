from logging import Logger

from jshell.core.pipe import PipeWriter
from jshell.core.shell import Shell, ShellProcess


class LxcCli(Shell):
    def __init__(
        self,
        host_shell: Shell,
        lxc_path: str = "lxc",
        project: str | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(logger=logger)
        self._host_shell = host_shell
        self._logger = logger
        self._lxc_path = lxc_path
        self._project = project

    async def _start_process(
        self, out: PipeWriter, err: PipeWriter, command: str, env: dict[str, str]
    ) -> ShellProcess:
        project_parameter = ""
        if self._project is not None:
            project_parameter = f"--project {self._project} "

        return (
            await self._host_shell._start_process(  # pylint: disable=protected-access
                out,
                err,
                f"{self._lxc_path} {project_parameter}{command}",
                env=env,
            )
        )
