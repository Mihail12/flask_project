import os

user = os.environ['POSTGRES_USER']
password = os.environ['POSTGRES_PASSWORD']
host = os.environ['POSTGRES_HOST']
database = os.environ['POSTGRES_DB']
port = os.environ['POSTGRES_PORT']

DATABASE_CONNECTION_URI = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'


EIAS_BASE_URL = os.environ['EIAS_BASE_URL']
FRONTED_URL = os.environ['FRONTED_URL']
SECRET_KEY = os.environ['SECRET_KEY']
EIAS_OAUTH2_KEY = os.environ['EIAS_OAUTH2_KEY']
EIAS_OAUTH2_SECRET = os.environ['EIAS_OAUTH2_SECRET']

EIAS_USER_IS_AUTHENTICATED = 'api/v1/user/is_authenticated/'
EIAS_USER_ME = 'api/v1/user/me/'
EIAS_GET_DEP = 'api/v1/service/get_dmsudep/'
EIAS_GET_USER = 'api/v1/get_user/'
EIAS_GET_STATE = 'api/v1/get_state/'
EIAS_GET_PASSPORT = 'api/v1/get_passport/'

EIAS_POST_UPDATE_INACTIVE_ID_FR = 'api/v1/document/lost/update_invalid_id_fr/'

CELERY_BROKER_URL = os.environ['CELERY_BROKER_URL']

ROOT_DIR = os.getcwd()
STATIC_DIR = os.path.join(ROOT_DIR, 'static')
INACTIVE_CSV_DIR = os.path.join(STATIC_DIR, 'inactive_csv')
INACTIVE_CSV_PARTIAL_DIR = os.path.join(STATIC_DIR, 'inactive_partial_csv')
INACTIVE_LOG_DIR = os.path.join(STATIC_DIR, 'inactive_log')


PERMISSIONS = {
    'view': 'view_inactive_doc',
    'create': 'create_inactive_doc',
    'edit_own': 'edit_own_inactive_doc',
    'edit_region': 'edit_region_inactive_doc',
}


# citizenship
UKRAINE = 233