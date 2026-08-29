# RoadPulse — core routes: authentication, incident reporting, and admin moderation.
#
# Endpoints:
#   Auth
#     POST /api/auth/register   { name, email, password }
#     POST /api/auth/login      { email, password, remember }
#     GET  /logout
#   Incidents (user-facing)
#     POST /api/incidents           multipart/form-data (see report.html)
#     GET  /api/incidents/recent    ?limit=20 -> dashboard's Recent Incidents table + map
#     GET  /api/incidents/mine      -> profile page's My Reports table (requires login)
#     GET  /api/incidents/active    -> full incidents list page (pending + verified)
#   Admin (requires an admin account)
#     GET    /api/admin/incidents               ?status=pending|verified|rejected|all
#     POST   /api/admin/incidents/<id>/approve
#     POST   /api/admin/incidents/<id>/reject
#     DELETE /api/admin/incidents/<id>          permanently deletes the report + its photo file
#     GET    /api/admin/sessions                see active_sessions() below for how this is derived

import os
import uuid
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, and_

from models import db, User, Incident, Log


def admin_required(view_func):
    """Like @login_required, but also requires role == 'admin'.

    Used by the admin routes below, and by app.py to protect the /admin
    page itself.
    """
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required.'}), 403
        return view_func(*args, **kwargs)
    return wrapped


# =====================================================================
# Auth
# =====================================================================

auth_bp = Blueprint('auth', __name__)


def _log(action, user_id=None):
    db.session.add(Log(user_id=user_id, action=action))
    db.session.commit()


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or not password:
        return jsonify({'message': 'Name, email, and password are all required.'}), 400
    if len(password) < 8:
        return jsonify({'message': 'Password must be at least 8 characters.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'An account with that email already exists.'}), 409

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    _log('register', user_id=user.id)

    return jsonify({'message': 'Account created.'}), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def login_api():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    remember = bool(data.get('remember'))

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid email or password.'}), 401

    login_user(user, remember=remember)
    _log('login', user_id=user.id)

    redirect_to = '/admin' if user.role == 'admin' else '/dashboard'
    return jsonify({'message': 'Signed in.', 'redirect': redirect_to}), 200


@auth_bp.route('/logout')
@login_required
def logout():
    _log('logout', user_id=current_user.id)
    logout_user()
    return redirect(url_for('login'))


# =====================================================================
# Incidents (user-facing)
# =====================================================================

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


@incidents_bp.route('/api/incidents/mine', methods=['GET'])
@login_required
def my_incidents():
    incidents = Incident.query.filter_by(user_id=current_user.id) \
        .order_by(Incident.reported_at.desc()).all()
    return jsonify([i.to_dict() for i in incidents]), 200


@incidents_bp.route('/api/incidents/active', methods=['GET'])
def active_incidents():
    # "Active" matches the definition already used for the dashboard's
    # Active Incidents stat card (services.py) — pending + verified,
    # i.e. not yet rejected.
    incidents = Incident.query.filter(Incident.status.in_(['pending', 'verified'])) \
        .order_by(Incident.reported_at.desc()).all()
    return jsonify([i.to_dict() for i in incidents]), 200


# =====================================================================
# Admin moderation
# =====================================================================
#
# "Active sessions" note: Flask's session cookies don't give us a
# server-side list of who's currently logged in for free. This
# approximates it from the Log table: for each user, look at their most
# recent login/logout event — if it was a login with no logout after it,
# treat them as currently signed in. Good enough for a demo; a production
# system would use a server-side session store (e.g. Redis) instead.

admin_bp = Blueprint('admin_api', __name__)

VALID_STATUSES = {'pending', 'verified', 'rejected'}


@admin_bp.route('/api/admin/incidents', methods=['GET'])
@admin_required
def list_incidents():
    # ?status=pending (default) | verified | rejected | all
    status = request.args.get('status', 'pending')
    query = Incident.query
    if status != 'all':
        if status not in VALID_STATUSES:
            return jsonify({'message': f'Unknown status "{status}".'}), 400
        query = query.filter_by(status=status)
    incidents = query.order_by(Incident.reported_at.desc()).all()
    return jsonify([i.to_dict() for i in incidents]), 200


def _review(incident_id, new_status, log_action):
    incident = Incident.query.get(incident_id)
    if not incident:
        return jsonify({'message': 'Incident not found.'}), 404

    incident.status = new_status
    incident.reviewed_by = current_user.id
    incident.reviewed_at = datetime.utcnow()
    db.session.add(Log(user_id=current_user.id, action=log_action,
                        target_type='incident', target_id=incident.id))
    db.session.commit()
    return jsonify({'message': f'Incident #{incident_id} {new_status}.'}), 200


@admin_bp.route('/api/admin/incidents/<int:incident_id>/approve', methods=['POST'])
@admin_required
def approve_incident(incident_id):
    return _review(incident_id, 'verified', 'incident_approved')


@admin_bp.route('/api/admin/incidents/<int:incident_id>/reject', methods=['POST'])
@admin_required
def reject_incident(incident_id):
    return _review(incident_id, 'rejected', 'incident_rejected')


@admin_bp.route('/api/admin/incidents/<int:incident_id>', methods=['DELETE'])
@admin_required
def delete_incident(incident_id):
    """Permanently remove a report — for spam, duplicates, or test data.

    Unlike reject (which keeps the record with status='rejected' for the
    audit trail), this actually deletes the row and its uploaded photo
    file, if any. The deletion itself is still logged so there's a record
    that it happened, even though the incident data itself is gone.
    """
    incident = Incident.query.get(incident_id)
    if not incident:
        return jsonify({'message': 'Incident not found.'}), 404

    if incident.photo_path:
        photo_file = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(incident.photo_path))
        if os.path.exists(photo_file):
            os.remove(photo_file)

    db.session.add(Log(user_id=current_user.id, action='incident_deleted',
                        target_type='incident', target_id=incident.id))
    db.session.delete(incident)
    db.session.commit()

    return jsonify({'message': f'Incident #{incident_id} deleted.'}), 200


@admin_bp.route('/api/admin/sessions', methods=['GET'])
@admin_required
def active_sessions():
    latest_ts = db.session.query(
        Log.user_id, func.max(Log.timestamp).label('ts')
    ).filter(Log.action.in_(['login', 'logout'])).group_by(Log.user_id).subquery()

    latest_logins = db.session.query(Log, User).join(
        latest_ts, and_(Log.user_id == latest_ts.c.user_id, Log.timestamp == latest_ts.c.ts)
    ).join(User, User.id == Log.user_id).filter(Log.action == 'login').all()

    sessions = [{
        'username': user.name,
        'location': None,
        'login_at': log.timestamp.isoformat()
    } for log, user in latest_logins]

    return jsonify(sessions), 200
