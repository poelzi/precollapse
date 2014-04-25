import sys
import logging
import os, os.path

from yapsy.PluginManager import PluginManager
from precollapse import exceptions
from .shell import PrecollapseApp
from .cmd import register_commands
from IPython import embed
from . import db


class CollapseManager(PluginManager):
    def __init__(self):
        self._commands = []
        self._backends = {}
        logging.basicConfig()
        self.log = logging.root
        self.log.setLevel(logging.DEBUG)
        self.app = PrecollapseApp(self)
        super(CollapseManager, self).__init__()
        self.setPluginPlaces(["precollapse/plugins"])
        # register base commands
        register_commands(self)
        self.collectPlugins()
        self.load_all()



    def register_command(self, cmd):
        self.log.debug("register command %s", cmd)
        self.app.command_manager.add_command(cmd.name, cmd)
        #self.app.command_manager.commands

    def register_backend(self, backend):
        self.log.debug("register backend %s", backend)


    def load_all(self):
        # Activate all loaded plugins
        for pluginInfo in self.getAllPlugins():
            print(pluginInfo)
            print(pluginInfo.name)
            self.activatePluginByName(pluginInfo.name)
            try:
                plug = pluginInfo.plugin_object
                plug.check()
                plug.register_commands(self)
                plug.register_backends(self)
            except exceptions.CommandMissing as e:
                self.log.warning("missing command: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)
            except Exception as e:
                import traceback
                traceback.print_exc(e)
                self.log.warning("error loading plugin: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)

    def run_shell(self, argv):
        return self.app.run(argv)

# create singleton
manager = CollapseManager()


def main(argv=sys.argv[1:]):
    return manager.run_shell(argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
