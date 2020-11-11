import datetime
import enum

import flask_sqlalchemy
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER
from sqlalchemy.ext.declarative import declared_attr

from config import EIAS_GET_DEP, EIAS_GET_USER, EIAS_GET_STATE
from oauth_processing import EIAS_BASE_URL
from utils import request_to_passport

db = flask_sqlalchemy.SQLAlchemy()


class ModelMixin(object):
    def __init__(self, *args, **kwargs):   # Used for pycharm to not show warnings when create new models objects
        super(ModelMixin, self).__init__(*args, **kwargs)

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.datetime.utcnow)


class OAuth2Token(db.Model, ModelMixin):
    __tablename__ = 'oauth2token'

    user_id = db.Column(db.Integer)
    token_type = db.Column(db.String(20))
    access_token = db.Column(db.String(48), nullable=False)
    refresh_token = db.Column(db.String(48))
    expires_at = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(15), nullable=True)
    session_key = db.Column(db.String(40), nullable=True)

    def to_token(self):
        return dict(
            access_token=self.access_token,
            token_type=self.token_type,
            refresh_token=self.refresh_token,
            expires_at=self.expires_at,
        )


class ReasonEnum(enum.Enum):
    VALID = 1
    NOT_VALID = 7
    LOST = 3
    CANCELED = 4
    STOLEN = 13
    DELETED = 10
    SPOIL = 2
    SPOIL_TECH = 11
    OFORM = 8  # оформлюється
    ISSUE_REF = 9  # відказ від отримання
    DESTROY = 6
    DECEASED = 14
    CANCELED_FORM = 16
    DETAINED = 17
    NEED_EXCLUDED = 15
    CHANGE = 5


class Reason(db.Model):
    __tablename__ = 'reason_inactive'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='')
    dev_type = db.Column(db.String(255), default='')


class DocType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    __tablename__ = 'doc_type'
    name = db.Column(db.String(255), default='')

    ID = 1
    IT = 3  # Тимчасове посвідчення громадянина України
    P = 4
    BC = 5  # свідоцтво про народження
    SP = 10  # Проїзний документ особи, якій надано додатковий захист
    ER = 12  # Посвідка на постійне проживання
    ET = 13  # Посвідка на тимчасове проживання
    PD = 14  # дипломатичний паспорт України
    PS = 15  # службовий паспорт України
    REP_A = 21  # уповноважена особа (authorized person)
    REP_L = 22  # законий представник (legal representative)
    CC = 23  # Довідка про реєстрацію особи громадянином Укаїни
    IS = 24  # посвідчення особи на повернення в Україну
    IN = 29  # Посвідчення особи без громадянства для виїзду за кордон
    EG = 26  # Картка мігранта
    EY = 20  # Посвідчення біженця
    IB = 27  # Проїзний документ біженця
    ED = 9  # Посвідчення особи, яка потребує додаткового захисту
    PR = 28  # Проїзний документ дитини
    AC = 37  # посвідка члена екіпажу
    F1 = 40


class DataSourceType(db.Model):
    __tablename__ = 'data_source_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), default='')

    CUSTOM = 1
    AUTO_P = 2
    AUTO_ID = 3
    AUTO_ALIENS = 4


