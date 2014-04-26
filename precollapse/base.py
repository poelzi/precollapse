from yapsy.IPlugin import IPlugin
from cliff.command import Command as cCommand
from cliff.show import ShowOne as cShowOne
from cliff.lister import Lister as cLister
import enum
import asyncio
import os
import os.path
import logging
from IPython import embed

class UrlWeight(enum.Enum):
    prefect   = 80
    very_good = 70
    good      = 60
    normal    = 50
    bad       = 40
    very_bad  = 30
    unable    = -1

    def __lt__(self, other):
        if isinstance(other, UrlWeight):
            return self.value < other.value
        return self.value < other
    def __gt__(self, other):
        if isinstance(other, UrlWeight):
            return self.value > other.value
        return self.value > other

class Backend(object):
    log = logging.getLogger(__name__)

    def __init__(self, manager):
        self.manager = manager

    def weight_entry(self, entry):
        return UrlWeight.unable

    def handle_entry(self, entry):
        """
        Passed a Entry instance from the sheduler daemon that should
        be processed by the backend.
        """
        raise NotImplemented

    def get_arguments(self):
        return None

    def get_progress(self, entry):
        return -2

    def get_all_jobs(self):
        return self.jobs

    def start_backend(self, daemon):
        self.daemon = daemon

class CommandBackend(Backend):
    """
    Backend that implements usage command arguments to spawn
    """
    @asyncio.coroutine
    def handle_entry(self, entry):
        args = self.get_command_args(entry)


        self.log.debug("run command: %s" %args)
        job = yield from asyncio.create_subprocess_exec(*args, stdin=None,
                                             stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE)
        #task = asyncio.Task(job)


        self.jobs.append(job)
        stdout, stderr = yield from job.communicate()
        embed()

        #self.daemon.loop.call_soon(task)
        exitcode = yield from job.wait()
        if exitcode == 0:
            entry.set_success()
        else:
            entry.set_error(stderr)

        #embed()

    def get_command_args(self, entry):
        raise NotImplemented

    def start_backend(self, daemon):
        self.daemon = daemon
        self.jobs = []

class DownloadManager(object):
    """
    Simple download manager for flat files
    """
    quality = 0

    def __init__(self, manager):
        self.manager = manager
        self.download_path = None

    def start(self):
        self.download_path = os.path.expanduser(self.manager.app.config.get("main", "download_dir"))
        if self.download_path[0] != os.path.sep:
            self.download_path = os.path.join(os.getcwd(), self.download_path)
        os.makedirs(self.download_path,
                    exist_ok=True)


    def prepare_entry(self, entry, relpath=None):
        """
        Prepare everything for the file to be added to the collection.
        relpath is determined by the backend

        returns absolute path
        """
        col = entry.collection_id
        #embed()
        if isinstance(col, int):
            from .db import create_session, model
            session = create_session()
            col = session.query(model.Collection).filter(model.Collection.id==col).one()

        if not col:
            raise ValueError("entries collection can't be None")

        rv = os.path.join(self.download_path, col.name, entry.full_path[1:])
        os.makedirs(rv,
                    exist_ok=True)
        return rv




    def entry_done(self, entry, ):
        """
        Mark file to be successfull downloaded
        """
        pass

class Plugin(IPlugin):
    commands = []
    backends = []
    download_manager = None


    def check(self):
        return None

    def register_commands(self, manager):
        for cmd in self.commands:
            manager.register_command(cmd)

    def register_backends(self, manager):
        for back in self.backends:
            manager.register_backend(back.name, back)

class CmdMixin(object):
    def get_parser(self, prog_name):
        try:
            args = self.__getattribute__("PARAMETERS")
        except AttributeError:
            args = []
        # search for the real implementation class
        # and get the parser
        bclass = self.__class__.__bases__[0]
        rclass = bclass.__bases__[-1]
        parser = rclass.get_parser(self, prog_name)
        for arg in args:
            kw = arg[-1]
            ar = arg[:-1]
            if not isinstance(kw, dict):
                ar = ar + (kw,)
                kw = {}
            parser.add_argument(*ar, **kw)
        return parser


class Command(CmdMixin, cCommand):
    pass

class ShowOne(CmdMixin, cShowOne):
    pass

class Lister(CmdMixin, cLister):
    pass

all_commands = (Command, ShowOne, Lister)
