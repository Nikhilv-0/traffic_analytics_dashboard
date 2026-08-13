# RoadPulse — shared extension instances.
#
# Kept in their own module so both app.py and models.py can import `db`
# without importing each other (avoids circular imports).

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
