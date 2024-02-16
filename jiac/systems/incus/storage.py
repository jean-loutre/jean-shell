from jiac.systems.incus.object import Object


class Storage(Object):
    """Incus Project settings"""

    subcommand = "storage"
    config_subcommand = "storage"
    ignore_keys = ("driver",)
