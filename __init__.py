from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from sqlalchemy_utils import database_exists, create_database

import config
from oauth_processing import eias, oauth_registration
from outside import outside_api
from models import db
from schemas import ma


def create_app():
    flask_app = Flask(__name__, template_folder='templates')
    flask_app.register_blueprint(outside_api, url_prefix='/api/v1')
    flask_app.register_blueprint(oauth_registration)
    CORS(flask_app, expose_headers='Authorization')
    flask_app.secret_key = config.SECRET_KEY
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    flask_app.app_context().push()
    db.init_app(flask_app)
    Migrate(flask_app, db)
    ma.init_app(flask_app)
    eias.init_app(flask_app)
    if not database_exists(config.DATABASE_CONNECTION_URI):
        print('Creating database.')
        create_database(config.DATABASE_CONNECTION_URI)
    db.create_all()
    return flask_app
