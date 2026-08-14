# Smart Features Module (partial)
#
# Feature: recommend an alternative open service with a shorter estimated wait.
# What makes it "smart": compares live queue length × expected duration across
# open services and suggests a better option when one exists.
#
# DONE in this module:
#   GET /api/smart/recommend?service_id=<id>   (login required)
#   Homescreen "Join recommended" → POST /api/queues/join
#
# LEFT FOR THE TEAM (see TODOs below):
#   - Use historical average wait from History instead of live-only estimates
#   - "Best time to join" endpoint based on past join/serve patterns
#   - Surface smart insights on the admin Reports screen

from flask import Blueprint, current_app, jsonify, request

from app.utils import login_required

smart_bp = Blueprint("smart", __name__)


def _live_wait_minutes(store, service):
    """Live estimate: people waiting × expected duration."""
    length = store.get_queue_length(service["id"])
    duration = service.get("duration") or 0
    return length * duration, length


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

    target_wait, target_length = _live_wait_minutes(store, target)
    alternatives = []
    for service in _open_services(store):
        if service["id"] == service_id:
            continue
        wait, length = _live_wait_minutes(store, service)
        if wait < target_wait:
            alternatives.append({
                "service_id": service["id"],
                "name": service["name"],
                "description": service.get("description"),
                "expected_duration": service["duration"],
                "queue_length": length,
                "estimated_wait_minutes": wait,
                "minutes_saved": target_wait - wait,
            })

    alternatives.sort(key=lambda a: a["estimated_wait_minutes"])
    best = alternatives[0] if alternatives else None

    # TODO (team — remaining smart work):
    # 1. Replace/augment _live_wait_minutes with historical averages from
    #    store.list_history() (average wait_time_minutes per service).
    # 2. Add GET /api/smart/best-time?service_id=... that looks at past
    #    joined/served timestamps and suggests quieter hours.
    # 3. Surface smart insights on the admin Reports screen.

    return jsonify({
        "service_id": service_id,
        "service_name": target["name"],
        "estimated_wait_minutes": target_wait,
        "queue_length": target_length,
        "recommendation": best,
        "alternatives": alternatives,
        "explanation": (
            f"Based on live queue length × expected duration, "
            f"{'we found a shorter wait at ' + best['name'] if best else 'no shorter open alternative was found'}."
        ),
    }), 200
