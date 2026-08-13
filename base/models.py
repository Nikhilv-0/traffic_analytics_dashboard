# RoadPulse — database models.
#
# Field choices below are driven directly by what the frontend already
# sends/expects:
#   - login.js / register form  -> User
#   - report.js POST /api/incidents -> Incident
#   - admin.js GET /api/incidents/pending, /approve, /reject -> Incident.status
#   - dashboard.js Congestion Forecast panel -> Prediction
#   - admin.js GET /api/admin/sessions + audit trail -> Log

from datetime import datetime
from flask_login import UserMixin
from extensions import db


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user' | 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Incidents this user has reported (Incident.user_id -> User.id)
    incidents = db.relationship(
        'Incident', back_populates='reporter',
        foreign_keys='Incident.user_id'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }

    def __repr__(self):
        return f'<User {self.email}>'


class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)

    # Nullable: report.js currently allows guest submissions (no auth wired yet)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reporter_name = db.Column(db.String(120), nullable=False, default='Guest')

    type = db.Column(db.String(50), nullable=False)          # Accident, Pothole, Waterlogging, ...
    severity = db.Column(db.String(10), nullable=False)      # low | medium | high
    description = db.Column(db.String(500), nullable=False)  # matches report.js's 500-char limit
    location_desc = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)

    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | verified | rejected | resolved

    reported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    reporter = db.relationship('User', back_populates='incidents', foreign_keys=[user_id])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'description': self.description,
            'location': self.location_desc,
            'lat': self.lat,
            'lng': self.lng,
            'status': self.status,
            'reported_by': self.reporter_name,
            'reported_at': self.reported_at.isoformat(),
            # photo_path is stored relative to /static (e.g. "uploads/xxx.jpg"),
            # see incidents.py's _save_photo(). None when no photo was attached.
            'photo_url': f'/static/{self.photo_path}' if self.photo_path else None
        }

    def __repr__(self):
        return f'<Incident {self.id} {self.type} ({self.status})>'


class Prediction(db.Model):
    __tablename__ = 'predictions'

    id = db.Column(db.Integer, primary_key=True)
    road_name = db.Column(db.String(255), nullable=False)
    predicted_level = db.Column(db.String(10), nullable=False)  # Low | Medium | High
    predicted_pct = db.Column(db.Integer, nullable=False)       # 0-100, drives the progress bar width
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'road': self.road_name,
            'level': self.predicted_level,
            'pct': self.predicted_pct,
            'generated_at': self.generated_at.isoformat()
        }

    def __repr__(self):
        return f'<Prediction {self.road_name}: {self.predicted_level}>'


class Log(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)       # e.g. 'login', 'incident_approved'
    target_type = db.Column(db.String(50), nullable=True)    # e.g. 'incident', 'user'
    target_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<Log {self.action} by user {self.user_id} at {self.timestamp}>'
