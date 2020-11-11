import base64
import binascii
import os
import datetime
from random import uniform
from time import sleep
from urllib.parse import parse_qs
import time

from flask import request, jsonify, abort, render_template
from sqlalchemy import desc
from flask_weasyprint import HTML, CSS, render_pdf

from config import CELERY_BROKER_URL, INACTIVE_CSV_DIR, PERMISSIONS, EIAS_BASE_URL, EIAS_GET_DEP, EIAS_GET_STATE, \
    UKRAINE, EIAS_USER_ME
from __init__ import create_app
from models import db, DocType, Reason, DocLost, DocLostHistory, DocLostChangeRequest, DataSourceType
from schemas import DocLostCreateSchema, DocTypeListSchema, DocReasonListSchema, DocLostListSchema, \
    DocLostUploadSchema, DocLostChangeRequestSchema, DocLostRetrieveSchema, DocLostChangeRequestListSchema
from utils import filter_queryset, get_current_user, is_authenticated, upload_file_validation, has_permission, \
    request_to_passport, get_history

from celery import Celery

app = create_app()
celery = Celery(
    'flask_tasks',
    broker=CELERY_BROKER_URL,
    backend='rpc://',
    include=['tasks']  # here should be all modules that have celery tasks
)  # there in no need for celery while we do not use upload_csv


@app.route('/api/v1/user/me/')
def user_me():
    """
    apo which used passports /api/v1/user/me/ and add permission to the data like view, add, etc.
    :return: json, status_code
    """
    url = EIAS_BASE_URL + EIAS_USER_ME
    user = request_to_passport(url).json()
    user_groups = user.get('groups').values()
    user['access'] = {
        'view': PERMISSIONS['view'] in user_groups,
        'add': PERMISSIONS['create'] in user_groups,
        'edit': PERMISSIONS['edit_region'] in user_groups or PERMISSIONS['edit_own'] in user_groups
    }
    return jsonify(user), 200


                                            #######################
                                            #### DockLost urls ####
                                            #######################


@app.route('/api/v1/doc_types/', methods=['GET'])
def get_doc_types_list():
    """
    List all DocLost types from table: DocType
    without pagination
    """
    type_schema = DocTypeListSchema()
    doc_types = DocType.query.all()
    return type_schema.jsonify(doc_types, many=True)


@app.route('/api/v1/doc_reasons/', methods=['GET'])
def get_doc_reason_list():
    """
    List all DocLost types from table: Reason
    without pagination
    """
    reason_schema = DocReasonListSchema()
    reasons = Reason.query.all()
    return reason_schema.jsonify(reasons, many=True)


@app.route('/api/v1/docs_inactive/', methods=['POST'])
@is_authenticated
@has_permission((PERMISSIONS['create'],))
def create_doc_inactive():
    """
    POST to create one item of DocLost
    """
    content_input = request.get_json()   # get data from request
    if not content_input:
        return abort(400)

    dmsudep_issue = {}
    if content_input.get('dmsudep_issue_id'):
        if str(content_input["dmsudep_issue_id"]).isdigit():
            url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{content_input["dmsudep_issue_id"]}/'
            response = request_to_passport(url)
            dmsudep_issue = response.json() if response.status_code is 200 else {}
        if not dmsudep_issue:
            url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}'
            response = request_to_passport(url, method='POST', data={'dmsudep_name': content_input["dmsudep_issue_id"]})
            dmsudep_issue = response.json() if response.status_code is 201 else {}
    content_input["dmsudep_issue_id"] = dmsudep_issue.get('id', None)
    doc_schema = DocLostCreateSchema()
    errors = doc_schema.validate(data=content_input)   # validate for errors in exists status_code is 400
    if not errors:
        user = get_current_user()
        user_dmsudep_id = user.get('dmsudep_id')
        content_input['user_add_id'] = user.get('id')
        content_input['dmsu_add_id'] = user_dmsudep_id
        content_input['data_source_type_id'] = DataSourceType.CUSTOM
        if content_input.get('date_destruction'):
            today = datetime.date.today()
            content_input['date_destruction_created'] = f'{today.year}-{today.month}-{today.day}'
        doc = doc_schema.load(content_input)
        db.session.add(doc)
        db.session.commit()
        return jsonify({'id': doc.id}), 201
    else:
        return jsonify(errors), 400