class DocLostMixin(ModelMixin):
    __tablename__ = 'doc_lost'

    @declared_attr   # this should be in order to declare ModelMixin class
    def doc_type_id(cls): return db.Column(db.Integer, db.ForeignKey('doc_type.id'), nullable=True)

    @declared_attr   # this should be in order to declare ModelMixin class
    def doc_type(cls): return db.relationship('DocType', lazy=True)

    @declared_attr
    def reason(cls): return db.relationship('Reason', lazy=True)

    @declared_attr
    def reason_id(cls): return db.Column(db.Integer, db.ForeignKey('reason_inactive.id'), nullable=True)

    @declared_attr
    def data_source_type(cls): return db.relationship('DataSourceType', lazy=True)

    @declared_attr
    def data_source_type_id(cls): return db.Column(db.Integer, db.ForeignKey('data_source_type.id'), nullable=True)

    first_name = db.Column(db.String(255), default='')
    last_name = db.Column(db.String(255), default='')
    middle_name = db.Column(db.String(255), default='')
    date_birth = db.Column(db.DateTime, nullable=True)
    series = db.Column(db.String(5), default='', nullable=True)
    number = db.Column(db.String(20))
    citizenship_id = db.Column('citizenship_id', ARRAY(INTEGER), nullable=True)  # r'^api/v1/get_state/' r'^api/v1/get_state/{id}/'
    issue_date = db.Column(db.Date, nullable=True)
    exp_date = db.Column(db.Date, nullable=True)
    dmsudep_issue_id = db.Column(db.Integer, nullable=True)  # r'^api/v1/get_dmsudep/' r'^api/v1/get_dmsudep/{id}/'
    date_invalid = db.Column(db.Date, nullable=True)
    date_add = db.Column(db.Date, nullable=True)
    date_destruction = db.Column(db.Date, nullable=True)
    date_destruction_created = db.Column(db.Date, nullable=True)

    dmsu_add_id = db.Column(db.Integer, nullable=True)  # r'^api/v1/get_dmsudep/' r'^api/v1/get_dmsudep/{id}/'
    dmsu_edit_id = db.Column(db.Integer, nullable=True)  # r'^api/v1/get_dmsudep/' r'^api/v1/get_dmsudep/{id}/'
    user_add_id = db.Column(db.Integer, nullable=True)  # r'^api/v1/get_user/' r'^api/v1/get_user/{id}/'
    user_edit_id = db.Column(db.Integer, nullable=True)  # r'^api/v1/get_user/' r'^api/v1/get_user/{id}/'
    notes = db.Column(db.String(255), default='', nullable=True)
    csv_file = db.Column(db.Integer, nullable=True, default=0)
    inactive_upload_id = db.Column(db.Integer, nullable=True)
    act = db.Column(db.String(50), default='', nullable=True)

    passport_request_id = db.Column(db.Integer, nullable=True)

    edit_reason_text = db.Column(db.String(255), default='', nullable=True)

    def show_citizenship(self):
        if not self.citizenship_id:
            return None
        citizenship_list = []
        for citizenship in self.citizenship_id:
            url = f'{EIAS_BASE_URL}{EIAS_GET_STATE}{citizenship}/'
            response = request_to_passport(url)
            citizenship_list.append(response.json() if response.status_code is 200 else {None})
        return citizenship_list

    def show_dmsu_edit(self):
        if not self.dmsu_edit_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{self.dmsu_edit_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def show_dmsu_add(self):
        if not self.dmsu_add_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{self.dmsu_add_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def show_dmsudep_issue(self):
        if not self.dmsudep_issue_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{self.dmsudep_issue_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def show_user_add(self):
        if not self.user_add_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{self.user_add_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

    def show_user_edit(self):
        if not self.user_edit_id:
            return None
        url = f'{EIAS_BASE_URL}{EIAS_GET_USER}{self.user_edit_id}/'
        response = request_to_passport(url)
        return response.json() if response.status_code is 200 else None

 # r'^api/v1/get_doc_status/' r'^api/v1/get_doc_status/{id}/'
# r'^api/v1/get_doc_type/' r'^api/v1/get_doc_type/{id}/'


class DocLost(db.Model, DocLostMixin):
    __tablename__ = 'doc_lost'


class DocLostHistory(db.Model, DocLostMixin):
    __tablename__ = 'doc_lost_history'

    source = db.relationship('DocLost', lazy=True, backref="history")
    source_id = db.Column(db.Integer, db.ForeignKey('doc_lost.id'), nullable=True)


class DocLostUploadStatusEnum(enum.Enum):
    PROCESS, DONE, PARTLY_DONE, ERROR = \
          0,    1,           2,     4


class DocLostUpload(db.Model, DocLostMixin):
    __tablename__ = 'doc_lost_uploads'

    file_upload = db.Column(db.String(255), nullable=True)
    file_upload_log = db.Column(db.String(255), nullable=True)
    file_upload_partial = db.Column(db.String(255), nullable=True)
    dep_add_id = db.Column(db.Integer, nullable=True)
    user_add_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.Enum(DocLostUploadStatusEnum), default=DocLostUploadStatusEnum.PROCESS)
    celery_id = db.Column(db.Integer, nullable=True)


class DocLostChangeRequest(db.Model, ModelMixin):
    __tablename__ = 'doc_lost_change_request'

    doc_lost_id = db.Column(db.Integer, db.ForeignKey('doc_lost.id'))
    doc_lost = db.relationship('DocLost', backref=db.backref('change_requests', lazy='dynamic'))

    text = db.Column(db.Text)
    reject_text = db.Column(db.Text)

    active = db.Column(db.Boolean, default=True)
    approved = db.Column(db.Boolean, default=False)

    region_add_id = db.Column(db.Integer, nullable=True)
    region_processed_id = db.Column(db.Integer, nullable=True)

    dep_add_id = db.Column(db.Integer, nullable=True)
    dep_processed_id = db.Column(db.Integer, nullable=True)

    user_add_id = db.Column(db.Integer, nullable=True)
    user_processed_id = db.Column(db.Integer, nullable=True)
