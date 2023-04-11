from jshell.systems.lxd.object import Object


class Network(Object):
    """LXD Network object"""

    subcommand = "network"
    ignore_keys = ("type",)
