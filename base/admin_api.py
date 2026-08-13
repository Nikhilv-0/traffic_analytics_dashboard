# RoadPulse — Admin module.
#
# Routes here match what admin.js already expects:
#   GET  /api/admin/incidents/pending  -> [{ id, type, description, location, reported_at }, ...]
#   POST /api/admin/incidents/:id/approve
#   POST /api/admin/incidents/:id/reject
#   GET  /api/admin/sessions           -> [{ username, location, login_at }, ...]
#
# "Active sessions" note: Flask's session cookies don't give us a
# server-side list of who's currently logged in for free. This
# approximates it from the Log table: for each user, look at their most
# recent login/logout event — if it was a login with no logout after it,
# treat them as currently signed in. Good enough for a demo; a production
# system would use a server-side session store (e.g. Redis) instead.

from datetime import datetime
from sqlalchemy import func, and_

from flask import Blueprint, jsonify
from flask_login import current_user

from extensions import db
from models import Incident, Log, User
from auth import admin_required

admin_bp = Blueprint('admin_api', __name__)


@admin_bp.route('/api/admin/incidents/pending', methods=['GET'])
@admin_required
def pending_incidents():
    incidents = Incident.query.filter_by(status='pending') \
        .order_by(Incident.reported_at.desc()).all()
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
