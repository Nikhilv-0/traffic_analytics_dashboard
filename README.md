# RoadPulse

Community-powered traffic analytics and incident reporting web app.

Built as an academic smart-city project

Users report road incidents (accidents, potholes, waterlogging, signal faults, roadblocks) with a location pin and an optional photo. Reports show up on a live map and table for everyone to see. Admins review each report and can verify, reject, or permanently delete it. The dashboard also shows live weather and a heuristic congestion forecast — both computed from real data, not placeholders.

## Features

- Email/password authentication with role-based access (`user` / `admin`)
- Incident reporting with map pin selection and optional photo upload
- Live dashboard: interactive map (marker/heatmap toggle), recent incidents table, real stat cards, weather widget, congestion forecast, analytics charts, CSV export
- Admin panel: status-filterable incident queue (Pending / Verified / All), approve/reject/delete actions, active-sessions view
- Profile page with account details and a "My Reports" table
- Full active-incidents list page
- Downloadable API reference and "About this project" text files, linked from the footer

## Tech Stack

**Backend:** Flask, Flask-SQLAlchemy, Flask-Login, SQLite (MySQL-ready via `DATABASE_URL`)
**Frontend:** Bootstrap 5, Leaflet.js (maps), Chart.js (analytics), vanilla JS — no build step, server-rendered Jinja2 templates

## Project Structure

```
app.py              # Flask app, config, extension init, blueprint registration, page routes, CLI
models.py            # Database models: User, Incident, Prediction, Log
routes.py             # Auth, incident reporting, and admin moderation routes
services.py           # Analytics, notifications, weather, predictions, and doc-download routes
requirements.txt      # Python dependencies
templates/            # HTML pages (login, dashboard, report, profile, incidents, admin)
static/                # Per-page CSS/JS, plus static/uploads/ for incident photos
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create the database and an admin account
python app.py                 # creates roadpulse.db on first run, then Ctrl+C
flask create-admin admin@roadpulse.com yourpassword --name "Your Name"

# 3. Run the dev server
python app.py
# Visit http://127.0.0.1:5000
```

By default the app uses a local SQLite file (`roadpulse.db`). To use MySQL instead, set a `DATABASE_URL` environment variable — no code changes needed:

```bash
export DATABASE_URL="mysql+pymysql://user:password@localhost/roadpulse"
```

## API Overview

| Method | Route | Auth | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | none | `{name, email, password}` |
| POST | `/api/auth/login` | none | `{email, password, remember}` |
| GET | `/logout` | login | |
| POST | `/api/incidents` | login | multipart/form-data incl. optional photo |
| GET | `/api/incidents/recent` | none | `?limit=20` |
| GET | `/api/incidents/mine` | login | current user's own reports |
| GET | `/api/incidents/active` | none | pending + verified only |
| GET | `/api/admin/incidents` | admin | `?status=pending\|verified\|rejected\|all` |
| POST | `/api/admin/incidents/<id>/approve` | admin | |
| POST | `/api/admin/incidents/<id>/reject` | admin | |
| DELETE | `/api/admin/incidents/<id>` | admin | permanently deletes report + photo |
| GET | `/api/admin/sessions` | admin | |
| GET | `/api/analytics/summary` | none | incidents by type / by hour |
| GET | `/api/dashboard/stats` | none | stat card numbers |
| GET | `/api/notifications` | login | |
| GET | `/api/weather` | none | Open-Meteo passthrough, 10-min cache |
| GET | `/api/predictions` | none | heuristic congestion forecast |
| GET | `/docs/api` | none | downloadable API reference (.txt) |
| GET | `/docs/about` | none | downloadable project summary (.txt) |

## Known Limitations

- No Flask-Migrate — schema changes currently require deleting `roadpulse.db` and letting `db.create_all()` rebuild it.
- The congestion forecast is a documented heuristic based on recent incident density, not a live traffic-speed feed.