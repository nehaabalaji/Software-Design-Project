# Shared extension instances. Kept in their own module so app/models.py and
# app/__init__.py can both import `db` without a circular import.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
