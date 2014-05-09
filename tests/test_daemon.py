import random
import unittest
import os
from precollapse import daemon, db, manager, base
from precollapse.db import model, create_session
from precollapse import db
import logging
from IPython import embed
import datetime
from . import async_test
import tempfile
import shutil
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
logging.root.setLevel(logging.DEBUG)

db._configure_engine = db.configure_engine
def configure_engine(*args, **kwargs):
    pass

db.configure_engine =  configure_engine

class TestDaemon(unittest.TestCase):

    def setUp(self):
        #self.tmpdir = tempfile.mkdtemp(prefix='precollapse')
        self.tmpdir = "/tmp/precollapse-test"
        os.makedirs(self.tmpdir, mode=0o744, exist_ok=True)
        self.log = logging.getLogger("TestDaemon")
        fname = os.path.join(self.tmpdir,"precollapse-test.db")
        try:
            #os.unlink(fname)
            pass
        except FileNotFoundError:
            pass
        print(fname)
        db._configure_engine(url='sqlite:///%s' %fname)
        db.Base.metadata.create_all(db.Engine)


    def tearDown(self):
        #shutil.rmtree(self.tmpdir)
        pass


    def test_jobs(self):
        # make sure the shuffled sequence does not lose any elements
        e1 = model.Entry(name="e1", priority=10)
        e2 = model.Entry(name="e2", priority=-10)
        e3 = model.Entry(name="e3", priority=0)
        e4 = model.Entry(name="e4", priority=30)

        j1 = daemon.Job(e1)
        j2 = daemon.Job(e2)
        j3 = daemon.Job(e3)
        j4 = daemon.Job(e4)

        lst = [j1, j2, j3, j4]
        lst.sort()

        self.assertEqual(lst, [j4, j1, j3, j2])

    def test_urlweight(self):
        UrlWeight = base.UrlWeight
        self.assertTrue(UrlWeight.very_good > UrlWeight.good)
        self.assertTrue(UrlWeight.normal > UrlWeight.unable)
        self.assertTrue(UrlWeight.unable < UrlWeight.normal)
        lst = [UrlWeight.very_good, base.UrlWeight.unable, UrlWeight.normal, UrlWeight.very_bad]
        lst.sort(reverse=True)
        self.assertEqual(lst,
                         [UrlWeight.very_good, UrlWeight.normal, UrlWeight.very_bad, UrlWeight.unable])
        self.assertTrue(UrlWeight.normal > 30)
        self.assertTrue(UrlWeight.normal < 100)


    #@async_test
    def test_entry(self):
        session = create_session()
        col = model.Collection.create(session, name="test")
        session.commit()
        root = col.get_root()

        e1 = model.Entry(name="e1", parent=root, priority=10, collection=col)
        e1e = model.Entry(name="child", parent=e1, priority=10, collection=col)
        e2 = model.Entry(name="e2", parent=root, priority=-10, collection=col)
        u1_name = "Übername for \\ | be"

        u1 = model.Entry(name=u1_name, collection=col)
        u1c = model.Entry(name="Some Ünicode child", parent=u1, collection=col)
        session.add(e1, e2, u1, u1c)
        session.commit()

        self.assertEqual(e1e.full_path, "/e1/child")
        self.assertEqual(e1e.system_path, os.path.join("e1","child"))
        self.assertEqual(e1.system_path, "e1")
        self.assertEqual(e1.full_path, "/e1")
        self.assertEqual(u1.full_path, u1_name)
        self.assertEqual(e2.full_path, "/%s/%s" %(u1_name, "Some Ünicode child"))

        with self.assertRaises(exc.InvalidNameError):
            model.Entry(name="bla/blubb", collection=col)





    def test_backend(self):
        man = manager.CollapseManager()
        man.log.setLevel(logging.DEBUG)

        example = model.Entry(name="e1", url="http://www.example.com", priority=10)
        backend, prio = man.get_backend_for_entry(example)
        self.assertNotEqual(backend, None)
        self.assertTrue(isinstance(backend, base.Backend), "not a backend subclass")

        unhandled = model.Entry(name="e1", url="thisschemaihavenotseen://somehost:82")
        backend, prio = man.get_backend_for_entry(unhandled)
        self.assertIs(backend, None)
        self.assertEqual(prio, base.UrlWeight.unable)

        backend = man.get_backend("wget")
        self.assertEqual(backend.name, "wget")


    @async_test
    def test_download_manager(self):
        man = manager.CollapseManager()
        man.app.options = man.app.parser.parse_known_args([])[0]
        man.app.initialize_app([])
        man.app.configure_logging()
        man.log.setLevel(logging.DEBUG)

        session = create_session()
        col = model.Collection.create(session, name="test")

        example = model.Entry(name="e1", parent_id=col.get_root().id, url="http://www.example.com", priority=10,
                              collection_id=col.id)
        gc = model.Entry(name="git-clone", parent_id=col.get_root().id,
                              url="https://github.com/poelzi/git-clone-test.git",
                              collection_id=col.id)

        session.add(example, gc)

        gc_back, gc_points = man.get_backend_for_entry(gc)
        self.assertEqual(gc_back.name, "git")

        session.commit()
        # test download_mananger
        for name,dm in man._download_managers.items():
            self.log.info("test download_manager %s", name)
            self.assertEqual(name, dm.name)

            man.download_mananger = dm(man, download_path=os.path.join(self.tmpdir, "downloads"))
            man.download_mananger.start()

            out_path = yield from man.download_mananger.prepare_entry(example)
            self.assertEqual(out_path[-12:], os.path.join('downloads', 'e1'))
            self.assertTrue(os.path.exists(out_path))

            example.collection_id = col.id
            out_path2 = yield from man.download_mananger.prepare_entry(example)
            self.assertEqual(out_path, out_path2)

        man.start_daemon(run_forever=False)
        yield from asyncio.sleep(3)


    def test_entry(self):
        session = create_session()
        col = model.Collection.create(session, name="test")
        session.commit()
        e1 = model.Entry(name="example.com", url="http://www.example.com", parent_id=col.get_root().id,
                         collection=col)
        session.add(e1)
        session.commit()
        e1.set_error("test failure")

        self.assertEqual(e1.error_msg, "test failure")
        now = datetime.datetime.now()
        in_5 = now + datetime.timedelta(minutes=5)
        in_1day = now + datetime.timedelta(days=1)
        self.assertLess(e1.last_failure, e1.next_check)
        lc = e1.next_check
        self.assertLess(e1.next_check, in_5)
        e1.set_error("test failure2")
        self.assertEqual(e1.error_msg, "test failure2")
        self.assertLess(lc, e1.next_check)
        self.assertEqual(e1.failure_count, 2)

        e1.set_success()
        self.assertGreater(e1.next_check, in_1day)
        self.assertEqual(e1.state, model.EntryState.done)


