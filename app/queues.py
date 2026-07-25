# Queue Management + Wait-Time Estimation Module
#
# Users can join/leave a queue and see their position and estimated wait.
# Administrators can view a service's full queue and serve the next person.
#
# Ordering: priority (urgent > high > medium > low), then arrival time.
# Estimated wait: position in queue * the service's expected duration.
#
# Endpoints:
#   POST /api/queues/join            login required   body: {service_id}
#   POST /api/queues/leave           login required   body: {service_id}
#   GET  /api/queues/mine            login required
#   GET  /api/queues/service/<id>    admin only
#   POST /api/queues/serve-next      admin only        body: {service_id}

from flask import Blueprint, current_app, jsonify, request

from app.utils import admin_required, login_required

queues_bp = Blueprint("queues", __name__)


def _estimate_wait(service, position):
    duration = service["duration"] if service else 0
    return position * duration


@queues_bp.post("/join")
@login_required
def join_queue(user):
    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    try:
        entry, position = store.join_queue(user_id=user["id"], service_id=service_id)
    except ValueError as e:
        return jsonify({"message": str(e)}), 409

    wait_minutes = _estimate_wait(service, position)
    store.add_history_entry(
        user_id=user["id"],
        service_id=service_id,
        action="joined",
        wait_time_minutes=wait_minutes,
        position_at_join=position,
    )

    entry["position"] = position
    entry["estimated_wait_minutes"] = wait_minutes
    return jsonify({"entry": entry}), 201


@queues_bp.post("/leave")
@login_required
def leave_queue(user):
    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    store = current_app.config["STORE"]
    entry = store.leave_queue(user_id=user["id"], service_id=service_id)
    if not entry:
        return jsonify({"message": "You are not in this queue"}), 404

    store.add_history_entry(user_id=user["id"], service_id=service_id, action="left")
    return jsonify({"message": "Left the queue"}), 200


@queues_bp.get("/mine")
@login_required
def my_queues(user):
    store = current_app.config["STORE"]
    entries = store.list_queue_entries_for_user(user["id"])
    return jsonify({"queue_entries": entries, "count": len(entries)}), 200


@queues_bp.get("/service/<service_id>")
@admin_required
def service_queue(admin_user, service_id):
    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    entries = store.list_queue(service_id)
    for i, entry in enumerate(entries):
        entry["position"] = i + 1
        entry["estimated_wait_minutes"] = _estimate_wait(service, i + 1)

    return jsonify({"service_id": service_id, "queue": entries, "count": len(entries)}), 200


@queues_bp.post("/serve-next")
@admin_required
def serve_next(admin_user):
    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    entry = store.serve_next(service_id)
    if not entry:
        return jsonify({"message": "Queue is empty"}), 404

    store.add_history_entry(user_id=entry["user_id"], service_id=service_id, action="served")
    return jsonify({"served": entry}), 200
