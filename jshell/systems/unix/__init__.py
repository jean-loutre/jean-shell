from pathlib import Path
from typing import AsyncIterator

from jshell.core.resource import Resource, resource
from jshell.core.shell import Shell, ShellPipe
from jshell.systems.os import Os


@resource
async def unix_os(sh: Resource[Shell]) -> AsyncIterator[Os]:
    async with sh as sh_:
        yield Unix(sh_)


class Unix(Os):
    def make_directory(self, path: str | Path) -> ShellPipe:
        return self._sh(f"mkdir -p {path}", raise_on_error=False)

    def write_file(self, path: str | Path) -> ShellPipe:
        return self._sh(f"cat > {path}")
