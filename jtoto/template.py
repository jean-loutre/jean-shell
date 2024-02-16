from typing import Any, AsyncIterator
from jinja2 import Environment, BaseLoader, PackageLoader, PrefixLoader, ChoiceLoader

from contextlib import asynccontextmanager
from io import BytesIO
from dataclasses import dataclass, field
from jtoto.manifest import SourceFile, File
from jtoto.stream import FileInputStream, InputStream


@dataclass(frozen=True)
class Template(SourceFile):
    """Item of a manifest representing a template to expand."""

    context: dict[str, Any] = field(default_factory=dict)


def template_manifest(
    manifest: dict[str, Template],
    *anchors: str,
    environment: Environment | None = None,
) -> dict[str, File]:
    """Expand a template manifest from python package resources.

    Will convert a dictionnary of [destination_path,Template] to a dictionnary
    of [destination_path, File] that can be used to write files on a remote
    system.

    Args:
        manifest: Dictionnary file destination / Template descriptor.

        *anchors:
            If specified, templates will be loaded from this packages, using
            PackageLoader. Parent packages templates are accessible in child
            package templates, under the prefix "parent" : see documentation
            (TODO) for further informations.

        environment: Base jinja2 environment to use for template expansion.

    Returns:
        The expanded manifest.
    """
    if environment is None:
        environment = Environment()

    environment = environment.overlay(enable_async=True, loader=_get_loader(*anchors))

    return {
        target: _TemplateFile(
            tpl.path,
            environment,
            tpl.context,
            user=tpl.user,
            group=tpl.group,
            mode=tpl.mode,
        )
        for target, tpl in manifest.items()
    }


class _TemplateFile(File):
    def __init__(
        self,
        template: str,
        environment: Environment,
        context: dict[str, Any],
        **kwargs: str | None,
    ) -> None:
        super().__init__(**kwargs)
        self._template = template
        self._environment = environment
        self._context = context

    @asynccontextmanager
    async def open(self) -> AsyncIterator[InputStream]:
        template = self._environment.get_template(self._template)
        rendered = await template.render_async(**self._context)
        bytes_io = BytesIO(rendered.encode("utf-8"))
        yield FileInputStream(bytes_io)


def _get_loader(
    *anchors: str,
) -> BaseLoader | None:
    loader: BaseLoader | None = None
    for anchor in reversed(anchors):
        current_loader = PackageLoader(anchor, package_path="")
        if loader is None:
            loader = current_loader
        else:
            loader = ChoiceLoader(
                [current_loader, loader, PrefixLoader({"parent": loader})]
            )

    return loader
