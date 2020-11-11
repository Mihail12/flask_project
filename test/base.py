import os
import sys
import unittest
from random import choice

# This row of code should be in order to start test without error.
# This row should be below import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from models import DocType, db, DocLost, Reason, OAuth2Token

TEST_DB = 'test.db'
user_id = 3
user_dmsu_id = 4


class BaseTests(unittest.TestCase):

    ############################
    #### setup and teardown ####
    ############################

    # executed prior to each test
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['DEBUG'] = False
        app.config['BASEDIR'] = os.getcwd()
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + \
            os.path.join(app.config['BASEDIR'], TEST_DB)
        self.app = app.test_client()
        db.drop_all()
        db.create_all()
        self.handle = 'test'
        # register remove function
        # self.addCleanup(os.remove, os.path.join(app.config['BASEDIR'], TEST_DB))

        self.d_type1, self.d_type2 = DocType(name='test_type1'), DocType(name='test_type2')
        db.session.bulk_save_objects([self.d_type1, self.d_type2])

        self.d_reason1, self.d_reason2 = Reason(name='test_reason1'), Reason(name='test_reason2')
        db.session.bulk_save_objects([self.d_reason1, self.d_reason2])
        db.session.commit()

        for i in range(5):
            db.session.add(DocLost(
                series=f'test{i}',
                number=f'test{i}',
                reason_id=choice(Reason.query.all()).id,
                doc_type_id=choice(DocType.query.all()).id
            ))

        self.access_token_test = 'test_token'
        self.token = OAuth2Token(access_token=self.access_token_test)
        db.session.add(self.token)
        db.session.commit()

    # executed after each test
    def tearDown(self):
        db.session.close()

    @classmethod
    def tearDownClass(cls):
        os.remove(os.path.join(app.config['BASEDIR'], TEST_DB))
