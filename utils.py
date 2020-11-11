import base64
import binascii
import json
import os
import re
from datetime import datetime
from functools import wraps
from urllib.parse import parse_qs

import requests
from flask import request, abort, Response, jsonify

from config import EIAS_USER_ME, EIAS_USER_IS_AUTHENTICATED, INACTIVE_CSV_DIR, EIAS_GET_DEP, EIAS_GET_STATE, PERMISSIONS
from oauth_processing import EIAS_BASE_URL


def request_to_passport(url, method='GET', data=None, query_params=None):
    from models import OAuth2Token
    if 'api/v1/pdf/' in request.base_url:
        token = request.token
    else:
        token = request.headers['Authorization'].replace('Bearer ', '')
    token_obj = OAuth2Token.query.filter_by(access_token=token).first()
    if not token_obj:
        return abort(403)
    token_type, access_token = (token_obj.token_type, token_obj.access_token) if token_obj else ('None', '')
    headers = {'Authorization': f'{token_type} {access_token}'}

    cookies = dict(sessionid=token_obj.session_key)
    if method == 'GET':
        response = requests.get(url, headers=headers, cookies=cookies, params=query_params)
    else:
        headers.update({"Content-Type": "application/json"})
        response = requests.post(url, headers=headers, cookies=cookies, data=json.dumps(data))
    return response


def get_current_user():
    url = EIAS_BASE_URL + EIAS_USER_ME
    user = request_to_passport(url).json()
    return user


def filter_queryset(filter_args, Model):
    filter_args = filter_args.copy()
    filter_args.pop('page', None)
    filter_args.pop('per_page', None)
    qs = Model.query.filter()
    for k, v in filter_args.items():
        if '__from' in k:
            date_ = str.replace(k, '__from', '')
            qs = qs.filter(getattr(Model, date_) >= datetime.strptime(v, '%Y.%m.%d'))
        elif '__to' in k:
            date_ = str.replace(k, '__to', '')
            qs = qs.filter(getattr(Model, date_) <= datetime.strptime(v, '%Y.%m.%d'))
        elif 'dmsu_add_code' in k:
            url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}?code={v}'
            response = request_to_passport(url)
            dep_id = response.json()[0].get('id', '') if len(response.json()) > 0 else None
            qs = qs.filter_by(dmsu_add_id=dep_id)
        else:
            qs = qs.filter(getattr(Model, k) == v)
    return qs


def is_authenticated(func):
    from models import OAuth2Token
    @wraps(func)
    def wrapper(*args, **kws):
        if 'api/v1/pdf/' in request.base_url:
            try:
                decoded_data = base64.b64decode(kws['pdf_data']).decode('utf-8')
            except binascii.Error:
                return jsonify({'error': 'Url not valid'}), 400
            data_dict = parse_qs(decoded_data.replace('?', ''))
            request.token = data_dict['token'][0] if data_dict['token'] else None
            token = request.token
        else:
            if not 'Authorization' in request.headers:
                abort(401)
            token = request.headers['Authorization'].replace('Bearer ', '')
        url = EIAS_BASE_URL + EIAS_USER_IS_AUTHENTICATED
        token_obj = OAuth2Token.query.filter_by(access_token=token).first()

        response = request_to_passport(url)
        if response.status_code != 200:
            return Response(response.text, status=response.status_code, mimetype='application/json')
        if token_obj.ip_address and token_obj.ip_address != request.remote_addr:
            return Response("invalid ip", status=401, mimetype='application/json')
        return func(*args, **kws)
    return wrapper


