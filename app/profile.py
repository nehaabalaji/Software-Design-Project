# UserProfile Module

# Stores profile details for the logged-in user (full name, optional phone,
# preferences), separate from UserCredentials per the A4 spec. One profile
# per user, linked by user_id.

# Endpoints:
#   GET  /api/profile/me   current user's profile (login required)
#   POST /api/profile/me   create profile (login required, one per user)
#   PUT  /api/profile/me   update profile fields (login required)

from flask import Blueprint, current_app, jsonify, request

from app.utils import login_required

profile_bp = Blueprint("profile", __name__)

MAX_FULL_NAME = 200
MAX_PHONE = 30
MAX_PREFERENCES = 500


def _validate(data, *, require_full_name):
    errors = {}

    full_name = (data.get("full_name") or "").strip()
    if require_full_name and not full_name:
        errors["full_name"] = "Full name is required"
    elif len(full_name) > MAX_FULL_NAME:
        errors["full_name"] = f"Full name must be {MAX_FULL_NAME} characters or fewer"

    phone = data.get("phone")
    if phone is not None:
        if not isinstance(phone, str):
            errors["phone"] = "Phone must be text"
        elif len(phone.strip()) > MAX_PHONE:
            errors["phone"] = f"Phone must be {MAX_PHONE} characters or fewer"

    preferences = data.get("preferences")
    if preferences is not None:
        if not isinstance(preferences, str):
            errors["preferences"] = "Preferences must be text"
        elif len(preferences.strip()) > MAX_PREFERENCES:
            errors["preferences"] = f"Preferences must be {MAX_PREFERENCES} characters or fewer"

    return errors


@profile_bp.get("/me")
@login_required
def get_my_profile(user):
    store = current_app.config["STORE"]
    profile = store.get_profile_by_user_id(user["id"])
    if profile is None:
        return jsonify({"message": "Profile not found"}), 404
    return jsonify({"profile": profile}), 200


@profile_bp.post("/me")
@login_required
def create_my_profile(user):
    store = current_app.config["STORE"]
    data = request.get_json(silent=True) or {}

    errors = _validate(data, require_full_name=True)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    try:
        profile = store.create_profile(
            user_id=user["id"],
            full_name=data["full_name"],
            phone=data.get("phone"),
            preferences=data.get("preferences", ""),
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 409

    return jsonify({"message": "Profile created", "profile": profile}), 201


@profile_bp.put("/me")
@login_required
def update_my_profile(user):
    store = current_app.config["STORE"]
    data = request.get_json(silent=True) or {}

    allowed = {k: v for k, v in data.items() if k in ("full_name", "phone", "preferences")}
    if not allowed:
        return jsonify({"message": "No updatable fields provided"}), 400

    errors = _validate(allowed, require_full_name="full_name" in allowed)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    cleaned = {}
    if "full_name" in allowed:
        cleaned["full_name"] = allowed["full_name"].strip()
    if "phone" in allowed:
        cleaned["phone"] = (allowed["phone"] or "").strip() or None
    if "preferences" in allowed:
        cleaned["preferences"] = (allowed["preferences"] or "").strip()

    profile = store.update_profile(user["id"], **cleaned)
    if profile is None:
        return jsonify({"message": "Profile not found"}), 404

    return jsonify({"message": "Profile updated", "profile": profile}), 200