@app.route('/api/v1/docs_inactive/', methods=['GET'])
@is_authenticated
@has_permission((PERMISSIONS['view'],))
def get_doc_lost_list():
    """
    get list of DocLost with pagination
    frontend table required 'page' and 'per_page' parameters, if not then 400
    """
    if 'page' not in request.args.keys() and 'per_page' not in request.args.keys():
        return abort(400)
    page = int(request.args.get('page'))
    per_page = int(request.args.get('per_page'))
    doc_lost_schema = DocLostListSchema()
    queryset = filter_queryset(request.args, DocLost)    # custom filtration through all fields in table
    queryset = queryset.order_by(desc("created_at"))
    docs_lost = queryset.paginate(page=page, per_page=per_page)   # for pagination there is required page and per_page
    dump = {
        'data': doc_lost_schema.jsonify(docs_lost.items, many=True).json,
        'page': docs_lost.page,
        'per_page': docs_lost.per_page,
        'total': docs_lost.total,
        'total_pages': docs_lost.pages
    }
    return jsonify(dump)


@app.route('/api/v1/docs_inactive/<int:doc_id>/', methods=['GET'])
@is_authenticated
@has_permission((PERMISSIONS['view'],))
def get_doc_lost(doc_id):
    """
    Get DocLost by id with variable doc_id, if not exists than 404
    :table DocLost
    """
    doc_lost_schema = DocLostRetrieveSchema()
    doc_lost = DocLost.query.get_or_404(doc_id)
    return doc_lost_schema.jsonify(doc_lost)


@app.route('/api/v1/docs_inactive/<int:doc_id>/', methods=['PUT'])
@is_authenticated
@has_permission((PERMISSIONS['edit_own'], PERMISSIONS['edit_region']))
def update_doc_lost(doc_id):
    """
    PUT for update info in DocList by id
    """
    doc_lost = DocLost.query.get_or_404(doc_id)
    json_data = request.get_json()
    if not json_data:  # if there is no data  -> 400
        return jsonify({'message': 'Invalid request'}), 400
    user = get_current_user()
    user_dmsudep_id = user.get('dmsudep_id')
    if json_data.get('date_destruction'):
        today = datetime.date.today()
        json_data['date_destruction_created'] = f'{today.year}-{today.month}-{today.day}'
    doc_lost_schema = DocLostCreateSchema()
    errors = doc_lost_schema.validate(json_data, partial=True)   # validate for errors in exists status_code is 400
    if errors:
        return jsonify(errors), 400

    ################# save to history model #################

    # get all fields from table DocLost
    rows = db.inspect(DocLost).columns.keys()
    # create dictionary that will be update DocLostHistory
    history_data = {key: getattr(doc_lost, key) for key in rows if key not in ('id', 'updated_at', 'created_at')}
    history_data['source_id'] = doc_id
    history_data['user_edit_id'] = user.get('id')
    history_data['dmsu_edit_id'] = user_dmsudep_id
    db.session.bulk_insert_mappings(DocLostHistory, (history_data,))   # save all data from history_data

    data = doc_lost_schema.load(json_data, instance=doc_lost)
    db.session.add(data)
    db.session.commit()   # save all data to database that was added to db.session
    return jsonify({'id': data.id}), 200


                                            ##############################
                                            #### DockLostHistory urls ####
                                            ##############################


@app.route('/api/v1/docs_inactive_history/<int:doc_id>/', methods=['GET'])
@is_authenticated
@has_permission((PERMISSIONS['view'],))
def get_doc_lost_history_list(doc_id):
    """
    List DocLostHistory data order_by "-created_at"
    allows filtering
    """
    data_to_show = []
    doc_lost = DocLost.query.get_or_404(doc_id)

    queryset = filter_queryset(request.args, DocLostHistory)
    queryset = queryset.filter_by(source_id=doc_id)
    queryset = queryset.order_by(desc("created_at"))
    if queryset.count() == 0:
        return jsonify(data_to_show)

    data_to_show = get_history(doc_lost, queryset)
    return jsonify(data_to_show)


                                            ###################################
                                            #### DockLosChangeRequest urls ####
                                            ###################################


@app.route('/api/v1/doc_lost/change_request/', methods=['POST'])
@is_authenticated
def doc_lost_change_request():
    """
    Add change_request with POST
    :table DocLostChangeRequestSchema
    """
    sleep(uniform(0, 1))  # sleep for situation with double click to prevent saving duplicated
    json_data = request.get_json()
    doc_lost = DocLost.query.get_or_404(json_data.get('doc_lost_id'))
    change_request = doc_lost.change_requests.filter_by(active=True).first()   # validate if the change_requests exists
    if change_request:
        return "The doc already has change request", 400

    doc_lost_change_request_schema = DocLostChangeRequestSchema()
    errors = doc_lost_change_request_schema.validate(json_data)  # validate for errors in exists status_code is 400
    if errors:
        return jsonify(errors), 400
    user = get_current_user()
    user_dmsudep_id = user.get('dmsudep_id')
    json_data['user_add_id'] = user.get('id')
    json_data['dep_add_id'] = int(user.get('dmsudep_id'))  # add save user credentials

    url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{user_dmsudep_id}/'
    dep = request_to_passport(url).json()    # request to passport in order to get dep region
    json_data['region_add_id'] = dep.get('region')
    data = doc_lost_change_request_schema.load(json_data)
    db.session.add(data)
    db.session.commit()
    return jsonify(message='Successfully created'), 201


