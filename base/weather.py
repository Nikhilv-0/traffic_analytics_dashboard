# RoadPulse — Weather module.
#
#   GET /api/weather -> { tempC, condition, icon, humidity, windKmh }
#
# Uses Open-Meteo (https://open-meteo.com) — free, no API key or signup
# required for non-commercial use. Called server-side (not from the
# browser) so we can cache it and keep the frontend simple.
#
# NOTE: this couldn't be live-tested in the sandbox this was built in
# (outbound network here is restricted to package registries, not
# api.open-meteo.com). Test it locally once the server's running — if
# the weather widget shows "Weather unavailable", the most likely cause
# is the `weather_code` response key (see WEATHER_CODES lookup below);
# print `payload` in the except/response to check the actual key name
# Open-Meteo returns if that happens.

import time

import requests
from flask import Blueprint, jsonify

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
