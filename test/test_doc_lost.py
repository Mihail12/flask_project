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
from models import DocType, db, DocLost, Reason, DataSourceType, DocLostHistory

TEST_DB = 'test.db'
user_id = 3
user_dmsu_id = 4

region_1 = 20
region_2 = 30

dmsudep_1_region_1 = 210
dmsudep_2_region_1 = 211
dmsudep_1_region_2 = 310
dmsudep_2_region_2 = 311

user_id_dmsudep_1_region_1 = 1110
user_id_dmsudep_2_region_1 = 1111
user_id_dmsudep_1_region_2 = 1112
user_id_dmsudep_2_region_2 = 1113


class DocLostTests(BaseTests):

    def setUp(self):
        super(DocLostTests, self).setUp()

        self.doc_lost1 = DocLost.query.get(1)
        self.doc_lost1.user_add_id = user_id_dmsudep_1_region_1
        self.doc_lost1.dmsu_add_id = dmsudep_1_region_1


    ###############
    #### tests ####
    ###############

    def test_get_doc_types_list(self):
        response = self.app.get('/api/v1/doc_types/')
        self.assertEqual(response.status_code, 200)
        type_list = response.json
        self.assertEqual(len(type_list), 2)
        in_db = set(t[0] for t in db.session.query(DocType.name).all())
        in_fact = set((t['name'] for t in type_list))
        self.assertEqual(in_db, in_fact)

    def test_get_doc_reason_list(self):
        response = self.app.get('/api/v1/doc_reasons/')
        self.assertEqual(response.status_code, 200)
        reason_list = response.json
        self.assertEqual(len(reason_list), 2)
        in_db = set(t[0] for t in db.session.query(Reason.name).all())
        in_fact = set((t['name'] for t in reason_list))
        self.assertEqual(in_db, in_fact)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['create']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_create_doc_inactive_ok(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "series": "test",
            "number": "test",
            "reason_id": 2,
            "doc_type_id": 1,
        })
        doc_count = DocLost.query.count()
        response = self.app.post('/api/v1/docs_inactive/', headers=headers, data=data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DocLost.query.count(), doc_count + 1)
        doc = DocLost.query.get(response.json['id'])
        self.assertEqual(doc.user_add_id, user_id)
        self.assertEqual(doc.dmsu_add_id, user_dmsu_id)
        self.assertEqual(doc.data_source_type_id, DataSourceType.CUSTOM)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['create']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_create_doc_inactive_field_errors(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "series": "invalid_test",
            "number": "test",
            "reason_id": 2,
            "doc_type_id": 1,
        })
        doc_count = DocLost.query.count()
        response = self.app.post('/api/v1/docs_inactive/', headers=headers, data=data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DocLost.query.count(), doc_count)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['view']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_get_doc_lost_list_without_page(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        response = self.app.get('/api/v1/docs_inactive/', headers=headers)
        self.assertEqual(response.status_code, 400)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['view']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_get_doc_lost_list_ok(self, app_g_user, g_user, utils_r_passport):
        per_page = 2
        page = 1
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        response = self.app.get(f'/api/v1/docs_inactive/?per_page={per_page}&page={page}', headers=headers)
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(len(json_data['data']), 2)
        self.assertEqual(json_data['per_page'], per_page)
        self.assertEqual(json_data['page'], page)
        sorted_first_time = DocLost.query.get(json_data['data'][0]['id']).created_at
        sorted_second_time = DocLost.query.get(json_data['data'][1]['id']).created_at
        self.assertTrue(sorted_first_time > sorted_second_time)

        page = 2
        response = self.app.get(f'/api/v1/docs_inactive/?per_page={per_page}&page={page}', headers=headers)
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(len(json_data['data']), 2)
        self.assertEqual(json_data['per_page'], per_page)
        self.assertEqual(json_data['page'], page)
        sorted_first_time = DocLost.query.get(json_data['data'][0]['id']).created_at
        sorted_second_time = DocLost.query.get(json_data['data'][1]['id']).created_at
        self.assertTrue(sorted_first_time > sorted_second_time)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['view']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    @mock.patch('schemas.get_current_user', return_value={'groups': {1: PERMISSIONS['view']}})
    def test_get_doc_lost_ok(self, app_g_user, g_user, schemas_r_passport, utils_r_passport, schemas_g_user):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        doc_lost = choice(DocLost.query.all())
        response = self.app.get(f'/api/v1/docs_inactive/{doc_lost.id}/', headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], doc_lost.id)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['view']}})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_get_doc_lost_404(self, app_g_user, g_user, utils_r_passport,):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        response = self.app.get(f'/api/v1/docs_inactive/{35354}/', headers=headers)
        self.assertEqual(response.status_code, 404)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['edit_own'], 2: PERMISSIONS['edit_region']}, 'dmsudep_id': user_dmsu_id})
    @mock.patch('app.get_current_user', return_value={ 'id': user_id, 'dmsudep_id': user_dmsu_id})
    def test_update_doc_lost_ok(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        doc_lost = choice(DocLost.query.all())
        doc_lost.dmsu_add_id = user_dmsu_id
        old_number = doc_lost.number
        data = json.dumps({
            "number": "new_test",
        })
        self.assertFalse(DocLostHistory.query.filter_by(source_id=doc_lost.id).first())
        response = self.app.put(f'/api/v1/docs_inactive/{doc_lost.id}/', headers=headers, data=data)
        self.assertEqual(response.status_code, 200)
        doc_lost_history = DocLostHistory.query.filter_by(source_id=doc_lost.id).first()
        self.assertTrue(doc_lost_history)
        self.assertEqual(doc_lost_history.number, old_number)
        self.assertEqual(doc_lost.number, 'new_test')
        self.assertEqual(doc_lost.user_edit_id, user_id)
        self.assertEqual(doc_lost.dmsu_edit_id, user_dmsu_id)

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['edit_own']}, 'dmsudep_id': dmsudep_1_region_1})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': dmsudep_1_region_1})
    def test_update_doc_lost_permission_own(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        old_number = self.doc_lost1.number
        data = json.dumps({
            "number": "new_test",
        })
        response = self.app.put(f'/api/v1/docs_inactive/{self.doc_lost1.id}/', headers=headers, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DocLost.query.get(self.doc_lost1.id).number, 'new_test')


    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['edit_region']}, 'dmsudep_id': dmsudep_1_region_2})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': dmsudep_1_region_2})
    def test_update_doc_lost_permission_not_own(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "number": "new_test",
        })
        response = self.app.put(f'/api/v1/docs_inactive/{self.doc_lost1.id}/', headers=headers, data=data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.decode('utf-8'), 'user has not permission for this action')

    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['edit_region']}, 'dmsudep_id': dmsudep_2_region_1, "dmsudep_region_id": region_1})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': dmsudep_2_region_1})
    def test_update_doc_lost_permission_region(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        utils_r_passport.return_value.json = lambda: {'region': region_1}

        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "number": "new_test",
        })

        response = self.app.put(f'/api/v1/docs_inactive/{self.doc_lost1.id}/', headers=headers, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DocLost.query.get(self.doc_lost1.id).number, 'new_test')


    @mock.patch('utils.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('schemas.request_to_passport', return_value=mock.Mock(status_code=200))
    @mock.patch('utils.get_current_user', return_value={'groups': {1: PERMISSIONS['edit_region']}, 'dmsudep_id': dmsudep_2_region_1, "dmsudep_region_id": region_1})
    @mock.patch('app.get_current_user', return_value={'id': user_id, 'dmsudep_id': dmsudep_2_region_1})
    def test_update_doc_lost_permission_not_own(self, app_g_user, g_user, schemas_r_passport, utils_r_passport):
        utils_r_passport.return_value.json = lambda: {'region': region_2}

        headers = {
            "Authorization": f"Bearer {self.access_token_test}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "number": "new_test",
        })

        response = self.app.put(f'/api/v1/docs_inactive/{self.doc_lost1.id}/', headers=headers, data=data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.decode('utf-8'), 'user has not permission for this action')


if __name__ == "__main__":
    unittest.main()
