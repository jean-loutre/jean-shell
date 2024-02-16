from typing import Any

from jiac.manifest import File
from jiac.template import template_manifest, Template


async def check_manifest(
    manifest: dict[str, File], expected_manifest: dict[str, Any]
) -> None:
    for key, value in expected_manifest.items():
        item = manifest[key]
        assert isinstance(item, File)
        async with item.open() as content:
            assert await content.read() == value["content"].encode("utf-8")
        assert item.user == value.get("user", None)
        assert item.group == value.get("group", None)
        assert item.mode == value.get("mode", None)


async def test_resource_manifest_file() -> None:
    manifest = template_manifest(
        {
            "/steven": Template(
                "steven.j2",
                user="peter",
                group="otters",
                mode="666",
                context={"name": "steven"},
            ),
            "/peter": Template("peter.j2", context={"name": "peter"}),
        },
        "tests.test_template_data.child",
        "tests.test_template_data.base",
    )

    await check_manifest(
        manifest,
        {
            "/steven": {
                "content": "name is steven from base\nname is steven from child",
                "user": "peter",
                "group": "otters",
                "mode": "666",
            },
            "/peter": {"content": "name is peter"},
        },
    )
