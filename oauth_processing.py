from authlib.flask.client import OAuth
from flask import Blueprint, url_for, request, redirect
from furl import furl

from config import EIAS_OAUTH2_KEY, EIAS_OAUTH2_SECRET, EIAS_BASE_URL, FRONTED_URL, EIAS_USER_ME
from models import OAuth2Token, db
from schemas import OAuth2TokenSchema

oauth_registration = Blueprint('oauth', __name__)

eias = OAuth()


eias.register(
    name='passport',
    client_id=EIAS_OAUTH2_KEY,
    client_secret=EIAS_OAUTH2_SECRET,
    access_token_url=EIAS_BASE_URL + 'oauth2/token/',
    authorize_url=EIAS_BASE_URL + 'oauth2/authorize/',
    api_base_url=EIAS_BASE_URL,
)


@oauth_registration.route('/login')
def login():
    redirect_uri = url_for('oauth.authorize', _external=True)
    return eias.passport.authorize_redirect(redirect_uri)


@oauth_registration.route('/authorize/')
def authorize():
    token = eias.passport.authorize_access_token()
    user = eias.passport.get(f'{EIAS_USER_ME}').json()
    session = eias.passport.get(f'get_session/{user["id"]}/').json()
    token_schema = OAuth2TokenSchema()
    user_exists = OAuth2Token.query.filter_by(user_id=user["id"]).first()
    data = {
        "access_token": token['access_token'],
        "token_type": token['token_type'],
        "refresh_token": token['refresh_token'],
        "expires_at": token['expires_at'],
        "ip_address": request.remote_addr,
        "session_key": session['session_key']
    }
    if user_exists:
        token_obj = token_schema.load(data, instance=user_exists)
    else:
        data["user_id"] = user['id']
        token_obj = token_schema.load(data)
    db.session.add(token_obj)
    db.session.commit()
    return redirect(furl(FRONTED_URL).add({'token': token_obj.access_token}).url)
