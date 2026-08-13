# RoadPulse — Incident module (user-facing side).
#
# Routes here match what the frontend already sends:
#   report.js     POST /api/incidents          (multipart/form-data, see report.html)
#   dashboard.js   GET /api/incidents/recent    -> feeds the Recent Incidents table + map

import os
import uuid

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import Incident, Log

incidents_bp = Blueprint('incidents', __name__)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
VALID_TYPES = {'Accident', 'Pothole', 'Waterlogging', 'Signal Fault', 'Roadblock', 'Other'}
VALID_SEVERITIES = {'low', 'medium', 'high'}


def _save_photo(file_storage):
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    filename = f'{uuid.uuid4().hex}{ext}'
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_storage.save(os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(filename)))
    return f'uploads/{filename}'  # stored relative to /static, e.g. /static/uploads/xxx.jpg


@incidents_bp.route('/api/incidents', methods=['POST'])
@login_required
def create_incident():
    form = request.form

    inc_type = (form.get('type') or '').strip()
    severity = (form.get('severity') or '').strip().lower()
    description = (form.get('description') or '').strip()
    location_desc = (form.get('location_desc') or '').strip()
    lat = form.get('lat')
    lng = form.get('lng')

    if inc_type not in VALID_TYPES:
        return jsonify({'message': 'Please select a valid incident type.'}), 400
    if severity not in VALID_SEVERITIES:
        return jsonify({'message': 'Please select a severity.'}), 400
    if not description or not location_desc:
        return jsonify({'message': 'Description and location are both required.'}), 400
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return jsonify({'message': 'Please pin the incident location on the map.'}), 400

    photo_path = None
    photo = request.files.get('photo')
    if photo and photo.filename:
        photo_path = _save_photo(photo)

    incident = Incident(
        user_id=current_user.id,
        reporter_name=current_user.name,  # logged in now, so use the real account name
        type=inc_type,
        severity=severity,
        description=description,
        location_desc=location_desc,
        lat=lat,
        lng=lng,
        photo_path=photo_path,
        status='pending'
    )
    db.session.add(incident)
    db.session.commit()

    db.session.add(Log(user_id=current_user.id, action='incident_reported',
                        target_type='incident', target_id=incident.id))
    db.session.commit()

    return jsonify({'message': 'Report submitted for review.', 'id': incident.id}), 201


@incidents_bp.route('/api/incidents/recent', methods=['GET'])
def recent_incidents():
    limit = request.args.get('limit', default=20, type=int)
    incidents = Incident.query.order_by(Incident.reported_at.desc()).limit(limit).all()
    return jsonify([i.to_dict() for i in incidents]), 200
