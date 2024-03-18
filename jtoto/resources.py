"""Utilities to deal with python package resources."""
from jtoto.manifest import File, SourceFile, Directory, SourceDirectory
from contextlib import asynccontextmanager
from jtoto import FileInputStream, InputStream
from os.path import relpath, join, normpath
from typing import AsyncIterator, Iterable, Iterator
from importlib.resources import Package, files
from importlib.resources.abc import Traversable


class _ResourcesFile(File):
    def __init__(self, resource: Traversable, **kwargs: str | None) -> None:
        super().__init__(**kwargs)
        self._resource = resource

    @asynccontextmanager
    async def open(self) -> AsyncIterator[InputStream]:
        with self._resource.open("rb") as resource:
            yield FileInputStream(resource)


def resources_manifest(
    input_manifest: dict[str, SourceFile | SourceDirectory], *anchors: Package
) -> dict[str, File | Directory]:
    """Expand a file manifest from python resources.

    Args:
        input_manifest: The manifest to expand.

    Returns:
        The expanded manifest.
    """
    roots = [files(anchor) for anchor in anchors]
    result_manifest: dict[str, File | Directory] = {}
    for target, item in input_manifest.items():
        if isinstance(item, SourceFile):
            result_manifest[target] = _load_file(roots, item)
        elif isinstance(item, SourceDirectory):
            result_manifest |= {
                normpath(join(target, child_target)): item
                for child_target, item in _load_directory(roots, item)
            }

    return result_manifest


def _load_file(roots: list[Traversable], file: SourceFile) -> File:
    for root in roots:
        resource_file = root.joinpath(file.path)
        if resource_file.is_dir():
            raise IsADirectoryError(file.path)
        elif not resource_file.is_file():
            continue

        return _ResourcesFile(resource_file, user=file.user, group=file.group, mode=file.mode)

    raise FileNotFoundError(file.path)


def _load_directory(
    roots: list[Traversable], directory: SourceDirectory
) -> Iterator[tuple[str, File | Directory]]:
    if directory.path is None:
        yield (
            ".",
            Directory(
                user=directory.user,
                group=directory.group,
                mode=directory.directory_mode,
                clean=directory.clean,
            ),
        )
        return
    for root in reversed(roots):
        source_directory = root / directory.path
        for child in _recursive_list(source_directory):
            child_target_path = relpath(str(child), str(source_directory))
            if child.is_file():
                item: File | Directory = _ResourcesFile(
                    child,
                    user=directory.user,
                    group=directory.group,
                    mode=directory.file_mode,
                )
            else:
                # Only clean topmost directory
                clean = child_target_path == "." and directory.clean
                item = Directory(
                    user=directory.user,
                    group=directory.group,
                    mode=directory.directory_mode,
                    clean=clean,
                )
            yield child_target_path, item


def _recursive_list(directory: Traversable) -> Iterable[Traversable]:
    yield directory
    if directory.is_dir():
        for child in directory.iterdir():
            yield from _recursive_list(child)
