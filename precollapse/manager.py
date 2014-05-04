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
        self._download_managers = {"plain": base.DownloadManager}
        self._default_dl = None
        self._dl_instance = {}
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

    def get_download_manager(self, collection):
        if collection.id in self._dl_instance:
            return self._dl_instance[collection.id]
        else:
            ndm = None
            if collection.download_manager:
                ndm = self.get_download_manager_class(collection.download_manager)
            if not ndm:
                if not self._default_dl:
                    # load default dl manager setting
                    self._default_dl = self.get_download_manager_class(
                          self.app.config.get("DEFAULT", "download_manager", fallback=None)
                        )
                if not self._default_dl:
                    # find best one
                    choices = list(self._download_managers.values())
                    choices.sort(key=lambda x: x.quality, reverse=True)
                    self._default_dl = choices[0]
                self.log.info("choose default download manager: %s", self._default_dl.name)
                ndm = self._default_dl
            dlp = collection.download_path
            if not dlp:
                dlp = os.path.expanduser(self.app.config.get("main", "download_dir"))
                if dlp != os.path.sep:
                    dlp = os.path.join(os.getcwd(), dlp)
                dlp = os.path.join(dlp, collection.basename)

            self._dl_instance[collection.id] = dlm = ndm(self, download_path=dlp)
            dlm.start()
            return dlm

    def get_download_manager_class(self, name):
        return self._download_managers.get(name, None)



    def load_all(self):
        # Activate all loaded plugins
        #best_dl = base.DownloadManager
        for pluginInfo in self.getAllPlugins():
            self.activatePluginByName(pluginInfo.name)
            try:
                plug = pluginInfo.plugin_object
                plug.check()
                plug.register_commands(self)
                plug.register_backends(self)
                if plug.download_manager:
                    assert plug.download_manager.name
                    if plug.download_manager.name in self._download_managers:
                        self.log.error("download manager with name %s already registered", plug.download_manager.name)
                    else:
                        self._download_managers[plug.download_manager.name] = plug.download_manager
            except exceptions.CommandMissing as e:
                self.log.warning("missing command: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)
            except Exception as e:
                import traceback
                traceback.print_exc(e)
                self.log.warning("error loading plugin: %s, disable plugin: %s" %(e, pluginInfo.name))
                deactivatePluginByName(pluginInfo.name)
        # initialize DownloadManager
        #self.download_manager = best_dl(self)

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
