# Queue Management Module
#
# Managed queues (open/closed) — assignment data-layer APIs:
#   POST /api/queues/                   create a queue for a service
#   GET  /api/queues/                   list all queues
#   GET  /api/queues/<queue_id>         get queue details
#   PUT  /api/queues/<queue_id>/status  update status (open/closed)
#
# User join / leave / serve-next (existing behavior):
#   POST /api/queues/join            login required   body: {service_id}
#   POST /api/queues/leave           login required   body: {service_id}
#   GET  /api/queues/mine            login required
#   GET  /api/queues/service/<id>    admin only
#   POST /api/queues/serve-next      admin only        body: {service_id}
#
# Ordering: priority (urgent > high > medium > low), then arrival time.
# Estimated wait: position in queue * the service's expected duration.
# Join/leave/serve-next also trigger notifications via app.notifications.

from flask import Blueprint, current_app, jsonify, request

from app.controllers import services_queues as ctrl
from app.notifications import is_almost_ready, notify_almost_ready, notify_joined
from app.utils import admin_required, login_required

queues_bp = Blueprint("queues", __name__)


def _estimate_wait(service, position):
    duration = service["duration"] if service else 0
    return position * duration


def _notify_now_almost_ready(store, service_id):
    """After a leave/serve shifts everyone up, alert anyone who's now close
    to the front. Called from leave_queue and serve_next."""
    for entry in store.list_queue(service_id):
        position = entry.get("position")
        if position and is_almost_ready(position):
            notify_almost_ready(
                store, user_id=entry["user_id"], service_id=service_id, position=position,
            )


# ---- Managed queue CRUD (assignment) -----------------------------------------

@queues_bp.post("/")
@admin_required
def create_queue(admin_user):
    return ctrl.create_queue(request.get_json(silent=True) or {})


@queues_bp.get("/")
def list_queues():
    return ctrl.list_queues()


@queues_bp.get("/<int:queue_id>")
def get_queue(queue_id):
    return ctrl.get_queue(queue_id)


@queues_bp.put("/<int:queue_id>/status")
@admin_required
def update_queue_status(admin_user, queue_id):
    return ctrl.update_queue_status(queue_id, request.get_json(silent=True) or {})


# ---- Join / leave / serve (people in line) -----------------------------------

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

    managed = store.get_queue_for_service(service_id)
    if managed and managed["status"] == "closed":
        return jsonify({"message": "This queue is closed"}), 400

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
    notify_joined(store, user_id=user["id"], service_id=service_id, position=position)
    if is_almost_ready(position):
        notify_almost_ready(store, user_id=user["id"], service_id=service_id, position=position)

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
    _notify_now_almost_ready(store, service_id)
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

    managed = store.get_queue_for_service(service_id)
    return jsonify({
        "service_id": service_id,
        "queue_status": managed["status"] if managed else None,
        "queue": entries,
        "count": len(entries),
    }), 200


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
    _notify_now_almost_ready(store, service_id)
    return jsonify({"served": entry}), 200
