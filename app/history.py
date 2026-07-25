# History Module
#
# Tracks queue participation history (join/leave/served/no-show).
# `store.add_history_entry(...)` (in app/store.py) is the integration
# point other modules -- the Queue module -- call whenever something
# history-worthy happens.
#
# Endpoints:
#   GET /api/history/mine    current user's own history (login required)
#   GET /api/history/        all history, filterable (admin)
#   GET /api/history/stats   aggregate stats (admin)

from flask import Blueprint, current_app, jsonify, request

from app.utils import admin_required, login_required

history_bp = Blueprint("history", __name__)

VALID_ACTIONS = {"joined", "left", "served", "no_show"}


def _filter_history(entries, user_id=None, service_id=None, action=None):
    result = entries
    if user_id is not None:
        result = [e for e in result if e["user_id"] == user_id]
    if service_id is not None:
        result = [e for e in result if e["service_id"] == service_id]
    if action is not None:
        result = [e for e in result if e["action"] == action]
    return result


def _parse_limit_arg():
    raw = request.args.get("limit")
    if raw is None:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, "limit must be an integer"


@history_bp.get("/mine")
@login_required
def my_history(user):
    store = current_app.config["STORE"]

    action = request.args.get("action")
    if action and action not in VALID_ACTIONS:
        return jsonify({"message": f"action must be one of {sorted(VALID_ACTIONS)}"}), 400

    entries = _filter_history(
        store.list_history(),
        user_id=user["id"],
        service_id=request.args.get("service_id"),
        action=action,
    )
    entries.sort(key=lambda e: e["timestamp"], reverse=True)

    limit, err = _parse_limit_arg()
    if err:
        return jsonify({"message": err}), 400
    if limit is not None:
        if limit < 1:
            return jsonify({"message": "limit must be a positive integer"}), 400
        entries = entries[:limit]

    return jsonify({"history": entries, "count": len(entries)}), 200


@history_bp.get("/")
@admin_required
def all_history(admin_user):
    store = current_app.config["STORE"]

    action = request.args.get("action")
    if action and action not in VALID_ACTIONS:
        return jsonify({"message": f"action must be one of {sorted(VALID_ACTIONS)}"}), 400

    entries = _filter_history(
        store.list_history(),
        user_id=request.args.get("user_id"),
        service_id=request.args.get("service_id"),
        action=action,
    )
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return jsonify({"history": entries, "count": len(entries)}), 200


@history_bp.get("/stats")
@admin_required
def history_stats(admin_user):
    store = current_app.config["STORE"]
    entries = store.list_history()
    total = len(entries)

    by_action = {}
    for entry in entries:
        by_action[entry["action"]] = by_action.get(entry["action"], 0) + 1

    by_service = {}
    for entry in entries:
        key = entry["service_name"] or f"service:{entry['service_id']}"
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
