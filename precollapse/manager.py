import sys
import logging
import os, os.path

from yapsy.PluginManager import PluginManager
from precollapse import exceptions
from .shell import PrecollapseApp
from .cmd import register_commands
from IPython import embed
from . import db, base


class CollapseManager(PluginManager):
    def __init__(self):
        self._commands = []
        self._backends = {}
        logging.basicConfig()
        self.log = logging.root
        #self.log.setLevel(logging.DEBUG)
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

    def register_backend(self, name, backend):
        if name in self._backends:
            self.log.error("plugin already registered: %s", name)
            return
        self.log.info("register backend %s:%s" %(name, backend))
        self._backends[name] = backend(self)

    def get_backend_for_entry(self, entry):
        """
        Returns the best backend for the entry.
        Returns a tuple (backend, priority)
        """

        best = None
        points = base.UrlWeight.unable
        for backend in self._backends.values():
            r = backend.weight_entry(entry)
            if r > points:
                points = r
                best = backend
        return (best, points)

    def get_backend(self, name):
        return self._backends.get(name, None)

    def get_all_backends(self):
        return self._backends.values()

    def load_all(self):
        # Activate all loaded plugins
        best_dl = base.DownloadManager
        for pluginInfo in self.getAllPlugins():
            print(pluginInfo)
            print(pluginInfo.name)
            self.activatePluginByName(pluginInfo.name)
            try:
                plug = pluginInfo.plugin_object
                print(plug)
                plug.check()
                plug.register_commands(self)
                plug.register_backends(self)
                if plug.download_manager:
                    if not best_dl or plug.quality > best_dl.quality:
                        best_dl = plug.download_manager
            except exceptions.CommandMissing as e:
                self.log.warning("missing command: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)
            except Exception as e:
                import traceback
                traceback.print_exc(e)
                self.log.warning("error loading plugin: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)
        # initialize DownloadManager
        self.download_manager = best_dl(self)

    def run_shell(self, argv):
        return self.app.run(argv)

# create singleton
manager = None


def main(argv=sys.argv[1:]):
    global manager
    manager = CollapseManager()
    return manager.run_shell(argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
