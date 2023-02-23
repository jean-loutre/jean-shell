from jshell.systems.lxd.object import LxcCommand, Object


class Project(Object):
    """LXD Project settings"""

    subcommand = "project"

    async def delete(self, _: LxcCommand) -> None:
        # Don't delete unreferenced projects. This allow to manage only specific
        # projects with jshell, while others are managed in a different way, without
        # jshell deleting unreferenced instances from them.
        return
