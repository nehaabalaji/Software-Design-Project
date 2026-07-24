from flask import Flask
from flask_cors import CORS

from app.auth import auth_bp
from app.store import InMemoryStore

# Other modules (services, queues, notifications, history) are for the rest
# of the team. When ready, import their blueprints and register them below.
# Example:
#   from app.services import services_bp
#   app.register_blueprint(services_bp, url_prefix="/api/services")


def create_app(store=None):
    app = Flask(__name__)
    CORS(app)

    app.config["STORE"] = store or InMemoryStore()

    # Authentication Module (done)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "QueueSmart"}

    return app