@app.route('/api/v1/doc_lost/change_request_outcome/', methods=['GET'])
@is_authenticated
def change_requests_list_outcome():
    """
    get list of DocLostChangeRequest with pagination
    frontend table required 'page' and 'per_page' parameters, if not then 400
    allows filtering  and ordered_by "-created_at"
    """
    if 'page' not in request.args.keys() and 'per_page' not in request.args.keys():
        return abort(400)
    user = get_current_user()
    page = int(request.args.get('page'))
    per_page = int(request.args.get('per_page'))
    change_request_schema = DocLostChangeRequestListSchema()
    queryset = filter_queryset(request.args, DocLostChangeRequest)
    queryset = queryset.filter_by(user_add_id=user.get('id'))    # filter that show only outcome change requests
    queryset = queryset.order_by(desc("created_at"))
    change_requests = queryset.paginate(page=page, per_page=per_page)
    dump = {
        'data': change_request_schema.jsonify(change_requests.items, many=True).json,
        'page': change_requests.page,
        'per_page': change_requests.per_page,
        'total': change_requests.total,
        'total_pages': change_requests.pages
    }
    return jsonify(dump)


@app.route('/api/v1/doc_lost/change_request_income/', methods=['GET'])
@is_authenticated
def change_requests_list_income():
    page = int(request.args.get('page'))
    per_page = int(request.args.get('per_page'))
    change_request_schema = DocLostChangeRequestListSchema()
    queryset = filter_queryset(request.args, DocLostChangeRequest)

    user = get_current_user()
    user_groups = user.get('groups').values()
    user_dmsudep_id = user.get('dmsudep_id')

    if PERMISSIONS['edit_region'] in user_groups:  # if user has "edit_region" show all request from region
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{user_dmsudep_id}/'
        dep = request_to_passport(url).json()
        queryset = queryset.filter_by(region_add_id=dep.get('region'))
    elif PERMISSIONS['edit_own'] in user_groups:  # if user has "edit_own" show all request from his dmsudep
        queryset = queryset.join(DocLostChangeRequest.doc_lost).filter(DocLost.dmsu_add_id == user_dmsudep_id)
    queryset = queryset.order_by(desc("created_at"))
    change_requests = queryset.paginate(page=page, per_page=per_page)  # for pagination page and per_page is required
    dump = {
        'data': change_request_schema.jsonify(change_requests.items, many=True).json,
        'page': change_requests.page,
        'per_page': change_requests.per_page,
        'total': change_requests.total,
        'total_pages': change_requests.pages
    }
    return jsonify(dump)


@app.route('/api/v1/doc_lost/change_request/<int:change_request_id>/', methods=['GET'])
def change_requests_retrieve(change_request_id):
    """
    Get DocLostChangeRequest by id with variable change_request_id, if not exists than 404
    :table DocLostChangeRequest
    """
    change_request = DocLostChangeRequest.query.get_or_404(change_request_id)
    change_request_schema = DocLostChangeRequestSchema()
    return change_request_schema.jsonify(change_request)


@app.route('/api/v1/doc_lost/change_request/<int:change_request_id>/', methods=['PUT'])
def change_requests_approve(change_request_id):
    """
    Make changes to DocLostChangeRequest object
    makes the object inactive -> active=False
    if json_data['approve'] is True? approved field change to True
    if json_data['approve'] is False, approved field do not change
    """
    user = get_current_user()
    user_dmsudep_id = user.get('dmsudep_id')
    change_request = DocLostChangeRequest.query.get_or_404(change_request_id)
    change_request.active = False  # make it False by default
    change_request.user_processed_id = user.get('id')
    change_request.dep_processed_id = user_dmsudep_id

    url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{user_dmsudep_id}/'
    dep = request_to_passport(url).json()
    change_request.region_processed_id = dep.get('region')   # request to passport in order to get dep region

    json_data = request.get_json()
    if json_data['approve']:
        change_request.approved = json_data['approve']  # if json_data['approve'] is True, approved field change to True
    else:
        change_request.reject_text = json_data['reject_text']
    db.session.add(change_request)
    db.session.commit()
    return jsonify(message='Successfully updated'), 200


                                            ############################
                                            #### Upload DocLost csv ####
                                            ############################


