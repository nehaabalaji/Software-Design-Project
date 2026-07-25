# History Module
#
# Tracks queue participation history for users (in memory).
# `add_history_entry(...)` is the integration point other modules
# (e.g. the Queue module) call whenever something history-worthy
# happens: a user joins a queue, leaves a queue, gets served, or is
# marked a no-show.
#
# Endpoints:
#   GET /api/history/mine    current user's own history (login required)
#   GET /api/history/        all history, filterable (admin)
#   GET /api/history/stats   aggregate stats (admin)

from flask import Blueprint, request, jsonify, g

from app.store import store, _now
from app.utils import login_required, admin_required, error_response

history_bp = Blueprint("history", __name__)

VALID_ACTIONS = {"joined", "left", "served", "no_show"}


def add_history_entry(
    user_id,
    service_id,
    action,
    wait_time_minutes=None,
    position_at_join=None,
    notes=None,
):
    """
    Record a queue-participation event.

    Called by the Queue module (or anything else) whenever a
    history-worthy event occurs. Not exposed as a REST endpoint on
    its own -- it's a plain function other backend modules import.

    Raises ValueError if `action` isn't a recognised value, so
    integration bugs fail loudly instead of writing junk history.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Invalid history action '{action}'. Must be one of {sorted(VALID_ACTIONS)}"
        )

    user = store.users.get(user_id)
    service = store.services.get(service_id)

    entry = {
        "id": store.next_id("history"),
        "user_id": user_id,
        "username": user["username"] if user else None,
        "service_id": service_id,
        "service_name": service["name"] if service else None,
        "action": action,
        "wait_time_minutes": wait_time_minutes,
        "position_at_join": position_at_join,
        "notes": notes,
        "timestamp": _now(),
    }
    store.history.append(entry)
    return entry


def _filter_history(entries, user_id=None, service_id=None, action=None):
    result = entries
    if user_id is not None:
        result = [e for e in result if e["user_id"] == user_id]
    if service_id is not None:
        result = [e for e in result if e["service_id"] == service_id]
    if action is not None:
        result = [e for e in result if e["action"] == action]
    return result


def _parse_int_arg(name):
    """Read an optional int query param. Returns (value, error_message)."""
    raw = request.args.get(name)
    if raw is None:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, f"{name} must be an integer"


@history_bp.route("/mine", methods=["GET"])
@login_required
def my_history():
    service_id, err = _parse_int_arg("service_id")
    if err:
        return error_response(err, 400)

    action = request.args.get("action")
    if action and action not in VALID_ACTIONS:
        return error_response(f"action must be one of {sorted(VALID_ACTIONS)}", 400)

    entries = _filter_history(
        store.history, user_id=g.current_user["id"], service_id=service_id, action=action
    )
    entries = sorted(entries, key=lambda e: e["id"], reverse=True)

    limit, err = _parse_int_arg("limit")
    if err:
        return error_response(err, 400)
    if limit is not None:
        if limit < 1:
            return error_response("limit must be a positive integer", 400)
        entries = entries[:limit]

    return jsonify({"history": entries, "count": len(entries)}), 200


@history_bp.route("/", methods=["GET"])
@admin_required
def all_history():
    user_id, err = _parse_int_arg("user_id")
    if err:
        return error_response(err, 400)
    service_id, err = _parse_int_arg("service_id")
    if err:
        return error_response(err, 400)

    action = request.args.get("action")
    if action and action not in VALID_ACTIONS:
        return error_response(f"action must be one of {sorted(VALID_ACTIONS)}", 400)

    entries = _filter_history(store.history, user_id=user_id, service_id=service_id, action=action)
    entries = sorted(entries, key=lambda e: e["id"], reverse=True)
    return jsonify({"history": entries, "count": len(entries)}), 200


@history_bp.route("/stats", methods=["GET"])
@admin_required
def history_stats():
    entries = store.history
    total = len(entries)

    by_action = {}
    for e in entries:
        by_action[e["action"]] = by_action.get(e["action"], 0) + 1

    by_service = {}
    for e in entries:
        key = e["service_name"] or f"service:{e['service_id']}"
        by_service[key] = by_service.get(key, 0) + 1

    wait_times = [
        e["wait_time_minutes"] for e in entries
        if isinstance(e.get("wait_time_minutes"), (int, float))
    ]
    avg_wait = round(sum(wait_times) / len(wait_times), 2) if wait_times else None

    return jsonify({
        "total_entries": total,
        "by_action": by_action,
        "by_service": by_service,
        "average_wait_time_minutes": avg_wait,
    }), 200