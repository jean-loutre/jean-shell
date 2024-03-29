from typing import Any

from pytest import raises

from jtoto.manifest import Directory, File, SourceDirectory, SourceFile
from jtoto.resources import resources_manifest


async def check_manifest(manifest: dict[str, File | Directory], expected_manifest: dict[str, Any]) -> None:
    for key, value in expected_manifest.items():
        item = manifest[key]
        item_type = value["type"]
        if item_type == "file":
            assert isinstance(item, File)
            async with item.open() as content:
                assert await content.read() == value["content"].encode("utf-8")
            assert item.user == value.get("user", None)
            assert item.group == value.get("group", None)
            assert item.mode == value.get("mode", None)
        elif item_type == "dir":
            assert isinstance(item, Directory)
            assert item.user == value.get("user", None)
            assert item.group == value.get("group", None)
            assert item.mode == value.get("mode", None)
            assert item.clean == value.get("clean", False)
        else:
            assert False


async def test_resource_manifest_file() -> None:
    manifest = resources_manifest(
        {
            "/base_file": SourceFile("base_file", user="peter", group="otters", mode="666"),
            "/steven": SourceFile("steven"),
        },
        "tests.test_resources_data.child",
        "tests.test_resources_data.base",
    )

    def _file(content: str) -> dict[str, Any]:
        return {"type": "file", "content": "base_file content\n"}

    await check_manifest(
        manifest,
        {
            "/base_file": {
                "type": "file",
                "content": "base_file content\n",
                "user": "peter",
                "group": "otters",
                "mode": "666",
            },
            "/steven": {"type": "file", "content": "steven content from child\n"},
        },
    )

    with raises(FileNotFoundError):
        resources_manifest(
            {"/base_file": SourceFile("do-not-exists")},
            "tests.test_resources_data.base",
        )

    with raises(IsADirectoryError):
        resources_manifest(
            {"/base_file": SourceFile("base")},
            "tests.test_resources_data",
        )


async def test_resource_manifest_directory() -> None:
    manifest = resources_manifest(
        {
            "/target": SourceDirectory(
                "subdirectory",
                user="peter",
                group="otters",
                file_mode="666",
                directory_mode="777",
                clean=True,
            )
        },
        "tests.test_resources_data.child",
        "tests.test_resources_data.base",
    )

    def _dir(clean: bool = False) -> dict[str, Any]:
        return {
            "type": "dir",
            "user": "peter",
            "group": "otters",
            "mode": "777",
            "clean": clean,
        }

    def _file(content: str) -> dict[str, Any]:
        return {
            "type": "file",
            "content": content,
            "user": "peter",
            "group": "otters",
            "mode": "666",
        }

    await check_manifest(
        manifest,
        {
            "/target": _dir(clean=True),
            "/target/peter": _file("peter content from child\n"),
            "/target/child_dir": _dir(),
            "/target/child_dir/peter": _file("peter content\n"),
            "/target/base_dir": _dir(),
            "/target/base_dir/peter": _file("peter content\n"),
        },
    )


async def test_resource_manifest_directory_no_source() -> None:
    manifest = resources_manifest(
        {
            "/target": SourceDirectory(
                user="peter",
                group="otters",
                file_mode="666",
                directory_mode="777",
                clean=True,
            )
        },
        "tests.test_resources_data.child",
        "tests.test_resources_data.base",
    )

    def _dir(clean: bool = False) -> dict[str, Any]:
        return {
            "type": "dir",
            "user": "peter",
            "group": "otters",
            "mode": "777",
            "clean": clean,
        }

    await check_manifest(
        manifest,
        {
            "/target": _dir(clean=True),
        },
    )
