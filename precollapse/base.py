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
import shutil
from . import utils
from sqlalchemy.orm import object_session

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

    @asyncio.coroutine
    def success(self, entry, msg, **kwargs):
        entry.set_success(msg)

    @asyncio.coroutine
    def failure(self, entry, msg, **kwargs):
        entry.set_error(msg)

class Arguments(list):
    def __init__(self, *args, **options):
        super(Arguments, self).__init__(args)
        self.options = options

    #def __repr__(self):
        #x = list.__str__(self)
        #return "<Arguments %s options=%s>" %(x, self.options)

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

    def get_msg(self, entry, stderr=False, returncode=None):
        i = stderr and 1 or 0
        if entry in self.buffers and len(self.buffers[entry]) > i:
            return self.buffers[entry][i].getvalue()

    @asyncio.coroutine
    def task_done(self, job, stderr=False, returncode=None, future=None):
        # update entry
        i = stderr and 1 or 0
        entry = job.entry
        if returncode is not None and not future.done():
            self.log.info("task done %s rc:%s", entry, returncode)
            if returncode not in self.valid_rc:
                msg = self.get_msg(entry, stderr, returncode)
                self.log.info("task failed: %s #",  utils.epsilon(msg))
                yield from self.failure(entry, msg, returncode=returncode)
                if future:
                    future.set_result((entry, False))
        if entry in self.buffers and job.last:
            if stderr:
                self.buffers[entry][i].truncate()
                self.buffers[entry][i].close()
            else:
                self.buffers[entry][i].truncate()
                self.buffers[entry][i].close()
            if self.buffers[entry][0].closed and self.buffers[entry][1].closed:
                del self.buffers[entry]
                del self.jobs[entry]

    def handle_entry(self, future, entry):
        all_args = yield from self.get_command_args(entry)
        all_args = list(all_args)

        job = None
        while True:
            try:
                args = all_args.pop(0)
            except IndexError:
                # all jobs done successfull
                msg = self.get_msg(entry, True, None)
                self.log.info("task success: %s",  utils.epsilon(msg))
                yield from self.success(entry, msg, returncode=job.returncode)
                if future:
                    future.set_result((entry, True))
                return

            if asyncio.iscoroutinefunction(args):
                xargs = yield from args()
                args = list(xargs)
                if isinstance(args, list) and not isinstance(args, Arguments):
                    all_args = args[1:] + all_args
                    args = args[0]

            if not len(args):
                continue

            opts = {
                "stdout": asyncio.subprocess.PIPE,
                "stderr": asyncio.subprocess.PIPE,
                "stdin": None
            }

            if hasattr(args, "options"):
                opts.update(args.options)

            self.log.debug("run command: %s" %args)

            job = yield from asyncio.create_subprocess_exec(*args, **opts)
            #task = asyncio.Task(job)

            job.last = not len(all_args)
            job.entry = entry
            job.future = future

            if job.stdout:
                asyncio.Task(self.read_stdout(job))
            if job.stderr:
                asyncio.Task(self.read_stderr(job))
            if job.stdin:
                asyncio.Task(self.get_stdin(job))

            self.jobs[entry] = job
            yield from job.wait()

    @asyncio.coroutine
    def get_stdin(self, job):
        pass

    @asyncio.coroutine
    def read_stdout(self, job):
        try:
            while True:
                data = yield from job.stdout.read()
                if not data:
                    yield from self.task_done(job, returncode=job.returncode, future=job.future)
                    return
                self.update_msg(job.entry, data)
        except Exception as e:
            self.log.exception(e)
            self.task_done(job, stderr=True, returncode=job.returncode, future=job.future)

    @asyncio.coroutine
    def read_stderr(self, job):
        try:
            while True:
                data = yield from job.stderr.read(10)
                if not data:
                    yield from self.task_done(job, stderr=True, returncode=job.returncode, future=job.future)
                    return
                self.update_msg(job.entry, data, stderr=True)
        except Exception as e:
            self.log.exception(e)
            self.task_done(job, stderr=True, returncode=job.returncode, future=job.future)

    def get_command_args(self, entry):
        raise NotImplemented

    def start_backend(self, daemon):
        self.daemon = daemon
        self.jobs = {}
        self.buffers = {}

class ExecutorBackend(Backend):
    def handle_entry(self, future, entry):
        object_session(entry).commit()
        process = self.manager.loop.run_in_executor(None, self.exec_entry, entry)
        try:
            rv = yield from asyncio.wait_for(process, 500)
            future.set_result((entry, rv))
        except asyncio.TimeoutError as e:
            process.shutdown(wait=True)
            future.set_exception(e)




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

    @asyncio.coroutine
    def clear_entry(self, entry):
        """
        Removes all files downloaded into the entry
        """
        path = os.path.join(self.download_path, entry.system_path)
        if self.manager.loop:
            yield from asyncio.wait_for(self._rm_recrusive(path), None)
        else:
            self._rm_recrusive(path)

    def _mv_cruft(self, path, cruft_path):
        os.makedirs(cruft_path, mode=0o755, exist_ok=True)
        i = 2
        while i:
            try:
                shutil.move(path, cruft_path)
                return
            except FileNotFoundError:
                return
            except shutil.Error:
                tpath = os.path.join(cruft_path, os.path.basename(path))
                shutil.rmtree(tpath, ignore_errors=True)
                i -= 1

    @asyncio.coroutine
    def move_to_craft(self, entry):
        path = os.path.join(self.download_path, entry.system_path)
        cruft_path = os.path.join(self.download_path, "_cruft")
        if self.manager.loop:
            yield from asyncio.wait_for(self._mv_cruft(path, cruft_path), None)
        else:
            self._mv_cruft(path, cruft_path)

    @asyncio.coroutine
    def entry_done(self, entry, ):
        """
        Mark file to be successfull downloaded
        """
        pass

    def get_temp_path(self, backend, entry=None):
        if entry:
            rv = os.path.join(self.download_path, "_temp", entry.system_path, backend.name)
        else:
            rv = os.path.join(self.download_path, "_temp", "_%s" %backend.name)
        return rv


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
