import pkgutil
import os
import importlib
from .. import base

# find all cmd modules and load them
modules = []
for x, name, x in list(pkgutil.iter_modules([os.path.dirname(__file__)])):
    mod = importlib.import_module('precollapse.cmd.%s' %name)
    modules.append(mod)

def register_commands(manager):
    manager.log.debug("register base commands")
    for mod in modules:
        for name,cls in mod.__dict__.items():
            try:
                if issubclass(cls, base.all_commands) and \
                    cls not in base.all_commands:
                    manager.register_command(cls)
            except TypeError:
                pass
