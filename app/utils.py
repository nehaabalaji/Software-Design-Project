# shared helpers used by auth (and later by other modules)

from functools import wraps

from flask import current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

USER = "User"
ADMINISTRATOR = "Administrator"
VALID_ROLES = {USER, ADMINISTRATOR}


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:].strip()
        return token or None
    return None


def get_current_user():
    """Return the logged-in user dict, or None."""
    store = current_app.config["STORE"]
    token = get_bearer_token()
    if not token:
        return None
    user_id = store.get_user_id_for_token(token)
    if not user_id:
        return None
    user = store.get_user_by_id(user_id)
    if not user:
        return None
    return {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
    }


def login_required(fn):
    """Use this on routes that need any logged-in user."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"message": "Authentication required"}), 401
        return fn(user, *args, **kwargs)

    return wrapper


def admin_required(fn):
    """Use this on routes that only administrators can call."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"message": "Authentication required"}), 401
        if user["role"] != ADMINISTRATOR:
            return jsonify({"message": "Administrator access required"}), 403
        return fn(user, *args, **kwargs)

    return wrapper


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def check_password(password_hash, password):
    return check_password_hash(password_hash, password)
