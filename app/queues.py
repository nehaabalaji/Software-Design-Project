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
from app.notifications import (
    ALMOST_READY_POSITION,
    is_almost_ready,
    notify_almost_ready,
    notify_delayed,
    notify_joined,
    notify_position_update,
    notify_served,
)
from app.utils import admin_required, login_required

queues_bp = Blueprint("queues", __name__)


def _estimate_wait(service, position):
    duration = service["duration"] if service else 0
    return position * duration


def _display_name(store, user_id):
    """Return the user's preferred display name (profile > first name > email)."""
    profile = store.get_profile_by_user_id(user_id)
    if profile and profile.get("full_name"):
        return profile["full_name"]
    user = store.get_user_by_id(user_id)
    if not user:
        return ""
    full = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    return full or user.get("email", "")


def _notify_admins(store, service_id, kind, message):
    """Create a notification for every admin user."""
    from app.models import User
    from app.utils import ADMINISTRATOR
    for admin in User.query.filter_by(role=ADMINISTRATOR).all():
        store.add_notification(
            user_id=admin.id, service_id=service_id, kind=kind, message=message,
        )


def _notify_now_almost_ready(store, service_id):
    """After a leave/serve shifts everyone up, alert anyone who's now close
    to the front. Called from leave_queue and serve_next."""
    for entry in store.list_queue(service_id):
        position = entry.get("position")
        if position and is_almost_ready(position):
            name = _display_name(store, entry["user_id"])
            notify_almost_ready(
                store, user_id=entry["user_id"], service_id=service_id,
                position=position, name=name,
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
    name = _display_name(store, user["id"])
    notify_joined(store, user_id=user["id"], service_id=service_id, position=position, name=name)
    if is_almost_ready(position):
        notify_almost_ready(store, user_id=user["id"], service_id=service_id, position=position, name=name)
    svc_name = service.get("name", "queue")
    _notify_admins(store, service_id, "joined",
                   f"{name} joined {svc_name} at position {position}.")

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
    name = _display_name(store, user["id"])
    svc = store.get_service(service_id)
    svc_name = svc.get("name", "queue") if svc else "queue"
    _notify_admins(store, service_id, "left", f"{name} left {svc_name}.")
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


@queues_bp.post("/entry/<entry_id>/move")
@admin_required
def move_queue_entry(admin_user, entry_id):
    """Admin moves a queue entry up or down one position."""
    from datetime import datetime, timedelta, timezone
    from app.models import QueueEntry
    from app.extensions import db

    data = request.get_json(silent=True) or {}
    direction = data.get("direction")
    if direction not in ("up", "down"):
        return jsonify({"message": "direction must be 'up' or 'down'"}), 400

    entry = db.session.get(QueueEntry, entry_id)
    if not entry or entry.status != "waiting":
        return jsonify({"message": "Queue entry not found"}), 404

    store = current_app.config["STORE"]
    service_id = entry.service_id
    sorted_entries = store._sorted_entries(service_id)

    idx = next((i for i, e in enumerate(sorted_entries) if e.id == entry_id), None)
    if idx is None:
        return jsonify({"message": "Entry not in active queue"}), 404

    if direction == "up" and idx == 0:
        return jsonify({"message": "Already at the front"}), 400
    if direction == "down" and idx == len(sorted_entries) - 1:
        return jsonify({"message": "Already at the back"}), 400

    neighbor_idx = idx - 1 if direction == "up" else idx + 1
    neighbor = sorted_entries[neighbor_idx]

    # Build the new order by moving the entry one slot
    new_order = list(sorted_entries)
    new_order.insert(neighbor_idx, new_order.pop(idx))

    # Assign each entry a unique timestamp (1 s apart) that enforces the new
    # order.  MySQL DATETIME has second precision, so we need at least 1 s gaps.
    base = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, e in enumerate(new_order):
        e.joined_at = base - timedelta(seconds=len(new_order) - i)

    db.session.commit()

    # 1-indexed positions before and after the move
    entry_old_pos = idx + 1
    neighbor_old_pos = neighbor_idx + 1
    entry_new_pos = neighbor_old_pos   # entry takes neighbour's old slot
    neighbor_new_pos = entry_old_pos   # neighbour takes entry's old slot

    entry_name = _display_name(store, entry.user_id)
    neighbor_name = _display_name(store, neighbor.user_id)

    def _send(user_id, old_pos, new_pos, name):
        if is_almost_ready(new_pos):
            notify_almost_ready(store, user_id=user_id, service_id=service_id,
                                position=new_pos, name=name)
        elif is_almost_ready(old_pos):
            notify_delayed(store, user_id=user_id, service_id=service_id,
                           position=new_pos, name=name)
        else:
            notify_position_update(store, user_id=user_id, service_id=service_id,
                                   position=new_pos, name=name)

    _send(entry.user_id,    entry_old_pos,    entry_new_pos,    entry_name)
    _send(neighbor.user_id, neighbor_old_pos, neighbor_new_pos, neighbor_name)

    svc = store.get_service(service_id)
    svc_name = svc.get("name", "queue") if svc else "queue"
    arrow = "up" if direction == "up" else "down"
    _notify_admins(store, service_id, "position_update",
                   f"{entry_name} moved {arrow} to position {entry_new_pos} in {svc_name}.")

    return jsonify({"message": "Queue order updated", "new_position": entry_new_pos}), 200


@queues_bp.delete("/entry/<entry_id>")
@admin_required
def remove_queue_entry(admin_user, entry_id):
    """Admin removes any user from a queue by queue entry ID."""
    from app.models import QueueEntry
    from app.extensions import db

    entry = db.session.get(QueueEntry, entry_id)
    if not entry or entry.status != "waiting":
        return jsonify({"message": "Queue entry not found"}), 404

    store = current_app.config["STORE"]
    service_id = entry.service_id
    entry.status = "canceled"
    entry.position = None
    db.session.commit()

    store.add_history_entry(user_id=entry.user_id, service_id=service_id, action="left")
    _notify_now_almost_ready(store, service_id)
    name = _display_name(store, entry.user_id)
    svc = store.get_service(service_id)
    svc_name = svc.get("name", "queue") if svc else "queue"
    _notify_admins(store, service_id, "left", f"{name} was removed from {svc_name}.")
    return jsonify({"message": "User removed from queue", "entry_id": entry_id}), 200


@queues_bp.post("/admin-add")
@admin_required
def admin_add_to_queue(admin_user):
    """Admin adds a specific user to a queue by their email address."""
    from app.models import User

    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id")
    user_email = (data.get("user_email") or "").strip().lower()

    if not service_id:
        return jsonify({"message": "service_id is required"}), 400
    if not user_email:
        return jsonify({"message": "user_email is required"}), 400

    store = current_app.config["STORE"]
    service = store.get_service(service_id)
    if not service:
        return jsonify({"message": "Service not found"}), 404

    managed = store.get_queue_for_service(service_id)
    if managed and managed["status"] == "closed":
        return jsonify({"message": "This queue is closed"}), 400

    target_user = User.query.filter_by(email=user_email).first()
    if not target_user:
        return jsonify({"message": f"No account found for: {user_email}"}), 404

    try:
        entry, position = store.join_queue(user_id=target_user.id, service_id=service_id)
    except ValueError as e:
        return jsonify({"message": str(e)}), 409

    wait_minutes = _estimate_wait(service, position)
    store.add_history_entry(
        user_id=target_user.id,
        service_id=service_id,
        action="joined",
        wait_time_minutes=wait_minutes,
        position_at_join=position,
    )
    name = _display_name(store, target_user.id)
    notify_joined(store, user_id=target_user.id, service_id=service_id, position=position, name=name)
    if is_almost_ready(position):
        notify_almost_ready(store, user_id=target_user.id, service_id=service_id, position=position, name=name)
    svc_name = service.get("name", "queue")
    _notify_admins(store, service_id, "joined",
                   f"{name} added to {svc_name} at position {position} by admin.")

    entry["position"] = position
    entry["estimated_wait_minutes"] = wait_minutes
    return jsonify({"entry": entry, "user_email": target_user.email}), 201


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
    name = _display_name(store, entry["user_id"])
    notify_served(store, user_id=entry["user_id"], service_id=service_id, name=name)
    _notify_now_almost_ready(store, service_id)
    svc_name = service.get("name", "queue")
    _notify_admins(store, service_id, "served", f"{name} was served from {svc_name}.")
    return jsonify({"served": entry}), 200
