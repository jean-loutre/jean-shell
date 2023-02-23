from typing import Any

from jshell.systems.lxd.object import LxcCommand, Object


class Storage(Object):
    """LXD Project settings"""

    subcommand = "storage"
    ignore_keys = ("driver",)

    def __init__(self, name: str, driver: str, **kwargs: Any) -> None:
        super().__init__(name, driver=driver, **kwargs)

    async def create(self, lxc: LxcCommand) -> None:
        await lxc(f"storage create {self.name} {self.driver}")

    async def delete(self, lxc: LxcCommand) -> None:
        if not self.used_by:
            await super().delete(lxc)
