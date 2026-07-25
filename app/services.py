# Service Management Module
#
# Admins create/update/delete services; anyone can list/view them.
# Each service has: name, description, expected duration (minutes),
# priority level (low / medium / high / urgent).
#
# Endpoints:
#   GET    /api/services/           list all services (anyone)
#   GET    /api/services/<id>       get a single service (anyone)
#   POST   /api/services/           create a service (admin)
#   PUT    /api/services/<id>       update a service (admin, partial)
#   DELETE /api/services/<id>       delete a service (admin)

from flask import Blueprint, current_app, jsonify, request

from app.utils import admin_required

services_bp = Blueprint("services", __name__)

PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}
NAME_MIN_LEN, NAME_MAX_LEN = 2, 100
DESC_MIN_LEN, DESC_MAX_LEN = 1, 500
DURATION_MIN, DURATION_MAX = 1, 480  # minutes, up to 8 hours


def _validate_service_payload(data, partial=False):
    """partial=True: only validate fields that are present (used for PUT)."""
    errors = {}

    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Name is required"
        elif not (NAME_MIN_LEN <= len(name.strip()) <= NAME_MAX_LEN):
            errors["name"] = f"Name must be {NAME_MIN_LEN}-{NAME_MAX_LEN} characters"

    if "description" in data or not partial:
        description = data.get("description")
        if not isinstance(description, str) or not description.strip():
            errors["description"] = "Description is required"
        elif not (DESC_MIN_LEN <= len(description.strip()) <= DESC_MAX_LEN):
            errors["description"] = f"Description must be {DESC_MIN_LEN}-{DESC_MAX_LEN} characters"

    if "duration" in data or not partial:
        duration = data.get("duration")
        if not isinstance(duration, int) or isinstance(duration, bool) or not (
            DURATION_MIN <= duration <= DURATION_MAX
        ):
            errors["duration"] = f"Duration must be an integer between {DURATION_MIN} and {DURATION_MAX}"

    if "priority" in data or not partial:
        priority = data.get("priority")
        if priority not in PRIORITY_LEVELS:
            errors["priority"] = f"Priority must be one of: {', '.join(sorted(PRIORITY_LEVELS))}"

    return errors


@services_bp.get("/")
def list_services():
    store = current_app.config["STORE"]
    services = store.list_services()
    for service in services:
        service["queue_length"] = store.get_queue_length(service["id"])
    services.sort(key=lambda s: s["created_at"])
    return jsonify({"services": services, "count": len(services)}), 200


@services_bp.get("/<service_id>")
def get_service(service_id):
    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404
    service["queue_length"] = store.get_queue_length(service_id)
    return jsonify({"service": service}), 200


@services_bp.post("/")
@admin_required
def create_service(admin_user):
    data = request.get_json(silent=True) or {}
    errors = _validate_service_payload(data, partial=False)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    store = current_app.config["STORE"]
    name = data["name"].strip()
    if store.service_name_exists(name):
        return jsonify({"message": "A service with this name already exists"}), 409

    service = store.create_service(
        name=name,
        description=data["description"].strip(),
        duration=data["duration"],
        priority=data["priority"],
    )
    service["queue_length"] = 0
    return jsonify({"service": service}), 201


@services_bp.put("/<service_id>")
@admin_required
def update_service(admin_user, service_id):
    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"message": "Request body must contain at least one field to update"}), 400

    errors = _validate_service_payload(data, partial=True)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    fields = {}
    if "name" in data:
        new_name = data["name"].strip()
        if store.service_name_exists(new_name, exclude_id=service_id):
            return jsonify({"message": "A service with this name already exists"}), 409
        fields["name"] = new_name
    if "description" in data:
        fields["description"] = data["description"].strip()
    if "duration" in data:
        fields["duration"] = data["duration"]
    if "priority" in data:
        fields["priority"] = data["priority"]

    updated = store.update_service(service_id, **fields)
    updated["queue_length"] = store.get_queue_length(service_id)
    return jsonify({"service": updated}), 200


@services_bp.delete("/<service_id>")
@admin_required
def delete_service(admin_user, service_id):
    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    if store.get_queue_length(service_id) > 0:
        return jsonify(
            {"message": "Cannot delete a service that has users currently in its queue"}
        ), 409

    store.delete_service(service_id)
    return jsonify({"message": "Service deleted", "id": service_id}), 200
