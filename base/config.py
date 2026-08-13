import os

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

    # Used later by the Incident Module for photo uploads (report.js already
    # posts a `photo` field to /api/incidents).
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB, matches the report page's stated limit
