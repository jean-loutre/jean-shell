from typing import Any

from jshell.systems.lxd.object import LxcCommand, Object


class Instance(Object):
    """LXD Project settings"""

    subcommand = ""
    ignore_keys = ("image",)

    def __init__(self, name: str, image: str = "", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._image = image

    async def create(self, lxc: LxcCommand) -> None:
        await (self._dump() | lxc(f"launch {self._image} {self.name}"))

    async def delete(self, lxc: LxcCommand) -> None:
        await lxc(f"delete --force {self.name}")

    async def save(self, lxc: LxcCommand) -> None:
        await (self._dump() | lxc(f"config edit {self.name}"))
        if self.status == "Stopped":
            await lxc(f"start {self.name}")
