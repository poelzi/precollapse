import random
import unittest
import os
#from precollapse import daemon, db, manager, base
#from precollapse.db import model, create_session
#from precollapse import db
from precollapse import utils
import logging
from IPython import embed
import datetime
from . import async_test
import tempfile
import shutil
import logging

logging.basicConfig(level=logging.DEBUG)
logging.root.setLevel(logging.DEBUG)

class TestUtils(unittest.TestCase):

    ##def setUp(self):
        ##self.tmpdir = tempfile.mkdtemp(prefix='precollapse')
        ##self.log = logging.getLogger("TestDaemon")
        ##fname = os.path.join(self.tmpdir,"precollapse-test.db")
        ##try:
            ##os.unlink(fname)
        ##except FileNotFoundError:
            ##pass
        ##db.configure_engine(url='sqlite:///%s' %fname)
        ##db.Base.metadata.create_all(db.Engine)


    #def tearDown(self):
        #shutil.rmtree(self.tmpdir)

    def test_senum(self):
        # make sure the shuffled sequence does not lose any elements
        class MySenum(utils.SEnum):
            bla = "blubb"
            second = "second"

        print(MySenum.choices())
        self.assertEqual(len(MySenum.choices()), 2)
        self.assertEqual(MySenum.choices(), ['blubb', 'second'])
        self.assertTrue(isinstance(MySenum.sql_type(), utils.SqlEnum))
