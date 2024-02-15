from pytest import raises
from typing import Any

from jiac.manifest import File, SourceFile, Directory, SourceDirectory
from jiac.tools.resources import resources_manifest


async def check_manifest(
    manifest: dict[str, File | Directory], expected_manifest: dict[str, Any]
) -> None:
    for key, value in expected_manifest.items():
        item = manifest[key]
        item_type = value["type"]
        if item_type == "file":
            assert isinstance(item, File)
            async with item.open() as content:
                assert await content.read() == value["content"].encode("utf-8")
        elif item_type == "dir":
            assert isinstance(item, Directory)
        else:
            assert False


async def test_resource_manifest_file() -> None:
    manifest = resources_manifest(
        {"/base_file": SourceFile("base_file"), "/steven": SourceFile("steven")},
        "tests.tools.test_resources_data.child",
        "tests.tools.test_resources_data.base",
    )

    await check_manifest(
        manifest,
        {
            "/base_file": {"type": "file", "content": "base_file content\n"},
            "/steven": {"type": "file", "content": "steven content from child\n"},
        },
    )

    with raises(FileNotFoundError):
        resources_manifest(
            {"/base_file": SourceFile("do-not-exists")},
            "tests.tools.test_resources_data.base",
        )

    with raises(IsADirectoryError):
        resources_manifest(
            {"/base_file": SourceFile("base")},
            "tests.tools.test_resources_data",
        )


async def test_resource_manifest_directory() -> None:
    manifest = resources_manifest(
        {"/target": SourceDirectory("subdirectory")},
        "tests.tools.test_resources_data.child",
        "tests.tools.test_resources_data.base",
    )

    await check_manifest(
        manifest,
        {
            "/target": {"type": "dir"},
            "/target/peter": {"type": "file", "content": "peter content from child\n"},
            "/target/child_dir": {"type": "dir"},
            "/target/child_dir/peter": {"type": "file", "content": "peter content\n"},
            "/target/base_dir": {"type": "dir"},
            "/target/base_dir/peter": {"type": "file", "content": "peter content\n"},
        },
    )
