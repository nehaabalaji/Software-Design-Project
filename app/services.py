# Service Management Module
#
# Supports create / update / list / delete of services.
# Each service has: name, description, expected duration (minutes),
# priority level (low / medium / high / urgent).
#
# Endpoints:
#   GET    /api/services/           list all services (anyone)
#   GET    /api/services/<id>       get a single service (anyone)
#   POST   /api/services/           create a service (admin)
#   PUT    /api/services/<id>       update a service (admin, partial update)
#   DELETE /api/services/<id>       delete a service (admin)

from flask import Blueprint, request, jsonify

from app.store import store, _now
from app.utils import (
    admin_required,
    error_response,
    require_fields,
    validate_string,
    validate_int,
    validate_choice,
)

services_bp = Blueprint("services", __name__)

# --- field constraints -------------------------------------------------
PRIORITY_LEVELS = ["low", "medium", "high", "urgent"]
PRIORITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "urgent": 4}

NAME_MIN_LEN, NAME_MAX_LEN = 2, 100
DESC_MIN_LEN, DESC_MAX_LEN = 1, 500
DURATION_MIN, DURATION_MAX = 1, 480  # minutes, up to 8 hours


def _validate_service_payload(data, partial=False):
    """
    Validate a service create/update payload.
    partial=True means "only validate fields that are present"
    (used for PUT, where the caller may send just one field).
    """
    errors = []

    if not partial:
        missing = require_fields(data, ["name", "description", "duration", "priority"])
        if missing:
            errors.append(f"Missing required field(s): {', '.join(missing)}")

    if not partial or "name" in data:
        errors += validate_string(
            data.get("name"), "name",
            min_length=NAME_MIN_LEN, max_length=NAME_MAX_LEN, required=not partial,
        )
    if not partial or "description" in data:
        errors += validate_string(
            data.get("description"), "description",
            min_length=DESC_MIN_LEN, max_length=DESC_MAX_LEN, required=not partial,
        )
    if not partial or "duration" in data:
        errors += validate_int(
            data.get("duration"), "duration",
            min_value=DURATION_MIN, max_value=DURATION_MAX, required=not partial,
        )
    if not partial or "priority" in data:
        errors += validate_choice(
            data.get("priority"), "priority", PRIORITY_LEVELS, required=not partial,
        )

    return errors


def _serialize(service):
    data = dict(service)
    data["priority_weight"] = PRIORITY_WEIGHT.get(service["priority"], 0)
    data["queue_length"] = len(store.queues.get(service["id"], []))
    return data


@services_bp.route("/", methods=["GET"])
def list_services():
    services = sorted(store.services.values(), key=lambda s: s["id"])
    return jsonify({
        "services": [_serialize(s) for s in services],
        "count": len(services),
    }), 200


@services_bp.route("/<int:service_id>", methods=["GET"])
def get_service(service_id):
    service = store.services.get(service_id)
    if not service:
        return error_response("Service not found", 404)
    return jsonify({"service": _serialize(service)}), 200


@services_bp.route("/", methods=["POST"])
@admin_required
def create_service():
    data = request.get_json(silent=True) or {}

    errors = _validate_service_payload(data, partial=False)
    if errors:
        return error_response("Validation failed", 400, details=errors)

    name = data["name"].strip()
    if any(s["name"].lower() == name.lower() for s in store.services.values()):
        return error_response("A service with this name already exists", 409)

    sid = store.next_id("service")
    service = {
        "id": sid,
        "name": name,
        "description": data["description"].strip(),
        "duration": data["duration"],
        "priority": data["priority"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    store.services[sid] = service
    store.queues[sid] = []

    return jsonify({"service": _serialize(service)}), 201


@services_bp.route("/<int:service_id>", methods=["PUT"])
@admin_required
def update_service(service_id):
    service = store.services.get(service_id)
    if not service:
        return error_response("Service not found", 404)

    data = request.get_json(silent=True) or {}
    if not data:
        return error_response("Request body must contain at least one field to update", 400)

    errors = _validate_service_payload(data, partial=True)
    if errors:
        return error_response("Validation failed", 400, details=errors)

    if "name" in data:
        new_name = data["name"].strip()
        clashes = any(
            s["id"] != service_id and s["name"].lower() == new_name.lower()
            for s in store.services.values()
        )
        if clashes:
            return error_response("A service with this name already exists", 409)
        service["name"] = new_name

    if "description" in data:
        service["description"] = data["description"].strip()
    if "duration" in data:
        service["duration"] = data["duration"]
    if "priority" in data:
        service["priority"] = data["priority"]

    service["updated_at"] = _now()
    return jsonify({"service": _serialize(service)}), 200


@services_bp.route("/<int:service_id>", methods=["DELETE"])
@admin_required
def delete_service(service_id):
    service = store.services.get(service_id)
    if not service:
        return error_response("Service not found", 404)

    if store.queues.get(service_id):
        return error_response(
            "Cannot delete a service that has users currently in its queue", 409
        )

    del store.services[service_id]
    store.queues.pop(service_id, None)
    return jsonify({"message": "Service deleted", "id": service_id}), 200