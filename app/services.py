# Service Management Module
# create / update / list / delete services
#
# Each service has: name, description, expected_duration (minutes), priority.
# Field names match the A2 Service Management screen.

from flask import Blueprint, current_app, jsonify, request

from app.utils import admin_required, login_required

services_bp = Blueprint("services", __name__)

NAME_MAX = 100
DESCRIPTION_MAX = 500
DURATION_MIN = 1
DURATION_MAX = 480

LOW = "Low"
NORMAL = "Normal"
HIGH = "High"
VALID_PRIORITIES = {LOW, NORMAL, HIGH}


def _validate_service(data, *, partial=False):
    """Validate a service payload.

    partial=True is used for updates, where only the supplied fields
    are checked (so a PUT can change just the name, for example).
    """
    if not isinstance(data, dict):
        return {"body": "Request body must be a JSON object"}

    errors = {}

    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Service name is required"
        elif len(name.strip()) > NAME_MAX:
            errors["name"] = f"Service name must be {NAME_MAX} characters or fewer"

    if not partial or "description" in data:
        description = data.get("description")
        if not isinstance(description, str) or not description.strip():
            errors["description"] = "Description is required"
        elif len(description.strip()) > DESCRIPTION_MAX:
            errors["description"] = (
                f"Description must be {DESCRIPTION_MAX} characters or fewer"
            )

    if not partial or "expected_duration" in data:
        duration = data.get("expected_duration")
        if isinstance(duration, bool) or not isinstance(duration, int):
            errors["expected_duration"] = "Expected duration must be a whole number of minutes"
        elif duration < DURATION_MIN or duration > DURATION_MAX:
            errors["expected_duration"] = (
                f"Expected duration must be between {DURATION_MIN} and {DURATION_MAX} minutes"
            )

    if not partial or "priority" in data:
        priority = data.get("priority")
        if priority not in VALID_PRIORITIES:
            errors["priority"] = f"Priority must be one of: {LOW}, {NORMAL}, {HIGH}"

    return errors


@services_bp.get("/")
@login_required
def list_services(current_user):
    """Any logged-in user can browse services (the A2 Join Queue screen)."""
    store = current_app.config["STORE"]
    return jsonify({"services": store.list_services()}), 200


@services_bp.get("/<service_id>")
@login_required
def get_service(current_user, service_id):
    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if service is None:
        return jsonify({"message": "Service not found"}), 404
    return jsonify({"service": service}), 200


@services_bp.post("/")
@admin_required
def create_service(current_user):
    data = request.get_json(silent=True)
    errors = _validate_service(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    store = current_app.config["STORE"]
    try:
        service = store.create_service(
            name=data["name"].strip(),
            description=data["description"].strip(),
            expected_duration=data["expected_duration"],
            priority=data["priority"],
        )
    except ValueError as e:
        return jsonify({"message": str(e), "errors": {"name": str(e)}}), 409

    return jsonify({"message": "Service created", "service": service}), 201


@services_bp.put("/<service_id>")
@admin_required
def update_service(current_user, service_id):
    data = request.get_json(silent=True)
    errors = _validate_service(data, partial=True)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    fields = {}
    if "name" in data:
        fields["name"] = data["name"].strip()
    if "description" in data:
        fields["description"] = data["description"].strip()
    if "expected_duration" in data:
        fields["expected_duration"] = data["expected_duration"]
    if "priority" in data:
        fields["priority"] = data["priority"]
    if "is_open" in data:
        if not isinstance(data["is_open"], bool):
            return jsonify({
                "message": "Validation failed",
                "errors": {"is_open": "is_open must be true or false"},
            }), 400
        fields["is_open"] = data["is_open"]

    if not fields:
        return jsonify({
            "message": "Validation failed",
            "errors": {"body": "No fields to update"},
        }), 400

    store = current_app.config["STORE"]
    try:
        service = store.update_service(service_id, **fields)
    except ValueError as e:
        return jsonify({"message": str(e), "errors": {"name": str(e)}}), 409

    if service is None:
        return jsonify({"message": "Service not found"}), 404

    return jsonify({"message": "Service updated", "service": service}), 200


@services_bp.delete("/<service_id>")
@admin_required
def delete_service(current_user, service_id):
    store = current_app.config["STORE"]
    if not store.delete_service(service_id):
        return jsonify({"message": "Service not found"}), 404
    return jsonify({"message": "Service deleted"}), 200
