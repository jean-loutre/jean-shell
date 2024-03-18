from logging import Logger
from typing import Any
from json import loads

from jtoto.shell import Process, Shell, Stderr, Stdout


class IncusCli(Shell):
    def __init__(
        self,
        host_shell: Shell,
        incus_path: str = "incus",
        project: str | None = None,
        logger: Logger | None = None,
    ) -> None:
        super().__init__(logger=logger)
        self._host_shell = host_shell
        self._logger = logger
        self._incus_path = incus_path
        self._project = project

    async def parse_stdout(self, command: str) -> Any:
        out = bytearray()
        await (self(command) >> out)
        return loads(out.decode("utf-8"))

    async def _start_process(self, out: Stdout, err: Stderr, command: str, env: dict[str, str]) -> Process:
        project_parameter = ""
        if self._project is not None:
            project_parameter = f"--project {self._project} "

        return await self._host_shell._start_process(  # pylint: disable=protected-access
            out,
            err,
            f"{self._incus_path} {project_parameter}{command}",
            env=env,
        )