def has_permission(group_list: [tuple, list]):
    from models import DocLost

    def actual_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return abort(403)
            user_groups = user.get('groups').values()

            if PERMISSIONS['edit_own'] in group_list and PERMISSIONS['edit_own'] in user_groups:
                doc_lost = DocLost.query.get_or_404(kwargs['doc_id'])
                user_dmsudep_id = user.get('dmsudep_id')
                edit_own = str(doc_lost.dmsu_add_id) == str(user_dmsudep_id)
                if edit_own:
                    return func(*args, **kwargs)
                if PERMISSIONS['edit_region'] not in user_groups:
                    return Response("user has not permission for this action", status=403, mimetype='application/json')

            if PERMISSIONS['edit_region'] in group_list and PERMISSIONS['edit_region'] in user_groups:
                doc_lost = DocLost.query.get_or_404(kwargs['doc_id'])
                url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{doc_lost.dmsu_add_id}/'
                dep = request_to_passport(url).json()
                edit_region = str(dep.get('region')) == str(user.get('dmsudep_region_id'))
                if edit_region and PERMISSIONS['edit_region'] in user_groups:
                    return func(*args, **kwargs)
                else:
                    return Response(f"user has not permission for this action", status=403, mimetype='application/json')

            for group in group_list:
                if group not in user_groups:
                    return Response(f"user has not permission for this action", status=403, mimetype='application/json')
            return func(*args, **kwargs)
        return wrapper
    return actual_decorator


def date_from_str(date_str, date_format='%d-%m-%Y'):
    """
    Перевод даты-времени из текста в дату по заданому формату
    :param date_str:
    :param date_format:
    :return:
    """
    from datetime import datetime
    date = None
    if date_str:
        try:
            date = datetime.strptime(date_str, date_format)
        except ValueError:
            pass
    return date


def upload_file_validation(upload_file):
    """
     Перевірка файла з недійсними документами, що завантажуються через WEB інтерфейс на коректність
    :param upload_file: шлях до файлу
    :return:
    """
    try:
        upload_file.read()
        upload_file.seek(0)
    except Exception as e:
        return False, str(e), ''

    file_name = upload_file.filename
    validation_name_file = r'^INACTIVE_[0-9]{4}_[0-9]{8}_[0-9]{4}'
    name, ext = os.path.splitext(file_name)
    if str(ext).lower() == '.csv' and re.match(validation_name_file, name):
        inactive, depcode, date_str, time = name.split('_')
        if date_from_str(date_str, date_format="%Y%m%d"):
            if not os.path.isfile(os.path.join(INACTIVE_CSV_DIR, file_name)):
                url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}?code={depcode}'
                response = request_to_passport(url)
                if response.status_code == 200 and response.json() and len(response.json()) > 0:
                    return True, '', response.json()[0].get('id')
                else:
                    return False, f'В БД відсутній підрозділ {depcode}', ''
            return False, 'файл вже було завантажено', ''
        return False, 'Невірний формат дати', ''
    return False, 'Невірний формат імені файлу', ''


def date_from_invalid_csv(date_str):
    """
    конвертація дат для БД (для завантаження недійсних документів через WEB інтерфейс)
    :param date_str:
    :return:
    """
    date_dot = u'^[0-9]{2}.[0-9]{2}.[0-9]{4}'
    date_sm = u'^[0-9]{8}'
    date_dash = u'^[0-9]{2}-[0-9]{2}-[0-9]{4}'
    date_t = None

    if re.match(date_dot, date_str):
        date_t = date_from_str(date_str, date_format="%d.%m.%Y")
    elif re.match(date_sm, date_str):
        date_t = date_from_str(date_str, date_format="%d%m%Y")
    elif re.match(date_dash, date_str):
        date_t = date_from_str(date_str, date_format="%d-%m-%Y")
    if date_t:
        if not (date_t.year > 1900 and date_t.year < 2100):
            date_t = None

    if date_str > '' and not date_t:
        date_t = date_str
    return date_t


def get_dep_by_code(dmsudep):
    """
    пошук підрозділу за кодом (для завантаження недійсних документів через WEB інтерфейс)
    :param dmsudep: code or name
    :return:
    """
    url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}?code={dmsudep}'
    dep = request_to_passport(url).json()[0] if request_to_passport(url).json() else {}
    return dep


