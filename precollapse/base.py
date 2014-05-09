from yapsy.IPlugin import IPlugin
from cliff.command import Command as cCommand
from cliff.show import ShowOne as cShowOne
from cliff.lister import Lister as cLister
import enum
import asyncio
import os
import io
import os.path
import logging
from IPython import embed

class UrlWeight(enum.Enum):
    prefect   = 80
    very_good = 70
    good      = 60
    likely    = 55
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

    def do_entry(self, entry):
        from .db import create_session
        session = create_session()
        session.add(entry)
        rv = asyncio.Future()
        try:
            asyncio.Task(self.handle_entry(rv, entry))
        except Exception as e:
            self.log.exception(e)
            session.rollback()
        # autocommit when entry was successfull
        def commit(ftr):
            session.commit()
        rv.add_done_callback(commit)
        return rv

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

    def success(self, entry, msg):
        entry.set_success(msg)

    def failure(self, entry, msg):
        entry.set_error(msg)

class CommandBackend(Backend):
    """
    Backend that implements usage command arguments to spawn
    """

    encoding = "utf-8"
    valid_rc = [0]

    def update_msg(self, entry, buffer_, stderr=False):
        if entry not in self.buffers:
            self.buffers[entry] = [io.StringIO(), io.StringIO()]
        i = stderr and 1 or 0
        if isinstance(buffer_, bytes):
            try:
                self.buffers[entry][i].write(buffer_.decode(self.encoding, "replace"))
            except UnicodeError as e:
                pass
        else:
            self.buffers[entry][i].write(buffer_)
        try:
            self.process_update(entry, self.buffers[entry][i], stderr)
        except Exception as e:
            self.log.exception(e)

    def process_update(self, entry, buffer_, strderr=False):
        pass

    def task_done(self, entry, stderr=False, returncode=None, future=None):
        # update entry
        if returncode is not None and not future.done():
            self.log.info("task done %s rc:%s", entry, returncode)
            if returncode in self.valid_rc:
                super(CommandBackend, self).success(entry, self.buffers[entry][1].getvalue())
                if future:
                    future.set_result((entry, True))
            else:
                super(CommandBackend, self).failure(entry, self.buffers[entry][1].getvalue())
                if future:
                    future.set_result((entry, False))
        if stderr:
            self.buffers[entry][1].truncate()
            self.buffers[entry][1].close()
        else:
            self.buffers[entry][0].truncate()
            self.buffers[entry][0].close()
        if self.buffers[entry][0].closed and self.buffers[entry][1].closed:
            del self.buffers[entry]
            del self.jobs[entry]

    def handle_entry(self, future, entry):
        args = yield from self.get_command_args(entry)

        self.log.debug("run command: %s" %args)
        job = yield from asyncio.create_subprocess_exec(*args, stdin=None,
                                             stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.PIPE)
        #task = asyncio.Task(job)
        @asyncio.coroutine
        def read_stdout(job):
            try:
                while True:
                    data = yield from job.stdout.read()
                    if not data:
                        self.task_done(entry, returncode=job.returncode, future=future)
                        return
                    self.update_msg(entry, data)
            except Exception as e:
                self.log.exception(e)
                self.task_done(entry, stderr=True, returncode=job.returncode, future=future)

        @asyncio.coroutine
        def read_stderr(job):
            try:
                while True:
                    data = yield from job.stderr.read(10)
                    if not data:
                        self.task_done(entry, stderr=True, returncode=job.returncode, future=future)
                        return
                    self.update_msg(entry, data, stderr=True)
            except Exception as e:
                self.log.exception(e)
                self.task_done(entry, stderr=True, returncode=job.returncode, future=future)

        asyncio.Task(read_stdout(job))
        asyncio.Task(read_stderr(job))
        self.jobs[entry] = job
        #tsk = asyncio.Task(job.wait())

    def get_command_args(self, entry):
        raise NotImplemented

    def start_backend(self, daemon):
        self.daemon = daemon
        self.jobs = {}
        self.buffers = {}

class DownloadManager(object):
    """
    Simple download manager for flat files
    """
    quality = 0
    name = "plain"

    def __init__(self, manager, download_path, collection=None):
        assert download_path
        self.manager = manager
        self.download_path = download_path
        self.collection = collection

    @asyncio.coroutine
    def start(self):
        #FIXME async this
        os.makedirs(self.download_path, exist_ok=True)


    @asyncio.coroutine
    def prepare_entry(self, entry, relpath=None):
        """
        Prepare everything for the file to be added to the collection.
        relpath is determined by the backend

        returns absolute path
        """
        print(entry.system_path)
        rv = os.path.join(self.download_path, entry.system_path)
        os.makedirs(rv,
                    exist_ok=True)
        return rv

    def _rm_recrusive(self, path):
        for (dirpath, dirnames, filenames) in os.walk(path, topdown=False, onerror=None, followlinks=False):
            for fn in filenames:
                os.unlink(os.path.join(dirpath, fn))
            for dn in dirnames:
                os.rmdir(os.path.join(dirpath, dn))
            #print(dirpath, dirnames, filenames)

    def clear_entry(self, entry):
        """
        Removes all files downloaded into the entry
        """
        path = os.path.join(self.download_path, entry.full_path[1:])
        if self.manager.loop:
            yield from asyncio.wait_for(self._rm_recrusive(path), None)
        else:
            self._rm_recrusive(path)

    @asyncio.coroutine
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
