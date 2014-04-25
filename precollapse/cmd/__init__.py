

from . import collections, db, shell, entries

def register_commands(manager):
    manager.log.debug("register base commands")
    for mod in [collections, db, shell, entries]:
        for cmd in mod.__all__:
            manager.register_command(cmd)
