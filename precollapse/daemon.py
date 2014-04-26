import asyncio
from .db import model
from .db import create_session
from sqlalchemy import or_, desc, asc
import queue
import sys
import logging
import datetime
import weakref
from concurrent.futures import ThreadPoolExecutor
import concurrent
asyncio.tasks._DEBUG = True

class Job(object):
    def __init__(self, entry):
        self.entry = entry

    def __lt__(self, other):
        if self.entry and getattr(other, 'entry', None):
            return not self.entry.priority.__lt__(other.entry.priority)
        return False

    def __repr__(self):
        return "<Job entry='%s'>" %(self.entry and self.entry.id or self.entry.name)


# FIXME: this async code definitly needs cleanup and love.
# asyncio python seems strange sometimes

class Daemon(object):
    log = logging.getLogger("daemon")

    def __init__(self, manager, check_interval = 10, queue_size=20):
        self.manager = manager
        self.jobs = asyncio.PriorityQueue(queue_size)
        self.check_interval = check_interval
        self.in_check = weakref.WeakSet()
        self.workpool = ThreadPoolExecutor(5)
        self.loop = None
        self.blacklist = set()

    @asyncio.coroutine
    def do_job(self):
        try:
            job = yield from self.jobs.get()
            #yield from asyncio.sleep(1000)
            print("got job")
            print(job)
            entry = job.entry
            self.log.info("check entry: %s" %entry.full_path)
            print(entry)
            if entry.plugin is None:
                self.log.debug("detect plugin for entry: %s" %entry.id)
                (plugin, prio) = self.manager.get_backend_for_entry(entry)
                entry.plugin = plugin.name
                self.log.debug("use plugin for entry %s: %s (prio=%s)" %(entry.id, plugin.name, prio))
                if not plugin:
                    self.log.error("can't find plugin to handle url %s" %(entry.id))
                    entry.set_error("can't find plugin")
            else:
                plugin = self.manager.get_backend(entry.plugin)
            if not plugin:
                self.log.error("entry has plugin that does not exist")
                self.blacklist.add(entry.id)
                # FIXME, blacklist entry until restart
                return
            
            yield from plugin.handle_entry(entry)

            return job
            #embed()
            #yield (priority, entry)

            #self.jobs.done()
            #embed()
        except Exception as e:
            self.log.exception(e)

    @asyncio.coroutine
    def got_entries(self, entries):
        print("got entries")
        print(entries)
        if not entries:
            return
        try:
            for entry in entries:
                print("-")
                if entry in self.in_check:
                    self.log.debug("entry still processed: %s" %entry.full_path)
                    continue

                #self.in_check.add(entry)
                #embed()
                print("qlen", self.jobs.qsize())
                asyncio.Task(self.do_job())
                yield from self.jobs.put(Job(entry))
                print("%%%%%%")
                #print(rv)

                #entry.next_check = next_check
                #session.add(entry)

        except Exception as e:
            print("#"*30)
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
                session = create_session()
                now = datetime.datetime.now()
                next_check = now + datetime.timedelta(seconds=60)


                def get_entries():
                    #print("in entries")
                    #for i in session.query(model.Entry).filter(or_(model.Entry.next_check==None,
                                                                #model.Entry.next_check<now)).\
                                                                    #order_by(desc(model.Entry.priority)):
                        #print("get_entries", i)
                        #yield i
                    try:
                        #conn = create_session()
                        qsession = create_session()
                        query = qsession.query(model.Entry).filter(or_(model.Entry.next_check==None,
                                                                    model.Entry.next_check<now)) \
                                                           .filter(model.Entry.type.isnot(model.TYPE_DIRECTORY)) \
                                                           .order_by(desc(model.Entry.priority))
                        rv = list(query)
                        print(rv)
                        #return [1,2,3]
                        return rv
                    except Exception as e:
                        self.log.exception(e)

                #def cb():
                #    pass
                h = asyncio.Handle(get_entries, ())
                #h.cancel()

                process = self.loop.run_in_executor(None, h)

                #process = self.loop.run_in_executor(None,
                #               get_entries)
                #process.add_done_callback(self.got_entries)
                print(process)
                #embed()
                #asyncio.tasks.wait_for(process, 100)
                #embed()
                yield from asyncio.wait_for(process, 60.0)
                print("done wait")
                yield from self.got_entries(process.result())
                #print(list(process.result()))

                #session.commit()
                #print(list(entries))

                yield from asyncio.sleep(self.check_interval)
            except Exception as e:
                self.log.exception(e)
                sys.exit(1)

    def run(self):
        self.loop = el = asyncio.get_event_loop()

        # start all backends
        for backend in self.manager.get_all_backends():
            backend.start_backend(self)

        asyncio.Task(self.check_jobs())
        asyncio.Task(self.do_job())
        el.run_forever()

