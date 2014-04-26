import random
import unittest
import os
from precollapse import daemon, db, manager, base
from precollapse.db import model, create_session
from precollapse import db
import logging
from IPython import embed
import datetime


logging.basicConfig(level=logging.DEBUG)
logging.root.setLevel(logging.DEBUG)

class TestDaemon(unittest.TestCase):

    def setUp(self):
        fname = "/tmp/precollapse-test.db"
        os.unlink(fname)
        db.configure_engine(url='sqlite:///%s' %fname)
        db.Base.metadata.create_all(db.Engine)


    def tearDown(self):
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

    def test_download_manager(self):
        man = manager.CollapseManager()
        man.app.options = man.app.parser.parse_known_args([])[0]
        man.app.initialize_app([])
        man.app.configure_logging()
        man.log.setLevel(logging.DEBUG)

        session = create_session()
        col = model.Collection.create(session, name="test")
        session.commit()
        example = model.Entry(name="e1", url="http://www.example.com", priority=10,
                              collection_id=col.id)
        session.add(example)
        
        # test download_mananger
        man.download_mananger = base.DownloadManager(man)
        man.download_mananger.start()

        out_path = man.download_mananger.prepare_entry(example)
        self.assertEqual(out_path[-18:], '/Downloads/test/e1')
        self.assertTrue(os.path.exists(out_path))

        example.collection_id = col.id
        out_path2 = man.download_mananger.prepare_entry(example)
        self.assertEqual(out_path, out_path2)



    def test_entry(self):
        session = create_session()
        col = model.Collection.create(session, name="test")
        e1 = model.Entry(name="example.com", url="http://www.example.com", parent_id=col.get_root().id)
        session.add(e1)
        session.commit()
        e1.set_error("test failure")

        self.assertEqual(e1.last_error, "test failure")
        now = datetime.datetime.now()
        in_5 = now + datetime.timedelta(minutes=5)
        in_1day = now + datetime.timedelta(days=1)
        self.assertLess(e1.last_failure, e1.next_check)
        lc = e1.next_check
        self.assertLess(e1.next_check, in_5)
        e1.set_error("test failure2")
        self.assertEqual(e1.last_error, "test failure2")
        self.assertLess(lc, e1.next_check)
        self.assertEqual(e1.failure_count, 2)

        e1.set_success()
        self.assertGreater(e1.next_check, in_1day)
        self.assertEqual(e1.state, model.EntryState.done)


