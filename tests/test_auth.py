from app.utils import ADMINISTRATOR, USER
from tests.conftest import auth_header, register_and_login


def test_register_user(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "password123",
            "role": USER,
            "first_name": "Neha",
            "last_name": "Balaji",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["role"] == USER
    assert "password_hash" not in body["user"]


def test_register_administrator(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "admin@example.com",
            "password": "password123",
            "role": ADMINISTRATOR,
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["user"]["role"] == ADMINISTRATOR


def test_register_defaults_to_user(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "default@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["user"]["role"] == USER


def test_register_validation(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "bad", "password": "short", "role": "Manager"},
    )
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert "email" in errors
    assert "password" in errors
    assert "role" in errors


def test_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_login_success(client):
    token, user = register_and_login(client, "login@example.com", role=ADMINISTRATOR)
    assert token
    assert user["role"] == ADMINISTRATOR


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "real@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "real@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_me_and_logout(client):
    token, _ = register_and_login(client, "me@example.com")
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "me@example.com"

    assert client.post("/api/auth/logout", headers=auth_header(token)).status_code == 200
    assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 401
