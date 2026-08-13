# RoadPulse — Predictions module.
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

from datetime import datetime, timedelta

from flask import Blueprint, jsonify

from extensions import db
from models import Incident, Prediction

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
