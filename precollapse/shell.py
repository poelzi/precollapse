import logging, logging.config
import sys

from gettext import gettext as _
from cliff.app import App
from cliff.commandmanager import CommandManager
from .__init__ import VERSION
from . import utils
import os, sys
import readline
import configparser
from . import db

CONFIG_FILE = "~/.config/precollapse/precollapse.conf"
CONFIG_PATH = "~/.config/precollapse"
CACHE_PATH = "~/.cache/precollapse"


class PrecollapseApp(App):

    log = logging.getLogger(__name__)

    def __init__(self, manager):
        #self.get_plugins()
        self.pwd = "/"
        self.manager = manager
        self.config = None

        super(PrecollapseApp, self).__init__(
            description=_('collection download and sharing tool'),
            version=VERSION,
            command_manager=CommandManager('precollapse.cmd'),
            interactive_app_factory=self._interactive_factory
        )

    def _interactive_factory(self, *args, **kwargs):
        # create a interactiveapp but adjust it
        from cliff.interactive import InteractiveApp
        rv = InteractiveApp(*args, **kwargs)
        rv.prompt = utils.get_prompt(self.pwd)
        return rv

    def set_pwd(self, path):
        """
        sets the working directory of the interactive prompt
        """
        self.pwd = path
        if self.interpreter:
            self.interpreter.prompt = utils.get_prompt(path)

    def build_option_parser(self, *args, **kwargs):
        parser = super(PrecollapseApp, self).build_option_parser(*args, **kwargs)
        parser.add_argument(
            '--config', '-c',
            default=CONFIG_FILE,
            action='store',
            metavar='config',
            help='use config file',
            )
        parser.add_argument(
            '--state',
            default=CONFIG_PATH,
            action='store',
            metavar='state',
            help='use state directory',
            )
        parser.add_argument(
            '--cache',
            default=CACHE_PATH,
            action='store',
            metavar='cache',
            help='use cache directory',
            )
        parser.add_argument(
            '--full-debug',
            default=False,
            action='store_true',
            help="set debug on subsystems")
        return parser


    def create_config_dir(self):
        self.state_path = os.path.expanduser(self.options.state)
        os.makedirs(self.state_path, exist_ok=True)
        self.cache_path = os.path.expanduser(self.options.cache)
        os.makedirs(self.cache_path, exist_ok=True)

    def get_cache_dir(self, backend):
        return os.path.join(self.cache_path, backend.name)

    def get_state_dir(self, backend):
        return os.path.join(self.cache_path, backend.name)


    #def get_plugins(self):
        #print("-"*20)
        #for pluginInfo in allPlugins.getAllPlugins():
            #print(pluginInfo)
            #allPlugins.activatePluginByName(pluginInfo.name)
            #print(allPlugins.getPluginByName(pluginInfo.name, category='Default'))

    def load_history(self):
        if not self.interactive_mode:
            return
        rpath = os.path.expanduser(os.path.join(self.options.state, "history" ))
        try:
            readline.read_history_file(rpath)
        except:
            pass

    def save_history(self):
        if not self.interactive_mode:
            return
        rpath = os.path.expanduser(os.path.join(self.options.state, "history" ))
        try:
            readline.write_history_file(rpath)
        except:
            pass

    def load_config(self):
        """load config files"""
        self.config = config = configparser.ConfigParser()

        default = os.path.join(os.path.dirname(__file__), "default.conf")
        path = os.path.expanduser(self.options.config)

        read = config.read([default, path])
        self.log.debug("read config files: %s" %read)
        #logging.config.fileConfig(config, disable_existing_loggers=True)
        #if path:
        #    logging.config.fileConfig(path, disable_existing_loggers=False)



    def initialize_app(self, argv):
        self.log.debug('initialize precollapse')
        self.create_config_dir()
        self.load_history()
        self.load_config()
        db.configure_engine(self.config.get("main", "database"))
        #self.manager.download_manager.start()
        #embed()


    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('got an error: %s', err)
        self.save_history()

