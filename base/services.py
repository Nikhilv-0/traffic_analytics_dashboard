# RoadPulse — supporting services: analytics, notifications, weather,
# congestion predictions, and the downloadable docs.
#
# Endpoints:
#   Analytics
#     GET /api/analytics/summary   { by_type, by_hour } -> dashboard charts
#     GET /api/dashboard/stats     stat card numbers (real data only)
#   Notifications
#     GET /api/notifications       personal + community events (requires login)
#   Weather
#     GET /api/weather             current conditions via Open-Meteo, 10-min cache
#   Predictions
#     GET /api/predictions         heuristic congestion forecast (see _compute_predictions)
#   Docs
#     GET /docs/api                downloadable API reference (text file)
#     GET /docs/about              downloadable "about this project" blurb (text file)

import time
from collections import Counter
from datetime import datetime, timedelta

import requests
from flask import Blueprint, jsonify, Response
from flask_login import login_required, current_user

from models import db, Incident, Prediction, Log


# =====================================================================
# Analytics
# =====================================================================
#
# by_hour note: there's no live traffic-speed feed in this project, so
# this is "incidents reported by hour of day" — a genuine proxy for
# activity patterns, not a fabricated congestion index.

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


# =====================================================================
# Notifications
# =====================================================================
#
#   GET /api/notifications -> real events, not simulated:
#     - personal: your own incident reports being approved/rejected
#     - community: recent high-severity incidents reported by anyone
#   Merged and sorted by recency, most recent first.

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


# =====================================================================
# Weather
# =====================================================================
#
# Uses Open-Meteo (https://open-meteo.com) — free, no API key or signup
# required for non-commercial use. Called server-side (not from the
# browser) so we can cache it and keep the frontend simple.

weather_bp = Blueprint('weather', __name__)

# Keep in sync with CITY_CENTER in static/dashboard.js and static/report.js
# Andheri, Mumbai Suburban
CITY_CENTER = (19.1136, 72.8697)

# WMO weather codes -> (human label, icon key). Icon keys are mapped to
# Bootstrap Icons classes on the frontend (see dashboard.js).
WEATHER_CODES = {
    0: ('Clear Sky', 'sun'),
    1: ('Mainly Clear', 'cloud-sun'),
    2: ('Partly Cloudy', 'cloud-sun'),
    3: ('Overcast', 'clouds'),
    45: ('Fog', 'cloud-fog'),
    48: ('Depositing Rime Fog', 'cloud-fog'),
    51: ('Light Drizzle', 'cloud-drizzle'),
    53: ('Moderate Drizzle', 'cloud-drizzle'),
    55: ('Dense Drizzle', 'cloud-drizzle'),
    61: ('Slight Rain', 'cloud-rain'),
    63: ('Moderate Rain', 'cloud-rain'),
    65: ('Heavy Rain', 'cloud-rain-heavy'),
    71: ('Slight Snow', 'cloud-snow'),
    73: ('Moderate Snow', 'cloud-snow'),
    75: ('Heavy Snow', 'cloud-snow'),
    80: ('Rain Showers', 'cloud-rain'),
    81: ('Rain Showers', 'cloud-rain'),
    82: ('Violent Rain Showers', 'cloud-rain-heavy'),
    95: ('Thunderstorm', 'cloud-lightning'),
    96: ('Thunderstorm w/ Hail', 'cloud-lightning-rain'),
    99: ('Thunderstorm w/ Hail', 'cloud-lightning-rain'),
}

# Simple in-memory cache — avoids hitting Open-Meteo on every dashboard
# load/refresh. Fine for a single-process dev server; swap for Flask-Caching
# + Redis if this ever runs multi-process.
_cache = {'data': None, 'fetched_at': 0}
CACHE_TTL_SECONDS = 600  # 10 minutes


