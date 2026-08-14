# Smart Features Module
#
# Feature 1 (Mahmoud): recommend an alternative open service with a shorter
# estimated wait (live queue length × expected duration).
#
# Feature 2 (Samuel): history-aware estimates + best time to join.
# What makes it "smart": instead of trusting each service's advertised
# duration, we learn the *actual* per-person pace from completed visits in
# History (wait_time_minutes ÷ position_at_join for "served" entries) and use
# that for wait estimates, falling back to live math when a service has no
# track record yet. GET /api/smart/best-time ranks the hours of the day by
# how busy a service historically is, so users know *when* to come, not just
# where.
#
# Endpoints:
#   GET /api/smart/recommend?service_id=<id>   (login required)
#   GET /api/smart/best-time?service_id=<id>   (login required)

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.utils import login_required

smart_bp = Blueprint("smart", __name__)

MIN_SERVED_SAMPLES = 3


def _served_pace_minutes(entries, service_id):
    """Average actual minutes-per-person for a service, learned from history.

    Uses "served" entries where we know both the real wait and the position
    the user joined at. Returns None until there are MIN_SERVED_SAMPLES
    usable entries, so one weird visit can't skew estimates."""
    paces = [
        e["wait_time_minutes"] / e["position_at_join"]
        for e in entries
        if e["service_id"] == service_id
        and e["action"] == "served"
        and isinstance(e.get("wait_time_minutes"), (int, float))
        and isinstance(e.get("position_at_join"), int)
        and e["position_at_join"] >= 1
    ]
    if len(paces) < MIN_SERVED_SAMPLES:
        return None
    return sum(paces) / len(paces)


def _estimate_wait_minutes(store, service, history_entries):
    """Estimated wait for joining a service now.

    Historical basis when the service has a track record, live basis
    (queue length × advertised duration) when it doesn't."""
    length = store.get_queue_length(service["id"])
    pace = _served_pace_minutes(history_entries, service["id"])
    if pace is not None:
        return round(length * pace, 1), length, "historical"
    duration = service.get("duration") or 0
    return length * duration, length, "live"


def _open_services(store):
    services = store.list_services()
    open_ones = []
    for service in services:
        managed = store.get_queue_for_service(service["id"])
        if managed is None or managed.get("status") == "open":
            open_ones.append(service)
    return open_ones


@smart_bp.get("/recommend")
@login_required
def recommend_alternative(user):
    """Suggest an alternative service with a shorter estimated wait.

    Query params:
      service_id  — the service the user is considering (required)
    """
    service_id = request.args.get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    store = current_app.config["STORE"]
    target = store.get_service(service_id)
    if not target:
        return jsonify({"message": "Service not found"}), 404

    history_entries = store.list_history()
    target_wait, target_length, target_basis = _estimate_wait_minutes(
        store, target, history_entries
    )
    alternatives = []
    for service in _open_services(store):
        if service["id"] == service_id:
            continue
        wait, length, basis = _estimate_wait_minutes(store, service, history_entries)
        if wait < target_wait:
            alternatives.append({
                "service_id": service["id"],
                "name": service["name"],
                "description": service.get("description"),
                "expected_duration": service["duration"],
                "queue_length": length,
                "estimated_wait_minutes": wait,
                "estimate_basis": basis,
                "minutes_saved": round(target_wait - wait, 1),
            })

    alternatives.sort(key=lambda a: a["estimated_wait_minutes"])
    best = alternatives[0] if alternatives else None

    return jsonify({
        "service_id": service_id,
        "service_name": target["name"],
        "estimated_wait_minutes": target_wait,
        "estimate_basis": target_basis,
        "queue_length": target_length,
        "recommendation": best,
        "alternatives": alternatives,
        "explanation": (
            f"Estimates use {'real historical service pace' if target_basis == 'historical' else 'live queue length × expected duration'}; "
            f"{'we found a shorter wait at ' + best['name'] if best else 'no shorter open alternative was found'}."
        ),
    }), 200


@smart_bp.get("/best-time")
@login_required
def best_time(user):
    """Suggest the quietest hours to join a service, from past join patterns.

    Query params:
      service_id  — the service to analyze (required)
    """
    service_id = request.args.get("service_id")
    if not service_id:
        return jsonify({"message": "service_id is required"}), 400

    store = current_app.config["STORE"]
    target = store.get_service(service_id)
    if not target:
        return jsonify({"message": "Service not found"}), 404

    joins_by_hour = {}
    for e in store.list_history():
        if e["service_id"] != service_id or e["action"] != "joined":
            continue
        hour = datetime.fromisoformat(e["timestamp"]).hour
        joins_by_hour[hour] = joins_by_hour.get(hour, 0) + 1

    if not joins_by_hour:
        return jsonify({
            "service_id": service_id,
            "service_name": target["name"],
            "quietest_hours": [],
            "busiest_hours": [],
            "explanation": "Not enough history yet to suggest a best time for this service.",
        }), 200

    ranked = sorted(joins_by_hour.items(), key=lambda kv: (kv[1], kv[0]))
    quietest = [{"hour": h, "joins": n} for h, n in ranked[:3]]
    busiest = [{"hour": h, "joins": n} for h, n in ranked[-3:][::-1]]

    def _fmt(hour):
        return f"{hour % 12 or 12}{'am' if hour < 24 and hour < 12 else 'pm'}"

    return jsonify({
        "service_id": service_id,
        "service_name": target["name"],
        "quietest_hours": quietest,
        "busiest_hours": busiest,
        "explanation": (
            f"Based on {sum(joins_by_hour.values())} past joins, "
            f"{target['name']} is quietest around {_fmt(quietest[0]['hour'])} "
            f"and busiest around {_fmt(busiest[0]['hour'])}."
        ),
    }), 200