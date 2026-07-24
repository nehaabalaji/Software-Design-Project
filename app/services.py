# Service Management Module - TODO (team)
#
# Should support create / update / list services.
# Each service needs: name, description, expected duration, priority.
#
# Suggested endpoints:
#   GET    /api/services/
#   POST   /api/services/          (admin)
#   PUT    /api/services/<id>      (admin)
#   DELETE /api/services/<id>      (admin)
#
# Use login_required / admin_required from app.utils
# and store service data on InMemoryStore in app.store

from flask import Blueprint

services_bp = Blueprint("services", __name__)