@weather_bp.route('/api/weather', methods=['GET'])
def get_weather():
    now = time.time()
    if _cache['data'] and (now - _cache['fetched_at']) < CACHE_TTL_SECONDS:
        return jsonify(_cache['data']), 200

    try:
        resp = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': CITY_CENTER[0],
                'longitude': CITY_CENTER[1],
                'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m',
                'timezone': 'auto'
            },
            timeout=5
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException:
        return jsonify({'message': 'Weather service is temporarily unavailable.'}), 502

    current = payload.get('current', {})

    # Defensive: Open-Meteo's docs/SDKs are inconsistent between
    # `weather_code` (current API) and the legacy `weathercode` naming.
    code = current.get('weather_code', current.get('weathercode', 0))
    condition, icon = WEATHER_CODES.get(code, ('Unknown', 'cloud'))

    data = {
        'tempC': round(current.get('temperature_2m', 0)),
        'condition': condition,
        'icon': icon,
        'humidity': round(current.get('relative_humidity_2m', 0)),
        'windKmh': round(current.get('wind_speed_10m', 0))
    }

    _cache['data'] = data
    _cache['fetched_at'] = now

    return jsonify(data), 200


# =====================================================================
# Predictions
# =====================================================================
#
#   GET /api/predictions -> [{ road, level, pct, generated_at }, ...]
#     feeds the dashboard's Congestion Forecast panel
#
# Heuristic, not a real traffic feed: there's no live speed/volume data
# source in this project, and Incident has no formal "road" identifier
# (report.js only collects a free-text location_desc). So this proxies
# congestion from recent incident *density* at each reported location —
# how many incidents were reported there recently, weighted by severity
# and how fresh each report is. That's a genuine signal (more/worse
# reports near a spot correlates with disruption), but it is explicitly
# NOT a measurement of actual traffic speed. Locations with zero recent
# incidents simply don't appear — there's nothing to infer congestion
# from there, so we don't invent a "Low" reading for them.
#
# Each call recomputes the forecast from current data and replaces the
# previous batch in the Prediction table (it's a live snapshot, not
# accumulated history) — see _compute_predictions().

predictions_bp = Blueprint('predictions', __name__)

WINDOW_HOURS = 3   # only consider incidents reported in the last N hours
MAX_ROADS = 5      # cap how many locations show up in the forecast panel
SEVERITY_WEIGHT = {'low': 1, 'medium': 2, 'high': 3}


def _score_for(incident, now):
    """Recency-weighted severity score for one incident.

    A fresh report counts fully; one at the edge of the window counts
    for almost nothing. Linear decay keeps the math easy to reason about
    and easy to re-tune (just WINDOW_HOURS) later.
    """
    age_minutes = (now - incident.reported_at).total_seconds() / 60
    window_minutes = WINDOW_HOURS * 60
    recency = max(0.0, 1 - (age_minutes / window_minutes))
    weight = SEVERITY_WEIGHT.get(incident.severity, 1)
    return weight * recency


def _level_for_pct(pct):
    if pct >= 70:
        return 'High'
    if pct >= 35:
        return 'Medium'
    return 'Low'


def _compute_predictions():
    now = datetime.utcnow()
    window_start = now - timedelta(hours=WINDOW_HOURS)

    recent = Incident.query.filter(
        Incident.reported_at >= window_start,
        Incident.status.in_(['pending', 'verified'])
    ).all()

    scores = {}
    for inc in recent:
        scores[inc.location_desc] = scores.get(inc.location_desc, 0) + _score_for(inc, now)

    if not scores:
        # No recent activity anywhere — clear any stale batch and report nothing.
        Prediction.query.delete()
        db.session.commit()
        return []

    # Normalize against the busiest location in *this* batch, so the
    # top spot reads as ~100% regardless of overall report volume,
    # rather than against an arbitrary fixed ceiling that would need
    # re-tuning as usage grows.
    top_score = max(scores.values())
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:MAX_ROADS]

    rows = []
    for location_desc, score in ranked:
        pct = max(round((score / top_score) * 100), 5)  # keep a sliver visible, never a 0% bar
        rows.append(Prediction(
            road_name=location_desc,
            predicted_level=_level_for_pct(pct),
            predicted_pct=pct,
            generated_at=now
        ))

    Prediction.query.delete()
    db.session.add_all(rows)
    db.session.commit()

    return rows


