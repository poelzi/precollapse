import asyncio
from .db import model
from .db import create_session
from sqlalchemy import or_,and_, desc, asc
import queue
import sys
import logging
import datetime
import weakref
from concurrent.futures import ThreadPoolExecutor
import concurrent
from . import webserver
#asyncio.tasks._DEBUG = True


class Job(object):
    def __init__(self, entry):
        self.entry = entry

    def __lt__(self, other):
        if self.entry and getattr(other, 'entry', None):
            return not self.entry.priority.__lt__(other.entry.priority)
        return False

    def __repr__(self):
        return "<Job entry='%s'>" %(self.entry and self.entry.id or self.entry.name)



class Daemon(object):
    log = logging.getLogger("daemon")

    def __init__(self, manager, check_interval = 10, queue_size=20):
        self.manager = manager
        self.jobs = asyncio.PriorityQueue(queue_size)
        self.check_interval = check_interval
        self.in_check = weakref.WeakSet()
        self.workpool = ThreadPoolExecutor(5)
        self.loop = manager.loop
        self.manager.loop = self.loop
        self.blacklist = set()
        self.first_run = True

    @asyncio.coroutine
    def do_job(self):
        while True:
            try:
                job = yield from self.jobs.get()
                #yield from asyncio.sleep(1000)
                entry = job.entry
                session = create_session()
                session.add(entry)
                self.log.info("check entry: %s" %entry.full_path)
                if entry.plugin is None:
                    self.log.debug("detect plugin for entry: %s" %entry.id)
                    (plugin, prio) = self.manager.get_backend_for_entry(entry)
                    if not plugin:
                        self.log.info("can't find plugin to handle url %s" %(entry))
                        entry.set_error("can't find plugin to handle url", unhandled=True)
                        continue
                    entry.plugin = plugin.name
                    session.commit()
                    self.log.debug("use plugin for entry %s: %s (prio=%s)" %(entry.id, plugin.name, prio))
                else:
                    plugin = self.manager.get_backend(entry.plugin)
                if not plugin:
                    self.log.error("entry has plugin that does not exist")
                    self.blacklist.add(entry.id)
                    # FIXME, blacklist entry until restart
                    return

                rv = plugin.do_entry(entry)
                def call_done(future):
                    asyncio.Task(self.job_done(future))
                #rv.add_done_callback(self.job_done)
                rv.add_done_callback(call_done)

            except Exception as e:
                self.log.exception(e)
        #raise asyncio.tasks.Return(job)

    def job_done(self, future):
        entry, rv = future.result()
        if not rv:
            self.log.error("job failed: %s", str(entry))
        else:
            dm = yield from self.manager.get_download_manager(entry.collection)
            yield from dm.entry_done(entry)

    @asyncio.coroutine
    def got_entries(self, entries):
        if not entries:
            return
        try:
            for entry in entries:
                if entry in self.in_check:
                    self.log.debug("entry still processed: %s" %entry.full_path)
                    continue

                #self.in_check.add(entry)
                #embed()
                #print("qlen", self.jobs.qsize())
                #asyncio.Task(self.do_job())
                yield from self.jobs.put(Job(entry))
                #print("%%%%%%")
                #print(rv)

                #entry.next_check = next_check
                #session.add(entry)

        except Exception as e:
            self.log.exception(e)
            #for i in session.query(model.Entry).filter(or_(model.Entry.next_check==None,
            #model.Entry.next_check<now)).\
                #order_by(desc(model.Entry.priority)):
            #print("jojojojo")
            ##embed()
            #yield from got_entries([i])

    @asyncio.coroutine
    def check_jobs(self):
        while True:
            try:
                self.log.debug("check jobs")
                now = datetime.datetime.now()
                next_check = now + datetime.timedelta(seconds=60)


                def get_entries():
                    try:
                        qsession = create_session()
                        query = model.Entry.jobs_filter(qsession, now, with_empty=self.first_run)
                        self.first_run = False
                        for entry in query:
                            qsession.expunge(entry)
                            yield entry

                        return
                    except Exception as e:
                        self.log.exception(e)

                process = self.loop.run_in_executor(None, get_entries)

                yield from asyncio.wait_for(process, 60.0)
                yield from self.got_entries(process.result())

                yield from asyncio.sleep(self.check_interval)
            except Exception as e:
                self.log.exception(e)
                sys.exit(1)

    def run(self, run_forever=True):

        # start all backends
        for backend in self.manager.get_all_backends():
            backend.start_backend(self)

        asyncio.Task(self.check_jobs())
        for i in range(self.manager.app.config.getint("daemon", "worker", fallback=1)):
            asyncio.Task(self.do_job())

        try:
            webserver.webapp.run(run_forever=run_forever)
        except KeyboardInterrupt:
            sys.exit(0)

