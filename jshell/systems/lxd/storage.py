from jshell.systems.lxd.object import Object


class Storage(Object):
    """LXD Project settings"""

    subcommand = "storage"
    ignore_keys = ("driver",)