def get_citizenship_by_name(citizenship_name):
    url = f'{EIAS_BASE_URL}{EIAS_GET_STATE}?code_eng={citizenship_name}'
    citizenship = request_to_passport(url).json()[0] if request_to_passport(url).json() else {}
    return citizenship


def dict_to_list_row(row, fieldlist, delimiter=';'):
    """
    Функція створює строку csv для файлу з помилками
    ввикористовується в body_upload_doc_inactive
    :param row:
    :param fieldlist:
    :param delimiter:
    :return:
    """
    row_list = ''
    for key in fieldlist:
        if key in row:
            try:
                row_list += row[key]+delimiter
            except TypeError:
                pass

    row_list += "\n"
    return row_list


def get_history(doc_lost, history_queryset):
    from models import db, DocLost, DocType, Reason, DataSourceType
    from schemas import DocTypeListSchema, DocReasonListSchema

    data_to_show = []

    fields = db.inspect(DocLost).columns.keys()
    fields_to_exclude = ('id', 'updated_at', 'created_at', 'dmsu_edit_id', 'dmsu_add_id', 'user_add_id', 'user_edit_id')
    date_fields = ('date_birth', 'issue_date', 'exp_date', 'date_invalid', 'date_add', 'date_destruction', 'date_destruction_created')
    doc_lost_fields = [key for key in fields if key not in fields_to_exclude]

    history_data_new = {key: getattr(doc_lost, key) for key in doc_lost_fields if key not in fields_to_exclude}
    new_instance = doc_lost
    for old_instance in history_queryset:
        history_data_old = {key: getattr(old_instance, key) for key in doc_lost_fields if
                            key not in ('id', 'updated_at', 'created_at')}
        data = {}
        data_to_show.append(data)
        for field in doc_lost_fields:
            if history_data_new[field] != history_data_old[field]:
                to_represent = {'new': history_data_new[field], 'old': history_data_old[field]}
                if field == 'doc_type_id':
                    new = DocType.query.get(history_data_new[field])
                    old = DocType.query.get(history_data_old[field])
                    new = DocTypeListSchema().jsonify(new).json if new else None
                    old = DocTypeListSchema().jsonify(old).json if old else None
                    to_represent = {'new': new, 'old': old}
                    field = 'doc_type'
                elif field == 'reason_id':
                    new = Reason.query.get(history_data_new[field])
                    old = Reason.query.get(history_data_old[field])
                    new = DocReasonListSchema().jsonify(new).json if new else None
                    old = DocReasonListSchema().jsonify(old).json if old else None
                    to_represent = {'new': new, 'old': old}
                    field = 'reason'
                elif field == 'data_source_type_id':
                    new = DataSourceType.query.get(history_data_new[field])
                    old = DataSourceType.query.get(history_data_old[field])
                    to_represent = {'new': new.name if new else None, 'old': old.name if old else None}
                    field = 'data_source_type'
                elif field in date_fields:
                    new = history_data_new[field].strftime("%Y-%m-%d") if history_data_new[field] else None
                    old = history_data_old[field].strftime("%Y-%m-%d") if history_data_old[field] else None
                    to_represent = {'new': new, 'old': old}
                elif field == 'citizenship_id':
                    to_represent = {'new': new_instance.show_citizenship(), 'old': old_instance.show_citizenship()}
                    field = 'citizenship'
                elif field == 'dmsudep_issue_id':
                    to_represent = {'new': new_instance.show_dmsudep_issue(), 'old': old_instance.show_dmsudep_issue()}
                    field = 'dmsudep_issue'
                data[field] = to_represent
            if field == 'edit_reason_text':
                data[field] = old_instance.edit_reason_text
        data['created_at'] = old_instance.created_at.strftime("%Y-%m-%d %H:%M:%S")
        data['user_edited'] = old_instance.show_user_add()
        data['user_edited_dep'] = old_instance.show_dmsu_add()
        history_data_new = history_data_old
        new_instance = old_instance

    return data_to_show
