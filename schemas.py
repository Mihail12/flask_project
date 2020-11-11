from flask_marshmallow import Marshmallow
from marshmallow import fields, validates, ValidationError

from config import EIAS_GET_DEP, EIAS_GET_USER, EIAS_GET_STATE, PERMISSIONS, EIAS_GET_PASSPORT
from models import DocLost, DocType, Reason, OAuth2Token, DocLostHistory, DocLostUpload, DocLostChangeRequest
from oauth_processing import EIAS_BASE_URL
from utils import request_to_passport, get_current_user

ma = Marshmallow()


class OAuth2TokenSchema(ma.ModelSchema):
    class Meta:
        model = OAuth2Token


class DocLostUploadSchema(ma.ModelSchema):
    class Meta:
        model = DocLostUpload


class DocTypeListSchema(ma.ModelSchema):
    class Meta:
        model = DocType
        fields = ('id', 'name')


class DocReasonListSchema(ma.ModelSchema):
    class Meta:
        model = Reason
        fields = ('id', 'name', 'dev_type')


class DocLostListSchema(ma.ModelSchema):
    class Meta:
        model = DocLost
        fields = ('id', 'doc_type', 'reason', 'series', 'number', 'dmsu_add')
        dateformat = '%Y-%m-%d'
        datetimeformat = '%Y-%m-%d'

    dmsu_add = fields.Function(DocLost.show_dmsu_add, attribute="dmsu_add_id")

    doc_type = fields.Nested("DocTypeListSchema")
    reason = fields.Nested("DocReasonListSchema")


class DocLostRetrieveSchema(ma.ModelSchema):
    class Meta:
        model = DocLost
        fields = ('id', 'doc_type', 'reason', 'first_name', 'middle_name', 'last_name', 'passport_doc', 'created_at',
                  'date_birth', 'series', 'number', 'citizenship', 'issue_date', 'exp_date', 'dmsudep_issue',
                  'date_invalid', 'date_add', 'date_destruction', 'date_destruction_created', 'data_source_type',
                  'dmsu_add', 'dmsu_edit', 'user_add', 'user_edit', 'notes', 'act', 'change_request', 'user_can_change')
        dateformat = '%Y-%m-%d'
        datetimeformat = '%Y-%m-%d'

    citizenship = fields.Function(DocLost.show_citizenship, attribute="citizenship_id")
    dmsudep_issue = fields.Function(DocLost.show_dmsudep_issue, attribute="dmsudep_issue_id")
    dmsu_add = fields.Function(DocLost.show_dmsu_add, attribute="dmsu_add_id")
    dmsu_edit = fields.Function(DocLost.show_dmsu_edit, attribute="dmsu_edit_id")
    user_add = fields.Function(DocLost.show_user_add)
    user_edit = fields.Function(DocLost.show_user_edit)

    data_source_type = fields.Method(serialize='get_data_source_type', attribute="data_source_type_id")

    doc_type = fields.Nested("DocTypeListSchema")
    reason = fields.Nested("DocReasonListSchema")
    change_request = fields.Method('get_change_request')
    user_can_change = fields.Method('get_user_can_change')
    passport_doc = fields.Method('get_passport_doc')

    def get_change_request(self, obj):
        change_request = obj.change_requests.filter_by(active=True).first()
        if change_request:
            url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{change_request.user_add_id}/'
            user = request_to_passport(url)
            data = {
                "text": change_request.text,
                'user': user.json() if user.status_code is 200 else None,
                'id': change_request.id
            }
        else:
            data = None
        return data

    def get_user_can_change(self, doc_lost):
        user = get_current_user()
        user_groups = user.get('groups').values()

        user_dmsudep_id = user.get('dmsudep_id')
        edit_own = str(doc_lost.dmsu_add_id) == str(user_dmsudep_id)
        if edit_own and PERMISSIONS['edit_own'] in user_groups:
            return True
        if PERMISSIONS['edit_region'] not in user_groups:
            return False

        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{doc_lost.dmsu_add_id}/'
        dep = request_to_passport(url).json()
        edit_region = str(dep.get('region')) == str(user.get('dmsudep_region_id'))
        if edit_region and PERMISSIONS['edit_region'] in user_groups:
            return True
        else:
            return False

    def get_data_source_type(self, obj):
        return getattr(obj.data_source_type, "name", None)

    def get_passport_doc(self, obj):
        url = f'{EIAS_BASE_URL}{EIAS_GET_PASSPORT}'
        query_params = {'doc_type': obj.doc_type_id, 'number': obj.number}
        if obj.series: query_params['series'] = obj.series
        response = request_to_passport(url, query_params=query_params)
        if response.status_code in [404, 400]:
            return None

        passport_data = response.json()
        return {'id': passport_data.get('id'), 'person': passport_data.get('person')}


