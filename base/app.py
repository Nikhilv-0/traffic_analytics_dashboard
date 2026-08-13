import os
import click
from flask import Flask, render_template, request, redirect
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from config import Config
from extensions import db, login_manager

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'  # where @login_required sends anonymous users

# Import models AFTER db.init_app so they register against this app's db.
# (Also makes them available to `flask shell` for quick inspection.)
import models  # noqa: E402
from auth import auth_bp, admin_required  # noqa: E402
from incidents import incidents_bp  # noqa: E402
from admin_api import admin_bp  # noqa: E402
from analytics import analytics_bp  # noqa: E402
from notifications import notifications_bp  # noqa: E402
from weather import weather_bp  # noqa: E402
from predictions import predictions_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(incidents_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(predictions_bp)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return models.User.query.get(int(user_id))


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


@app.cli.command('create-admin')
@click.argument('email')
@click.argument('password')
@click.option('--name', default='Admin', help='Display name for the account.')
def create_admin(email, password, name):
    """Create (or promote) an admin account, e.g.:
    flask create-admin admin@roadpulse.com secretpass123 --name "City Admin"
    """
    email = email.strip().lower()
    user = models.User.query.filter_by(email=email).first()
    if user:
        user.role = 'admin'
        click.echo(f'Existing user {email} promoted to admin.')
    else:
        user = models.User(
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
        'User': models.User,
        'Incident': models.Incident,
        'Prediction': models.Prediction,
        'Log': models.Log,
    }


if __name__ == '__main__':
    with app.app_context():
        # Creates roadpulse.db and all tables on first run if they don't
        # exist yet. Safe to leave in for now — once the schema is settled,
        # swap this for Flask-Migrate so schema changes don't require
        # dropping the database.
        db.create_all()
    app.run(debug=True)
