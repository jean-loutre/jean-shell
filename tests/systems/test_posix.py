from jtoto.systems.posix import write_manifest
from collections import OrderedDict
from io import BytesIO
from jtoto.manifest import Directory, File
from jtoto.stream import FileInputStream, InputStream
from contextlib import asynccontextmanager
from typing import AsyncIterator
from jtoto.testing import MockShell, check_process, MockProcess


class _MockFile(File):
    def __init__(self, content: str, **kwargs: str | None) -> None:
        super().__init__(**kwargs)
        self._content = content.encode("utf-8")

    @asynccontextmanager
    async def open(self) -> AsyncIterator[InputStream]:
        yield FileInputStream(BytesIO(self._content))


async def test_posix_write_manifest() -> None:
    async def _mock_cli() -> AsyncIterator[MockProcess]:
        yield check_process(
            "sh",
            expected_stdin=("rm -fr /etc/otters/orson-welles\n"),
        )
        yield check_process(
            "sh",
            expected_stdin=("mkdir -p /etc/otters || true\n" "find /etc/otters\n"),
            stdout=b"/etc/otters/orson-welles\n/etc/otters/peter\n",
        )
        yield check_process("cat > /etc/otters/peter", expected_stdin="peter")
        yield check_process("cat > /etc/otters/steven", expected_stdin="steven")
        # fmt: off
        yield check_process(
            "sh",
            expected_stdin=(
                "chown -R peter \'/etc/otters\'\n"
                "chgrp -R otters \'/etc/otters\'\n"
                "chmod -R 755 \'/etc/otters\'\n"
                "chown -R steven \'/etc/otters/steven\'\n"
                "chgrp -R otters \'/etc/otters/steven\'\n"
                "chmod -R 644 \'/etc/otters/steven\'\n"
            ),
        )
        # fmt: on

    async with MockShell(_mock_cli()) as sh:
        await write_manifest(
            sh,
            OrderedDict(
                [
                    ("/etc", Directory()),
                    (
                        "/etc/otters",
                        Directory(user="peter", group="otters", mode="755", clean=True),
                    ),
                    ("/etc/otters/peter", _MockFile("peter")),
                    (
                        "/etc/otters/steven",
                        _MockFile("steven", user="steven", group="otters", mode="644"),
                    ),
                ]
            ),
        )
