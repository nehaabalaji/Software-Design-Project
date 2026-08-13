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

migrate = Migrate()
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(store=None):
    app = Flask(__name__)
    CORS(app)

    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    migrate.init_app(app, db)

    # store=... lets tests inject InMemoryStore (app/store.py); the real app
    # defaults to MySQL via SQLStore (app/sql_store.py).
    app.config["STORE"] = store or SQLStore()

    # Authentication Module (done)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # Service Management Module (done)
    app.register_blueprint(services_bp, url_prefix="/api/services")

    # Queue Management Module (done)
    app.register_blueprint(queues_bp, url_prefix="/api/queues")

    # History Module (done)
    app.register_blueprint(history_bp, url_prefix="/api/history")

    # Notification Module
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")

    # UserProfile Module (A4)
    app.register_blueprint(profile_bp, url_prefix="/api/profile")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "QueueSmart"}

    # Serve the website (HTML/CSS/JS) from the same server as the API
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
