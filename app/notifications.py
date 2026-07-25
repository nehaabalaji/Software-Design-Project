# Notification Module
#
# Records in-app notifications for users and lets them read/mark them.
# No real email/SMS -- notifications are stored in memory and returned as JSON,
# which the assignment allows.
#
# The Queue module is the trigger: it calls notify_joined(...) when a user
# joins a queue and notify_almost_ready(...) when a user is close to the front.
# Those helpers write through store.add_notification(...) -- the same pattern
# history.py uses with store.add_history_entry(...).
#
# Endpoints:
#   GET  /api/notifications/            current user's notifications (login required)
#   POST /api/notifications/<id>/read   mark one as read (login required, own only)
#   POST /api/notifications/read-all    mark all of the caller's as read (login required)

from flask import Blueprint, current_app, jsonify, request

from app.utils import login_required

notifications_bp = Blueprint("notifications", __name__)

# How close to the front a user must be before an "almost ready" alert fires.
ALMOST_READY_POSITION = 3

JOINED = "joined"
ALMOST_READY = "almost_ready"
SERVED = "served"
VALID_KINDS = {JOINED, ALMOST_READY, SERVED}


# ----------------------------------------------------------------------
# Integration point for the Queue module (call these, don't POST to them).
# They mirror how queues.py already calls store.add_history_entry(...).
# ----------------------------------------------------------------------

def notify_joined(store, *, user_id, service_id, position):
    """Call when a user joins a queue."""
    message = f"You joined the queue at position {position}."
    return store.add_notification(
        user_id=user_id,
        service_id=service_id,
        kind=JOINED,
        message=message,
    )


def notify_almost_ready(store, *, user_id, service_id, position):
    """Call when a user moves close to the front of the queue."""
    ahead = position - 1
    if ahead <= 0:
        message = "You're next -- please be ready."
    elif ahead == 1:
        message = "Almost your turn -- 1 person ahead of you."
    else:
        message = f"Almost your turn -- {ahead} people ahead of you."
    return store.add_notification(
        user_id=user_id,
        service_id=service_id,
        kind=ALMOST_READY,
        message=message,
    )


def is_almost_ready(position):
    """True when a user is close enough to the front to warrant an alert.

    The Queue module can use this to decide whether to call
    notify_almost_ready after a serve-next shifts everyone forward.
    """
    if isinstance(position, bool) or not isinstance(position, int):
        raise ValueError("Position must be a whole number")
    if position < 1:
        raise ValueError("Position must be 1 or greater")
    return position <= ALMOST_READY_POSITION


# ----------------------------------------------------------------------
# HTTP endpoints (what the front end calls)
# ----------------------------------------------------------------------

@notifications_bp.get("/")
@login_required
def list_my_notifications(user):
    store = current_app.config["STORE"]

    notifications = store.list_notifications(user["id"])

    unread_only = request.args.get("unread")
    if unread_only is not None and unread_only.lower() in ("1", "true", "yes"):
        notifications = [n for n in notifications if not n["read"]]

    notifications.sort(key=lambda n: n["timestamp"], reverse=True)
    unread_count = sum(1 for n in store.list_notifications(user["id"]) if not n["read"])

    return jsonify({
        "notifications": notifications,
        "count": len(notifications),
        "unread_count": unread_count,
    }), 200


@notifications_bp.post("/<notification_id>/read")
@login_required
def mark_read(user, notification_id):
    store = current_app.config["STORE"]

    notification = store.mark_notification_read(notification_id, user["id"])
    if notification is None:
        return jsonify({"message": "Notification not found"}), 404

    return jsonify({"message": "Notification marked as read", "notification": notification}), 200


@notifications_bp.post("/read-all")
@login_required
def mark_all_read(user):
    store = current_app.config["STORE"]
    updated = store.mark_all_notifications_read(user["id"])
    return jsonify({"message": "Notifications marked as read", "updated": updated}), 200