def dep_exists(value):
    if not value:
        return value
    url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{value}/'
    response = request_to_passport(url)
    if response.status_code is 200:
        return value
    raise ValidationError(f"DmsuDep with id: {value} does not exist")


def user_exists(value):
    url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{value}/'
    response = request_to_passport(url)
    if response.status_code is 200:
        return value
    raise ValidationError(f"User with id: {value} does not exist")


class DocLostCreateSchema(ma.ModelSchema):
    class Meta(ma.ModelSchema.Meta):
        model = DocLost
        fields = ('doc_type_id', 'reason_id', 'first_name', 'middle_name', 'last_name',
                  'date_birth', 'series', 'number', 'citizenship_id', 'issue_date', 'exp_date', 'dmsudep_issue_id',
                  'date_invalid', 'date_add', 'date_destruction', 'date_destruction_created', 'edit_reason_text',
                  'dmsu_add_id', 'dmsu_edit_id', 'user_add_id', 'user_edit_id', 'notes', 'act', 'data_source_type_id')
        dateformat = '%Y-%m-%d'
        datetimeformat = '%Y-%m-%d'

    dmsu_add_id = fields.Int(validate=[dep_exists], allow_none=True)
    dmsu_edit_id = fields.Int(validate=[dep_exists], allow_none=True)
    user_add_id = fields.Int(validate=[user_exists], allow_none=True)
    user_edit_id = fields.Int(validate=[user_exists], allow_none=True)

    @validates('citizenship_id')
    def citizenship_exists(self, value):
        if not value:
            return value
        for citizenship in value:
            url = f'{EIAS_BASE_URL}{EIAS_GET_STATE}{citizenship}/'
            response = request_to_passport(url)
            if response.status_code is not 200:
                raise ValidationError(f"State with id: {citizenship} does not exist")
        return value

    @validates('reason_id')
    def reason_exists(self, value):
        r = Reason.query.filter_by(id=value)
        if r.count():
            return value
        raise ValidationError(f"Reason with id: {value} does not exist")

    @validates('doc_type_id')
    def doc_type_exists(self, value):
        d = DocType.query.filter_by(id=value)
        if d.count():
            return value
        raise ValidationError(f"DocType with id: {value} does not exist")


class DocLostAliensSchema(ma.ModelSchema):
    class Meta:
        model = DocLost
        fields = ('id', 'doc_type_id', 'series', 'number', 'reason_id', 'first_name', 'middle_name', 'last_name',
                  'date_birth', 'date_destruction', 'act', 'notes',
                  'date_add', 'citizenship', 'issue_date', 'exp_date', 'dmsudep_issue_id', 'date_invalid',
                  'user_add_id', 'user_edit_id', 'source_id', 'data_source_type_id', 'passport_request_id')
        dateformat = '%Y-%m-%d'
        datetimeformat = '%Y-%m-%d'

    citizenship = fields.Method('get_citizenship', deserialize='load_citizenship', attribute="citizenship_id")

    def get_citizenship(self, obj):
        citizenship = DocLost.show_citizenship(obj)
        return [c.get('code_eng') for c in citizenship]

    def load_citizenship(self, value):
        url = f'{EIAS_BASE_URL}{EIAS_GET_STATE}?code_eng={value}'
        response = request_to_passport(url).json()
        if response.status_code is 200:
            raise ValidationError(f'There is no state with alpha-3: {value}')
        return [response[0]['id']]


class DocLostChangeRequestSchema(ma.ModelSchema):
    class Meta(ma.ModelSchema.Meta):
        model = DocLostChangeRequest
        fields = ("doc_lost_id", "text", "approved", "user_processed", "active", "reject_text", "region_processed_id",
                  "dep_processed_id", "dep_add_id", "user_add", "region_add_id", "user_add_id", "user_processed_id")

    user_add = fields.Method('get_user_add')
    user_processed = fields.Method('get_user_processed')

    def get_user_add(self, obj):
        if not obj.user_add_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{obj.user_add_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def get_user_processed(self, obj):
        if not obj.user_processed_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{obj.user_processed_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None


class DocLostChangeRequestListSchema(ma.ModelSchema):
    class Meta(ma.ModelSchema.Meta):
        model = DocLostChangeRequest
        fields = ("doc_lost_id", "text", "user_add", "active", "approved", "dep_add", "created_at", "reject_text")
        dateformat = '%Y-%m-%d'
        datetimeformat = '%Y-%m-%d'

    user_add = fields.Method('get_user_add')

    def get_user_add(self, obj):
        if not obj.user_add_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{obj.user_add_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def get_dep_add(self, obj):
        if not obj.user_add_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{obj.dep_add_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None
