# RoadPulse — Analytics module.
#
#   GET /api/analytics/summary -> { by_type: [...], by_hour: [...] }
#     feeds the two remaining dashboard charts (pie + hour-of-day line)
#   GET /api/dashboard/stats   -> stat card numbers, real data only
#
# by_hour note: there's no live traffic-speed feed in this project, so
# this is "incidents reported by hour of day" — a genuine proxy for
# activity patterns, not a fabricated congestion index.

from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, jsonify

from models import Incident

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/api/analytics/summary', methods=['GET'])
def summary():
    incidents = Incident.query.all()

    by_type = Counter(i.type for i in incidents)
    by_hour = Counter(i.reported_at.hour for i in incidents)

    return jsonify({
        'by_type': [{'type': t, 'count': c} for t, c in sorted(by_type.items())],
        'by_hour': [{'hour': h, 'count': by_hour.get(h, 0)} for h in range(24)]
    }), 200


@analytics_bp.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)

    active_incidents = Incident.query.filter(
        Incident.status.in_(['pending', 'verified'])
    ).count()

    reports_today = Incident.query.filter(Incident.reported_at >= today_start).count()
    reports_yesterday = Incident.query.filter(
        Incident.reported_at >= yesterday_start,
        Incident.reported_at < today_start
    ).count()

    # Real trend, not simulated — falls back to plain language when a
    # percentage wouldn't mean anything (e.g. divide-by-zero on day one).
    if reports_yesterday > 0:
        pct = round((reports_today - reports_yesterday) / reports_yesterday * 100)
        trend = 'up' if pct > 0 else 'down' if pct < 0 else 'flat'
        trend_text = f'{abs(pct)}% vs yesterday' if pct != 0 else 'Same as yesterday'
    elif reports_today > 0:
        trend, trend_text = 'up', 'New today'
    else:
        trend, trend_text = 'flat', 'No reports yet'

    return jsonify({
        'active_incidents': active_incidents,
        'reports_today': reports_today,
        'reports_today_trend': trend,
        'reports_today_trend_text': trend_text
    }), 200
