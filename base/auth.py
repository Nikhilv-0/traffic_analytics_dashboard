# RoadPulse — Authentication module.
#
# Routes here match the payloads the frontend already sends:
#   login.js    POST /api/auth/register  { name, email, password }
#   login.js    POST /api/auth/login     { email, password, remember }
#   navbar link GET  /logout

from functools import wraps

from flask import Blueprint, jsonify, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import User, Log

auth_bp = Blueprint('auth', __name__)


def admin_required(view_func):
    """Like @login_required, but also requires role == 'admin'."""
    @wraps(view_func)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required.'}), 403
        return view_func(*args, **kwargs)
    return wrapped


def _log(action, user_id=None):
    db.session.add(Log(user_id=user_id, action=action))
    db.session.commit()


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or not password:
        return jsonify({'message': 'Name, email, and password are all required.'}), 400
    if len(password) < 8:
        return jsonify({'message': 'Password must be at least 8 characters.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'An account with that email already exists.'}), 409

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    _log('register', user_id=user.id)

    return jsonify({'message': 'Account created.'}), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
def login_api():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    remember = bool(data.get('remember'))

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid email or password.'}), 401

    login_user(user, remember=remember)
    _log('login', user_id=user.id)

    redirect_to = '/admin' if user.role == 'admin' else '/dashboard'
    return jsonify({'message': 'Signed in.', 'redirect': redirect_to}), 200


@auth_bp.route('/logout')
@login_required
def logout():
    _log('logout', user_id=current_user.id)
    logout_user()
    return redirect(url_for('login'))