@predictions_bp.route('/api/predictions', methods=['GET'])
def get_predictions():
    predictions = _compute_predictions()
    return jsonify([p.to_dict() for p in predictions]), 200


# =====================================================================
# Docs
# =====================================================================
#
# Static, informational downloads linked from every page's footer. Both
# are served as text/plain attachments (not rendered pages), so the
# footer links do exactly what they say: download a text file.

docs_bp = Blueprint('docs', __name__)

API_DOCS = """RoadPulse -- API Reference
Generated from the live Flask routes in this project.

AUTH
----
POST   /api/auth/register        Create an account. Body: {name, email, password}
POST   /api/auth/login           Sign in. Body: {email, password, remember}
GET    /logout                   Sign out (requires login)

INCIDENTS
---------
POST   /api/incidents            Submit a new incident report (requires login, multipart/form-data:
                                  type, severity, description, location_desc, lat, lng, photo[optional])
GET    /api/incidents/recent     Most recent incidents, any status. Query: ?limit=20
GET    /api/incidents/mine       Incidents reported by the signed-in user (requires login)
GET    /api/incidents/active     All incidents currently pending or verified

ADMIN (requires an admin account)
----------------------------------
GET    /api/admin/incidents                  List incidents. Query: ?status=pending|verified|rejected|all
POST   /api/admin/incidents/<id>/approve     Mark an incident verified
POST   /api/admin/incidents/<id>/reject      Mark an incident rejected
DELETE /api/admin/incidents/<id>             Permanently delete an incident (any status) + its photo file

ANALYTICS
---------
GET    /api/analytics/summary    Incident counts by type and by hour of day
GET    /api/dashboard/stats      Dashboard stat-card numbers (active incidents, reports today + trend)

NOTIFICATIONS
-------------
GET    /api/notifications        Personal + community notifications (requires login)

WEATHER
-------
GET    /api/weather              Current conditions for Andheri, Mumbai Suburban (via Open-Meteo)

PREDICTIONS
-----------
GET    /api/predictions          Heuristic congestion forecast, derived from recent incident
                                  density per reported location (not a live traffic-speed feed)

Notes
-----
- All endpoints return JSON except the two under /docs, which return plain text.
- Endpoints marked "requires login" use session-based auth (Flask-Login), not tokens.
- This is an academic project -- treat this reference as a snapshot of the current
  implementation, not a versioned/stable public API.
"""

ABOUT = """RoadPulse -- About This Project

RoadPulse is a community-powered traffic analytics and incident reporting
platform, built as an academic project (Idea Lab, Shree L.R. Tiwari College
of Engineering, E&TC department).

What it does
------------
- Lets signed-in users report road incidents (accidents, potholes,
  waterlogging, signal faults, roadblocks) with a location pin and an
  optional photo.
- Shows those reports on a live map and table, with an admin moderation
  queue to verify or reject submissions.
- Surfaces real weather for Andheri, Mumbai Suburban (via Open-Meteo), and
  a heuristic congestion forecast based on recent incident density.
- Every stat, chart, and list in the app is backed by real data from the
  project's own database -- nothing is filled in with placeholder numbers.

Tech stack
----------
Backend:   Flask, Flask-SQLAlchemy, Flask-Login, SQLite (MySQL-ready via
           a DATABASE_URL environment variable)
Frontend:  Bootstrap 5, Leaflet.js (maps), Chart.js (analytics), vanilla
           JS -- no build step, server-rendered Jinja templates
Design:    A "night traffic-control room" theme -- dark asphalt tones with
           amber and teal accents, applied consistently across every page

Status
------
This is a working student project, not a production traffic authority
tool. Data shown reflects whatever has actually been reported and
recorded in this deployment.
"""


@docs_bp.route('/docs/api')
def download_api_docs():
    return Response(
        API_DOCS,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=roadpulse-api-docs.txt'}
    )


@docs_bp.route('/docs/about')
def download_about():
    return Response(
        ABOUT,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=roadpulse-about.txt'}
    )
