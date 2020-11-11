from flask import Blueprint, jsonify, request, abort

from models import DocLost, db, DocLostHistory
from schemas import DocLostAliensSchema
from utils import is_authenticated, get_current_user

outside_api = Blueprint('aliens_api', __name__)


@outside_api.route("/document/inactive/", methods=['GET'])
@is_authenticated
def document_inactive_get():
    """
    List DocLost with filter_by: doc_type, series and number
    """
    doc_lost_schema = DocLostAliensSchema()

    doc_type = request.args.get('doc_type')   # validate parameters that take part in querying
    series = request.args.get('series', None)
    number = request.args.get('number')
    if not doc_type:
        return jsonify({"error": 'doc_type parameter is required'}), 400
    if not number:
        return jsonify({"error": 'number parameter is required'}), 400

    doc_lost_qs = DocLost.query.filter_by(doc_type_id=doc_type, number=number)
    if series:
        doc_lost_qs = doc_lost_qs.filter_by(series=series)
    doc_lost = doc_lost_qs.first()
    if not doc_lost:
        abort(404)
    return doc_lost_schema.jsonify(doc_lost)


@outside_api.route("/document/inactive/", methods=['POST'])
@is_authenticated
def document_inactive_post():
    content_input = request.get_json()
    if not content_input.get('doc_type_id'):
        return jsonify({"error": 'doc_type_id parameter is required'}), 400
    if not content_input.get('number'):
        return jsonify({"error": 'number parameter is required'}), 400
    doc_lost_qs = DocLost.query.filter_by(doc_type_id=content_input.get('doc_type_id'),
                                          number=content_input.get('number'))
    if content_input.get('series'):
        doc_lost_qs = doc_lost_qs.filter_by(series=content_input.get('series'))
    doc_lost = doc_lost_qs.first()
    if doc_lost:
        return jsonify({'id': doc_lost.id}), 409

    doc_schema = DocLostAliensSchema()
    errors = doc_schema.validate(data=content_input)
    if not errors:
        content_input['user_add_id'] = get_current_user().get('id')
        doc_lost = doc_schema.load(content_input)
        db.session.add(doc_lost)
        db.session.commit()
        return jsonify({'id': doc_lost.id}), 201
    else:
        return jsonify(errors), 400


@outside_api.route("/document/inactive/<int:doc_id>/", methods=['PUT'])
@is_authenticated
def document_inactive_edit(doc_id):
    doc_lost = DocLost.query.get_or_404(doc_id)
    json_data = request.get_json()
    if not json_data:
        return jsonify({'message': 'Invalid request'}), 400

    user = get_current_user()
    user_dmsudep_id = user.get('dmsudep_id')
    if doc_lost.dmsudep_issue_id != int(user_dmsudep_id):
        return jsonify({'message': f'Only dep with id:{user_dmsudep_id} could update the document'}), 403

    json_data['user_edit_id'] = user.get('id')
    doc_lost_schema = DocLostAliensSchema()
    errors = doc_lost_schema.validate(json_data, partial=True)
    if errors:
        return jsonify(errors), 400

    ################# save to history model #################

    rows = db.inspect(DocLost).columns.keys()
    history_data = {key: getattr(doc_lost, key) for key in rows if key not in ('id', 'updated_at', 'created_at')}
    history_data['source_id'] = doc_id
    db.session.bulk_insert_mappings(DocLostHistory, (history_data,))

    data = doc_lost_schema.load(json_data, instance=doc_lost)
    db.session.add(data)
    db.session.commit()
    return jsonify(message='Successfully updated'), 201