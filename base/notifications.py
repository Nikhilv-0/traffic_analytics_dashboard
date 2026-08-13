# RoadPulse — Notifications.
#
#   GET /api/notifications -> real events, not simulated:
#     - personal: your own incident reports being approved/rejected
#     - community: recent high-severity incidents reported by anyone
#   Merged and sorted by recency, most recent first.

from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from models import Log, Incident

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    items = []

    # Personal: outcomes on incidents this user reported
    own_reviews = Log.query.filter(
        Log.action.in_(['incident_approved', 'incident_rejected'])
    ).order_by(Log.timestamp.desc()).limit(20).all()

    for log in own_reviews:
        incident = Incident.query.get(log.target_id)
        if not incident or incident.user_id != current_user.id:
            continue
        verb = 'verified' if log.action == 'incident_approved' else 'rejected'
        items.append({
            'kind': 'approved' if verb == 'verified' else 'rejected',
            'text': f'Your {incident.type} report at {incident.location_desc} was {verb}.',
            'timestamp': log.timestamp.isoformat()
        })

    # Community: recent high-severity incidents (from anyone)
    high_severity = Incident.query.filter_by(severity='high') \
        .order_by(Incident.reported_at.desc()).limit(5).all()

    for inc in high_severity:
        items.append({
            'kind': 'alert',
            'text': f'New high-severity {inc.type.lower()} reported near {inc.location_desc}.',
            'timestamp': inc.reported_at.isoformat()
        })

    items.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(items[:8]), 200
