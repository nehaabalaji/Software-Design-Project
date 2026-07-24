# Authentication Module
# register, login, roles (User / Administrator), basic validation

import re

from flask import Blueprint, current_app, jsonify, request

from app.utils import (
    ADMINISTRATOR,
    USER,
    VALID_ROLES,
    check_password,
    get_bearer_token,
    hash_password,
)

auth_bp = Blueprint("auth", __name__)

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate_email(email):
    if not email or not str(email).strip():
        return "Email is required"
    if not EMAIL_REGEX.match(str(email).strip()):
        return "Please enter a valid email address"
    return None


def _validate_password(password):
    if not password:
        return "Password is required"
    if len(password) < 8:
        return "Password must be at least 8 characters"
    return None


def _validate_register(data):
    if not isinstance(data, dict):
        return {"body": "Request body must be a JSON object"}

    errors = {}
    email = data.get("email", "") if isinstance(data.get("email", ""), str) else ""
    password = data.get("password", "") if isinstance(data.get("password", ""), str) else ""
    role = data.get("role") or USER
    if not isinstance(role, str):
        role = ""

    err = _validate_email(email)
    if err:
        errors["email"] = err

    err = _validate_password(password)
    if err:
        errors["password"] = err

    if role not in VALID_ROLES:
        errors["role"] = f"Role must be one of: {USER}, {ADMINISTRATOR}"

    return errors


def _validate_login(data):
    if not isinstance(data, dict):
        return {"body": "Request body must be a JSON object"}

    errors = {}
    email = data.get("email", "") if isinstance(data.get("email", ""), str) else ""
    password = data.get("password", "") if isinstance(data.get("password", ""), str) else ""

    err = _validate_email(email)
    if err:
        errors["email"] = err

    err = _validate_password(password)
    if err:
        errors["password"] = err

    return errors


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)
    errors = _validate_register(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    store = current_app.config["STORE"]
    try:
        user = store.create_user(
            email=data["email"].strip(),
            password_hash=hash_password(data["password"]),
            role=data.get("role") or USER,
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
        )
    except ValueError as e:
        return jsonify({"message": str(e), "errors": {"email": str(e)}}), 409

    return jsonify({"message": "Registration successful", "user": user}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    errors = _validate_login(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    store = current_app.config["STORE"]
    user = store.get_user_by_email(data["email"].strip())
    if user is None or not check_password(user["password_hash"], data["password"]):
        return jsonify({"message": "Invalid email or password"}), 401

    token = store.create_token(user["id"])
    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        },
    }), 200


@auth_bp.get("/me")
def me():
    store = current_app.config["STORE"]
    token = get_bearer_token()
    if not token:
        return jsonify({"message": "Authentication required"}), 401

    user_id = store.get_user_id_for_token(token)
    user = store.get_user_by_id(user_id) if user_id else None
    if not user:
        return jsonify({"message": "Authentication required"}), 401

    return jsonify({
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        }
    }), 200


@auth_bp.post("/logout")
def logout():
    store = current_app.config["STORE"]
    token = get_bearer_token()
    if not token or not store.revoke_token(token):
        return jsonify({"message": "Authentication required"}), 401
    return jsonify({"message": "Logout successful"}), 200
