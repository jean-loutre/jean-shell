from pathlib import Path

from jshell.core.shell import Shell, ShellPipe
from jshell.systems.os import Os


class Unix(Os):
    def make_directory(self, sh: Shell, path: str | Path) -> ShellPipe:
        return sh(f"mkdir -p {path}", raise_on_error=False)

    def write_file(self, sh: Shell, path: str | Path) -> ShellPipe:
        return sh(f"cat > {path}")
