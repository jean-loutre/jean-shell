from typing import Any

from jshell.systems.lxd.object import LxcCommand, Object


class Network(Object):
    """LXD Network object"""

    subcommand = "network"
    ignore_keys = ("type",)

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)

    async def create(self, lxc: LxcCommand) -> None:
        if self.type:
            await lxc(f"network create {self.name} --type={self.type}")
        else:
            await lxc(f"network create {self.name}")

    async def delete(self, lxc: LxcCommand) -> None:
        if self.managed:
            await super().delete(lxc)
