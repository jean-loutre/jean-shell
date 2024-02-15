"""Posix-related implementations :

 * [write_manifest](#jiac.systems.posix.write_manifest) : Allow to synchronize
 a file manifest to a posix-compliant shell, by using standard posix utilities
 such as mkdir, cat, chown, chrgp and chmod.
"""
from jiac.shell import Shell
from jiac.stream import Stream, copy_stream
from jiac.manifest import File, Directory


async def write_manifest(shell: Shell, manifest: dict[str, File | Directory]) -> None:
    """Write the given manifest calling posix tools on the given shell.

    Args:
        shell: Shell on which to execute synchronization commands.
        manifest:
            File manifest, either created by hands from objects in the
            [jiac.manifest](../../manifest) module, or loaded from some source,
            for example with the
            [resources_manifest](../../resources#jiac.resources.resources_manifest)
            function.
    """
    directories = [
        (target, item)
        for target, item in manifest.items()
        if isinstance(item, Directory)
    ]

    files = [
        (target, item) for target, item in manifest.items() if isinstance(item, File)
    ]

    directories = sorted(directories, key=lambda it: len(it[0]), reverse=True)
    synced_paths: set[str] = set()

    stdin: Stream | None = None

    async def _send(command: str) -> None:
        assert stdin is not None
        await stdin.write(command.encode("utf-8"))

    async with shell("sh").write_stdin() as stdin:
        for destination_path, directory in directories:
            if all(not it.startswith(destination_path) for it in synced_paths):
                await _send(f"mkdir -p {destination_path} || true\n")

            synced_paths.add(destination_path)

    for destination_path, file in files:
        async with file.open() as in_, shell(
            f"cat > {destination_path}"
        ).write_stdin() as out:
            assert out is not None
            await copy_stream(in_, out)

    async with shell("sh").write_stdin() as stdin:
        for destination_path, item in manifest.items():
            user = item.user

            if user:
                await _send(f"chown -R {user} '{destination_path}'\n")

            group = item.group

            if group:
                await _send(f"chgrp -R {group} '{destination_path}'\n")

            mode = item.mode
            if mode:
                await _send(f"chmod -R {mode} '{destination_path}'\n")
