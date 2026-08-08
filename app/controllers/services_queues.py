# Controllers: business logic for Service and Queue APIs.
# Routes stay thin; persistence goes through the app STORE (SQLStore / InMemoryStore).

from flask import current_app, jsonify

PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}
PRIORITY_TO_LEVEL = {"low": 0, "medium": 1, "high": 2, "urgent": 3}
LEVEL_TO_PRIORITY = {0: "low", 1: "medium", 2: "high", 3: "urgent"}
QUEUE_STATUSES = {"open", "closed"}

NAME_MIN_LEN, NAME_MAX_LEN = 2, 100
DESC_MAX_LEN = 500
DURATION_MIN, DURATION_MAX = 1, 480


def _store():
    return current_app.config["STORE"]


def normalize_service_payload(data):
    """Accept assignment aliases: expected_duration, priority_level."""
    out = dict(data or {})
    if "expected_duration" in out and "duration" not in out:
        out["duration"] = out["expected_duration"]
    if "priority_level" in out and "priority" not in out:
        level = out["priority_level"]
        if isinstance(level, int) and level in LEVEL_TO_PRIORITY:
            out["priority"] = LEVEL_TO_PRIORITY[level]
    return out


def enrich_service(service):
    """Expose assignment field names alongside existing ones."""
    if not service:
        return None
    enriched = dict(service)
    enriched["service_id"] = service["id"]
    enriched["expected_duration"] = service["duration"]
    enriched["priority_level"] = service.get(
        "priority_level", PRIORITY_TO_LEVEL.get(service.get("priority"), 0)
    )
    return enriched


def validate_service_payload(data, partial=False):
    """Reject empty names and non-positive durations. partial=True for PUT edits."""
    errors = {}

    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Name is required and must not be empty"
        elif not (NAME_MIN_LEN <= len(name.strip()) <= NAME_MAX_LEN):
            errors["name"] = f"Name must be {NAME_MIN_LEN}-{NAME_MAX_LEN} characters"

    if "description" in data or not partial:
        description = data.get("description")
        if not isinstance(description, str) or not description.strip():
            errors["description"] = "Description is required"
        elif len(description.strip()) > DESC_MAX_LEN:
            errors["description"] = f"Description must be at most {DESC_MAX_LEN} characters"

    if "duration" in data or not partial:
        duration = data.get("duration")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            errors["duration"] = "expected_duration / duration must be an integer greater than 0"
        elif duration > DURATION_MAX:
            errors["duration"] = f"Duration must be at most {DURATION_MAX} minutes"

    if "priority" in data or not partial:
        priority = data.get("priority")
        if priority not in PRIORITY_LEVELS:
            errors["priority"] = f"Priority must be one of: {', '.join(sorted(PRIORITY_LEVELS))}"

    return errors


# ---- Service controller actions ------------------------------------------------

def list_services():
    store = _store()
    services = [enrich_service(s) for s in store.list_services()]
    for service in services:
        service["queue_length"] = store.get_queue_length(service["id"])
        managed = store.get_queue_for_service(service["id"])
        service["queue_status"] = managed["status"] if managed else None
    services.sort(key=lambda s: s["created_at"])
    return jsonify({"services": services, "count": len(services)}), 200


def get_service(service_id):
    store = _store()
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404
    service = enrich_service(service)
    service["queue_length"] = store.get_queue_length(service_id)
    managed = store.get_queue_for_service(service_id)
    service["queue_status"] = managed["status"] if managed else None
    return jsonify({"service": service}), 200


