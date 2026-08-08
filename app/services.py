# Service Management Module
#
# REST APIs (under /api/services):
#   POST   /           create a service
#   GET    /           list all services
#   GET    /:id        get one service
#   PUT    /:id        UPDATE / EDIT a service  ← TA feedback fix
#   DELETE /:id        delete a service
#
# Persistence: MySQL via SQLStore (or InMemoryStore in tests).

from flask import Blueprint, request

from app.controllers import services_queues as ctrl
from app.utils import admin_required

services_bp = Blueprint("services", __name__)


@services_bp.get("/")
def list_services():
    return ctrl.list_services()


@services_bp.get("/<service_id>")
def get_service(service_id):
    return ctrl.get_service(service_id)


@services_bp.post("/")
@admin_required
def create_service(admin_user):
    return ctrl.create_service(request.get_json(silent=True) or {})


@services_bp.put("/<service_id>")
@admin_required
def update_service(admin_user, service_id):
    """Edit an existing service (name, description, duration, priority).

    This is the dedicated update endpoint used by the admin Edit UI.
    """
    return ctrl.update_service(service_id, request.get_json(silent=True) or {})


@services_bp.delete("/<service_id>")
@admin_required
def delete_service(admin_user, service_id):
    return ctrl.delete_service(service_id)
