from flask import Flask
from flask_cors import CORS

from app.auth import auth_bp
from app.history import history_bp
from app.queues import queues_bp
from app.services import services_bp
from app.store import InMemoryStore
from app.notifications import notifications_bp


def create_app(store=None):
    app = Flask(__name__)
    CORS(app)

    app.config["STORE"] = store or InMemoryStore()

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

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "QueueSmart"}

    return app
