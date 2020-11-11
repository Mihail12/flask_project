import json
import os
import sys
import unittest
from random import choice
from unittest import mock

from config import PERMISSIONS

from test.base import BaseTests

# This row of code should be in order to start test without error.
# This row should be below import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app
from models import DocType, db, DocLost, DocLostChangeRequest, Reason, OAuth2Token, DataSourceType, DocLostHistory

TEST_DB = 'test.db'
user_id = 4
user_dmsu_id = 5


class OutsideTests(BaseTests):

    ###############
    #### tests ####
    ###############

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    def test_document_inactive_get_error(self, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        response = self.app.get('/api/v1/document/inactive/', headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'doc_type parameter is required')

        params = {
            'doc_type': 1
        }
        response = self.app.get('/api/v1/document/inactive/', headers=headers, query_string=params)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], 'number parameter is required')


    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.DocLostAliensSchema.get_citizenship', return_value=None)
    def test_document_inactive_get_ok(self, g_citiz, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        doc_lost = choice(DocLost.query.all())
        params = {
            'doc_type': doc_lost.doc_type_id,
            'number': doc_lost.number
        }
        response = self.app.get('/api/v1/document/inactive/', headers=headers, query_string=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], doc_lost.id)


