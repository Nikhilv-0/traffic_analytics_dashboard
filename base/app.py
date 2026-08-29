# RoadPulse — application entry point.
#
# Creates the Flask app, wires up config/extensions/blueprints, and
# defines the page routes (server-rendered templates). All JSON API
# routes live in routes.py (auth, incidents, admin) and services.py
# (analytics, notifications, weather, predictions, docs).

import os
import click
from flask import Flask, render_template, redirect
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from models import db, login_manager, User, Incident, Prediction, Log
from routes import auth_bp, incidents_bp, admin_bp, admin_required
from services import analytics_bp, notifications_bp, weather_bp, predictions_bp, docs_bp

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # TODO: before deploying anywhere real, set this via an environment
    # variable instead — never commit a real secret key to source control.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

    # Defaults to a local SQLite file. To switch to MySQL later, set the
    # DATABASE_URL environment variable, e.g.:
    #   mysql+pymysql://user:password@localhost/roadpulse
    # No other code changes needed — SQLAlchemy abstracts the difference.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'roadpulse.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Used by the Incident module for photo uploads (report.js posts a
    # `photo` field to /api/incidents).
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB, matches the report page's stated limit


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'  # where @login_required sends anonymous users

app.register_blueprint(auth_bp)
app.register_blueprint(incidents_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(predictions_bp)
app.register_blueprint(docs_bp)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def login():
    if current_user.is_authenticated:
        return redirect('/admin' if current_user.role == 'admin' else '/dashboard')
    return render_template('login.html')

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/report')
@login_required
def report():
    return render_template('report.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/incidents')
@login_required
def incidents():
    return render_template('incidents.html')


@app.cli.command('create-admin')
@click.argument('email')
@click.argument('password')
@click.option('--name', default='Admin', help='Display name for the account.')
def create_admin(email, password, name):
    """Create (or promote) an admin account, e.g.:
    flask create-admin admin@roadpulse.com secretpass123 --name "City Admin"
    """
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()
    if user:
        user.role = 'admin'
        click.echo(f'Existing user {email} promoted to admin.')
    else:
        user = User(
            name=name, email=email, role='admin',
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        click.echo(f'Admin account created for {email}.')
    db.session.commit()


@app.shell_context_processor
def make_shell_context():
    """Lets `flask shell` auto-import these — no manual imports needed.
    Try: User.query.all()  or  Incident.query.filter_by(status='pending').all()
    """
    return {
        'db': db,
        'User': User,
        'Incident': Incident,
        'Prediction': Prediction,
        'Log': Log,
    }


if __name__ == '__main__':
    with app.app_context():
        # Creates roadpulse.db and all tables on first run if they don't
        # exist yet. Safe to leave in for now — once the schema is settled,
        # swap this for Flask-Migrate so schema changes don't require
        # dropping the database.
        db.create_all()
    app.run(debug=True)