@app.route('/upload_doc_lost_file/', methods=['POST'])
@is_authenticated
def upload_inactive():
    if not request.files:  # if no files than 400
        return 'There is no file in request', 400
    upload = request.files['doc_lost']
    is_valid, message, dmsudep_owner_id = upload_file_validation(upload)   # the validation used from passport

    user = get_current_user()
    user_dmsudep_id = user.get('dmsudep_id')

    if is_valid:
        save_path = os.path.join(INACTIVE_CSV_DIR, upload.filename)
        if not os.path.exists(INACTIVE_CSV_DIR):
            os.makedirs(INACTIVE_CSV_DIR)
        upload.save(save_path)
        doc_schema = DocLostUploadSchema()
        obj = doc_schema.load(data={          # save all data and send to celery
            "file_upload": save_path,
            "dep_add_id": user_dmsudep_id,
            "user_add_id": user.get('id'),
        })
        db.session.add(obj)
        db.session.commit()
        task = celery.send_task('tasks.save_docs_lost', args=[obj.id], kwargs={})
        # tasks.save_docs_lost(obj.id)
        return '', 200
    else:
        return message, 400


@app.route('/api/v1/check_passport/', methods=['GET'])
@is_authenticated
def check_passport():
    doc_type = int(request.args.get('doc_type'))   # validate parameters that take part in querying
    series = request.args.get('series', None)
    number = request.args.get('number')

    if doc_type == DocType.P and not series:
        return jsonify({'error': 'there are not enough fields has been send'}), 400
    if not number and not doc_type:
        return jsonify({'error': 'there are not enough fields has been send'}), 400

    doc_lost_qs = DocLost.query.filter_by(doc_type_id=doc_type, number=number)
    doc_lost_qs = doc_lost_qs.filter_by(series=series) if series else doc_lost_qs
    if doc_lost_qs.count() > 0:
        return jsonify({'error': "Doc lost have been found in DocLost table"}), 409

    url = f'{EIAS_BASE_URL}api/v1/get_passport/'
    query_params = {'doc_type': doc_type, 'number':number}
    if series: query_params['series'] = series
    response = request_to_passport(url, query_params=query_params)
    if response.status_code in [404, 400]:
        return jsonify({}), 200

    passport_data = response.json()
    dmsudep_issue = None
    if passport_data.get('dmsudep_issue'):
        url = f'{EIAS_BASE_URL}{EIAS_GET_DEP}{passport_data.get("dmsudep_issue")}/'
        response = request_to_passport(url)
        dmsudep_issue = response.json() if response.status_code is 200 else None

    url = f'{EIAS_BASE_URL}{EIAS_GET_STATE}{UKRAINE}/'
    response = request_to_passport(url)
    citizenship = response.json() if response.status_code is 200 else None

    data = {
        'first_name': passport_data.get('first_str'),
        'last_name': passport_data.get('last_str'),
        'middle_name': passport_data.get('middle_str'),
        'date_birth': passport_data.get('date_birth'),
        'dmsudep_issue': dmsudep_issue,
        'citizenship': [citizenship],
        'exp_date': passport_data.get('date_exp')
    }
    return jsonify(data), 200


@app.route('/api/v1/pdf/<pdf_data>', methods=['GET'])
@is_authenticated
def get_pdf(pdf_data):
    try:
        decoded_data = base64.b64decode(pdf_data).decode('utf-8')
    except binascii.Error:
        return jsonify({'error': 'Url not valid'}), 400
    data_dict = parse_qs(decoded_data.replace('?', ''))
    doc_id = data_dict['id'][0] if data_dict['id'] else None
    doc_lost = DocLost.query.get_or_404(doc_id)
    user = get_current_user()
    data = {
        'doc_lost': doc_lost,
        'history_objects': [],
        'user': user,
        'user_dep_name': user['dmsudep'].get(str(user.get('dmsudep_id', ''))),
        'ref_num': f'{doc_id}{time.strftime("%H%S%d%Y")}',
        'ref_date': time.strftime("%Y-%m-%d")
    }
    if data_dict.get('type') == ['full']:
        queryset = DocLostHistory.query.filter_by(source_id=doc_id).order_by(desc("created_at"))
        data['history_objects'] = get_history(doc_lost, queryset)

    def get_data_if_empty(obj_dict, name):
        result = obj_dict.get(name)
        if result is None or result is '':
            result = 'Не заповненно'
        return result

    def get_citizenship_if_empty(obj_dict, name):
        result = obj_dict.get(name)
        if result is None or result is '':
            result = 'Не заповненно'
        else:
            result = ', '.join([c['name'] for c in result])
        return result

    data['get_data_if_empty'] = get_data_if_empty
    data['get_citizenship_if_empty'] = get_citizenship_if_empty
    rendered_html = render_template('pdf_template.html', **data)
    rendered_css = render_template('pdf_styles.css')
    return render_pdf(HTML(string=rendered_html), stylesheets=[CSS(string=rendered_css)])


if __name__ == '__main__':
    app.run(host='0.0.0.0')
