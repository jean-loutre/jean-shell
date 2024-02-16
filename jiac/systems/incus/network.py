from jiac.systems.incus.object import Object


class Network(Object):
    """Incus Network object"""

    subcommand = "network"
    config_subcommand = "network"
    ignore_keys = ("type",)
