# History Module
#
# Tracks queue participation history (join/leave/served/no-show).
# `store.add_history_entry(...)` (in app/store.py) is the integration
# point other modules -- the Queue module -- call whenever something
# history-worthy happens.
#
# Endpoints:
#   GET /api/history/mine        current user's own history (login required)
#   GET /api/history/            all history, filterable (admin)
#   GET /api/history/stats       aggregate stats (admin)
#   GET /api/history/report      full report: summary + per-service + per-user
#                                 breakdown, filterable (admin)
#   GET /api/history/report.csv  same filters, raw rows as a CSV download (admin)
#
# Filters shared by /, /report and /report.csv: action, user_id, service_id,
# start_date, end_date (YYYY-MM-DD or full ISO datetime).

import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, request

from app.utils import admin_required, login_required

history_bp = Blueprint("history", __name__)

VALID_ACTIONS = {"joined", "left", "served", "no_show"}


def _entry_timestamp(entry):
    return datetime.fromisoformat(entry["timestamp"])


def _filter_history(entries, user_id=None, service_id=None, action=None, start=None, end=None):
    result = entries
    if user_id is not None:
        result = [e for e in result if e["user_id"] == user_id]
    if service_id is not None:
        result = [e for e in result if e["service_id"] == service_id]
    if action is not None:
        result = [e for e in result if e["action"] == action]
    if start is not None:
        result = [e for e in result if _entry_timestamp(e) >= start]
    if end is not None:
        result = [e for e in result if _entry_timestamp(e) <= end]
    return result


def _parse_limit_arg():
    raw = request.args.get("limit")
    if raw is None:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, "limit must be an integer"


def _parse_date_arg(name, end_of_day=False):
    """Accepts YYYY-MM-DD or a full ISO datetime. Date-only values are
    treated as UTC midnight (or 23:59:59.999999 when end_of_day=True, so an
    end_date filter includes that whole day)."""
    raw = request.args.get(name)
    if not raw:
        return None, None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None, f"{name} must be an ISO date (YYYY-MM-DD) or datetime"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if end_of_day and len(raw) <= 10:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed, None


def _collect_filtered_history(store):
    """Parse action/user_id/service_id/date-range filters from the query
    string and return (entries, error_response). entries is newest-first."""
    action = request.args.get("action")
    if action and action not in VALID_ACTIONS:
        return None, (jsonify({"message": f"action must be one of {sorted(VALID_ACTIONS)}"}), 400)

    start, err = _parse_date_arg("start_date")
    if err:
        return None, (jsonify({"message": err}), 400)
    end, err = _parse_date_arg("end_date", end_of_day=True)
    if err:
        return None, (jsonify({"message": err}), 400)

    entries = _filter_history(
        store.list_history(),
        user_id=request.args.get("user_id"),
        service_id=request.args.get("service_id"),
        action=action,
        start=start,
        end=end,
    )
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries, None


def _average_wait(entries):
    wait_times = [
        e["wait_time_minutes"] for e in entries
        if isinstance(e.get("wait_time_minutes"), (int, float))
    ]
    return round(sum(wait_times) / len(wait_times), 2) if wait_times else None


def _build_report(entries):
    """Aggregate filtered history entries into the three sections the
    reporting module needs: overall stats, per-service activity, and
    per-user participation history."""
    by_action = {}
    for e in entries:
        by_action[e["action"]] = by_action.get(e["action"], 0) + 1

    services = {}
    for e in entries:
        key = e["service_id"] or "unknown"
        bucket = services.setdefault(key, {
            "service_id": e["service_id"],
            "service_name": e["service_name"] or "Unknown service",
            "total_entries": 0,
            "by_action": {},
            "_wait_times": [],
        })
        bucket["total_entries"] += 1
        bucket["by_action"][e["action"]] = bucket["by_action"].get(e["action"], 0) + 1
        if isinstance(e.get("wait_time_minutes"), (int, float)):
            bucket["_wait_times"].append(e["wait_time_minutes"])

    service_list = []
    for bucket in services.values():
        wait_times = bucket.pop("_wait_times")
        bucket["average_wait_time_minutes"] = (
            round(sum(wait_times) / len(wait_times), 2) if wait_times else None
        )
        service_list.append(bucket)
    service_list.sort(key=lambda s: s["total_entries"], reverse=True)

    users = {}
    for e in entries:
        key = e["user_id"]
        bucket = users.setdefault(key, {
            "user_id": e["user_id"],
            "email": e["user_email"],
            "total_entries": 0,
            "by_action": {},
            "entries": [],
        })
        bucket["total_entries"] += 1
        bucket["by_action"][e["action"]] = bucket["by_action"].get(e["action"], 0) + 1
        bucket["entries"].append({
            "timestamp": e["timestamp"],
            "service_name": e["service_name"],
            "action": e["action"],
            "wait_time_minutes": e["wait_time_minutes"],
        })

    user_list = list(users.values())
    user_list.sort(key=lambda u: u["total_entries"], reverse=True)

    return {
        "summary": {
            "total_entries": len(entries),
            "by_action": by_action,
            "average_wait_time_minutes": _average_wait(entries),
        },
        "services": service_list,
        "users": user_list,
    }


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
    entries, err = _collect_filtered_history(store)
    if err:
        return err
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

    return jsonify({
        "total_entries": total,
        "by_action": by_action,
        "by_service": by_service,
        "average_wait_time_minutes": _average_wait(entries),
    }), 200


@history_bp.get("/report")
@admin_required
def history_report(admin_user):
    """Reporting module: users + their participation history, service
    activity, and overall usage stats -- filterable by action, user_id,
    service_id, start_date, end_date."""
    store = current_app.config["STORE"]
    entries, err = _collect_filtered_history(store)
    if err:
        return err

    report = _build_report(entries)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["filters"] = {
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "service_id": request.args.get("service_id"),
        "user_id": request.args.get("user_id"),
        "action": request.args.get("action"),
    }
    return jsonify(report), 200


@history_bp.get("/report.csv")
@admin_required
def history_report_csv(admin_user):
    """Same filters as /report, exported as a downloadable CSV of the raw
    (filtered) history rows -- one row per queue participation event."""
    store = current_app.config["STORE"]
    entries, err = _collect_filtered_history(store)
    if err:
        return err

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "timestamp", "user_email", "service_name", "action",
        "wait_time_minutes", "position_at_join", "notes",
    ])
    for e in entries:
        writer.writerow([
            e["timestamp"],
            e["user_email"] or "",
            e["service_name"] or "",
            e["action"],
            e["wait_time_minutes"] if e["wait_time_minutes"] is not None else "",
            e["position_at_join"] if e["position_at_join"] is not None else "",
            e["notes"] or "",
        ])

    filename = f"queuesmart_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
