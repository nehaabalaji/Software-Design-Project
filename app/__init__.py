from flask import Flask, abort, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
from pathlib import Path

from app import config
from app.auth import auth_bp
from app.extensions import db
from app.history import history_bp
from app.queues import queues_bp
from app.services import services_bp
from app.sql_store import SQLStore
from app.notifications import notifications_bp
from app import models  # noqa: F401 -- registers tables with SQLAlchemy for Flask-Migrate
from app.profile import profile_bp
from app.smart import smart_bp

migrate = Migrate()
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(store=None):
    app = Flask(__name__)
    CORS(app)

    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    migrate.init_app(app, db)

    # Local SQLite fallback: create tables automatically (no flask db upgrade needed)
    if config.USING_SQLITE:
        with app.app_context():
            db.create_all()

    # store=... lets tests inject InMemoryStore (app/store.py); the real app
    # defaults to SQLStore (MySQL when available, otherwise SQLite).
    app.config["STORE"] = store or SQLStore()

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(services_bp, url_prefix="/api/services")
    app.register_blueprint(queues_bp, url_prefix="/api/queues")
    app.register_blueprint(history_bp, url_prefix="/api/history")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(smart_bp, url_prefix="/api/smart")

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "app": "QueueSmart",
            "database": "sqlite" if config.USING_SQLITE else "mysql",
        }

    @app.get("/")
    def site_index():
        return send_from_directory(PROJECT_ROOT, "index.html")

    @app.get("/<path:filename>")
    def site_files(filename):
        if filename.startswith("api/"):
            abort(404)
        target = PROJECT_ROOT / filename
        if target.is_file():
            return send_from_directory(PROJECT_ROOT, filename)
        abort(404)

    return app
