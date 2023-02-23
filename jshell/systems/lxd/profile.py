from jshell.systems.lxd.object import LxcCommand, Object


class Profile(Object):
    """LXD Project settings"""

    subcommand = "profile"

    async def delete(self, lxc: LxcCommand) -> None:
        if self.name != "default":
            await super().delete(lxc)