def create_service(data):
    data = normalize_service_payload(data)
    errors = validate_service_payload(data, partial=False)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    store = _store()
    name = data["name"].strip()
    if store.service_name_exists(name):
        return jsonify({"message": "A service with this name already exists"}), 409

    priority = data["priority"]
    try:
        service = store.create_service(
            name=name,
            description=(data.get("description") or "").strip(),
            duration=data["duration"],
            priority=priority,
            priority_level=PRIORITY_TO_LEVEL[priority],
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 409
    except Exception:
        return jsonify({"message": "Server error while creating service"}), 500

    # Auto-create an open managed queue for this service
    try:
        store.create_managed_queue(service_id=service["id"], status="open")
    except ValueError:
        pass

    service = enrich_service(service)
    service["queue_length"] = 0
    service["queue_status"] = "open"
    return jsonify({"service": service, "message": "Service created"}), 201


def update_service(service_id, data):
    """PUT /services/:id — full edit support (TA feedback fix).

    Accepts any subset of: name, description, duration/expected_duration,
    priority / priority_level. Returns the updated service object.
    """
    store = _store()
    existing = store.get_service(service_id)
    if not existing:
        return jsonify({"message": "Service not found"}), 404

    data = normalize_service_payload(data)
    if not data:
        return jsonify({"message": "Request body must contain at least one field to update"}), 400

    errors = validate_service_payload(data, partial=True)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    fields = {}
    if "name" in data:
        new_name = data["name"].strip()
        if store.service_name_exists(new_name, exclude_id=service_id):
            return jsonify({"message": "A service with this name already exists"}), 409
        fields["name"] = new_name
    if "description" in data:
        fields["description"] = (data.get("description") or "").strip()
    if "duration" in data:
        fields["duration"] = data["duration"]
    if "priority" in data:
        fields["priority"] = data["priority"]
        fields["priority_level"] = PRIORITY_TO_LEVEL[data["priority"]]

    try:
        updated = store.update_service(service_id, **fields)
    except Exception:
        return jsonify({"message": "Server error while updating service"}), 500

    updated = enrich_service(updated)
    updated["queue_length"] = store.get_queue_length(service_id)
    managed = store.get_queue_for_service(service_id)
    updated["queue_status"] = managed["status"] if managed else None
    return jsonify({
        "message": "Service updated successfully",
        "service": updated,
    }), 200


def delete_service(service_id):
    store = _store()
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    if store.get_queue_length(service_id) > 0:
        return jsonify(
            {"message": "Cannot delete a service that has users currently in its queue"}
        ), 409

    try:
        store.delete_service(service_id)
    except Exception:
        return jsonify({"message": "Server error while deleting service"}), 500
    return jsonify({"message": "Service deleted", "id": service_id}), 200


# ---- Queue (managed open/closed) controller actions ---------------------------

def enrich_queue(queue):
    if not queue:
        return None
    out = dict(queue)
    out["id"] = queue["queue_id"]
    return out


def create_queue(data):
    store = _store()
    service_id = (data or {}).get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    if not store.get_service(service_id):
        return jsonify({"message": "Service not found"}), 404

    status = (data or {}).get("status", "open")
    if status not in QUEUE_STATUSES:
        return jsonify({"message": "status must be 'open' or 'closed'"}), 400

    if store.get_queue_for_service(service_id):
        return jsonify({"message": "A queue already exists for this service"}), 409

    try:
        queue = store.create_managed_queue(service_id=service_id, status=status)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception:
        return jsonify({"message": "Server error while creating queue"}), 500

    return jsonify({"queue": enrich_queue(queue), "message": "Queue created"}), 201


def list_queues():
    store = _store()
    queues = [enrich_queue(q) for q in store.list_managed_queues()]
    return jsonify({"queues": queues, "count": len(queues)}), 200


def get_queue(queue_id):
    store = _store()
    try:
        queue_id_int = int(queue_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Queue not found"}), 404

    queue = store.get_managed_queue(queue_id_int)
    if not queue:
        return jsonify({"message": "Queue not found"}), 404

    service = store.get_service(queue["service_id"])
    payload = enrich_queue(queue)
    payload["service"] = enrich_service(service) if service else None
    payload["queue_length"] = store.get_queue_length(queue["service_id"])
    return jsonify({"queue": payload}), 200


def update_queue_status(queue_id, data):
    store = _store()
    try:
        queue_id_int = int(queue_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Queue not found"}), 404

    queue = store.get_managed_queue(queue_id_int)
    if not queue:
        return jsonify({"message": "Queue not found"}), 404

    status = (data or {}).get("status")
    if status not in QUEUE_STATUSES:
        return jsonify({"message": "Invalid status. Allowed values: open, closed"}), 400

    try:
        updated = store.update_managed_queue_status(queue_id_int, status)
    except Exception:
        return jsonify({"message": "Server error while updating queue status"}), 500

    return jsonify({
        "message": f"Queue status updated to '{status}'",
        "queue": enrich_queue(updated),
    }), 200
