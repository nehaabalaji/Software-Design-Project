from app.store import InMemoryStore
from app.utils import USER
from tests.conftest import auth_header, register_and_login


# endpoint: get


def test_get_profile_requires_login(client):
    assert client.get("/api/profile/me").status_code == 401


def test_get_profile_missing_returns_404(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.get("/api/profile/me", headers=auth_header(token))
    assert resp.status_code == 404


def test_get_profile_returns_own_profile(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token),
                json={"full_name": "Sam Parsons"})

    resp = client.get("/api/profile/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["full_name"] == "Sam Parsons"


# endpoint: create


def test_create_profile(client):
    token, user = register_and_login(client, "u@example.com")
    resp = client.post("/api/profile/me", headers=auth_header(token),
                       json={"full_name": "Sam Parsons", "phone": "713-555-0100",
                             "preferences": "email notifications"})
    assert resp.status_code == 201
    profile = resp.get_json()["profile"]
    assert profile["user_id"] == user["id"]
    assert profile["full_name"] == "Sam Parsons"
    assert profile["phone"] == "713-555-0100"
    assert profile["preferences"] == "email notifications"


def test_create_profile_requires_login(client):
    assert client.post("/api/profile/me", json={"full_name": "X"}).status_code == 401


def test_create_profile_requires_full_name(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.post("/api/profile/me", headers=auth_header(token), json={})
    assert resp.status_code == 400
    assert "full_name" in resp.get_json()["errors"]


def test_create_profile_rejects_long_full_name(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.post("/api/profile/me", headers=auth_header(token),
                       json={"full_name": "x" * 201})
    assert resp.status_code == 400
    assert "full_name" in resp.get_json()["errors"]


def test_create_profile_rejects_bad_phone_type(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.post("/api/profile/me", headers=auth_header(token),
                       json={"full_name": "Sam", "phone": 12345})
    assert resp.status_code == 400
    assert "phone" in resp.get_json()["errors"]


def test_create_profile_duplicate_returns_409(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token), json={"full_name": "Sam"})
    resp = client.post("/api/profile/me", headers=auth_header(token), json={"full_name": "Sam Again"})
    assert resp.status_code == 409


def test_profiles_are_per_user(client):
    token_a, _ = register_and_login(client, "a@example.com")
    token_b, _ = register_and_login(client, "b@example.com")
    client.post("/api/profile/me", headers=auth_header(token_a), json={"full_name": "User A"})
    client.post("/api/profile/me", headers=auth_header(token_b), json={"full_name": "User B"})

    resp_a = client.get("/api/profile/me", headers=auth_header(token_a))
    resp_b = client.get("/api/profile/me", headers=auth_header(token_b))
    assert resp_a.get_json()["profile"]["full_name"] == "User A"
    assert resp_b.get_json()["profile"]["full_name"] == "User B"


# endpoint: update


def test_update_profile(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token), json={"full_name": "Sam"})

    resp = client.put("/api/profile/me", headers=auth_header(token),
                      json={"preferences": "sms alerts"})
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["preferences"] == "sms alerts"
    assert resp.get_json()["profile"]["full_name"] == "Sam"


def test_update_profile_missing_returns_404(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.put("/api/profile/me", headers=auth_header(token),
                      json={"full_name": "New Name"})
    assert resp.status_code == 404


def test_update_profile_rejects_empty_body(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token), json={"full_name": "Sam"})
    resp = client.put("/api/profile/me", headers=auth_header(token), json={"irrelevant": "x"})
    assert resp.status_code == 400


def test_update_profile_rejects_blank_full_name(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token), json={"full_name": "Sam"})
    resp = client.put("/api/profile/me", headers=auth_header(token), json={"full_name": "  "})
    assert resp.status_code == 400


def test_update_profile_requires_login(client):
    assert client.put("/api/profile/me", json={"full_name": "X"}).status_code == 401


def test_update_clears_phone_with_empty_string(client):
    token, _ = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token),
                json={"full_name": "Sam", "phone": "713-555-0100"})
    resp = client.put("/api/profile/me", headers=auth_header(token), json={"phone": ""})
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["phone"] is None


# store methods directly


def test_store_create_profile_requires_existing_user():
    store = InMemoryStore()
    try:
        store.create_profile(user_id="nope", full_name="Ghost")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_store_create_and_get_profile():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    created = store.create_profile(user_id=user["id"], full_name="Sam", preferences="email")
    fetched = store.get_profile_by_user_id(user["id"])
    assert fetched["id"] == created["id"]
    assert fetched["full_name"] == "Sam"


def test_store_duplicate_profile_raises():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    store.create_profile(user_id=user["id"], full_name="Sam")
    try:
        store.create_profile(user_id=user["id"], full_name="Sam 2")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_store_update_missing_profile_returns_none():
    store = InMemoryStore()
    assert store.update_profile("nope", full_name="X") is None


def test_store_profile_survives_across_requests(client, store):
    # Data persisted through one request is retrievable in a later one.
    # the A4 "persisted and retrievable across requests" requirement.
    token, user = register_and_login(client, "u@example.com")
    client.post("/api/profile/me", headers=auth_header(token),
                json={"full_name": "Persistent Sam"})

    profile = store.get_profile_by_user_id(user["id"])
    assert profile is not None
    assert profile["full_name"] == "Persistent Sam"

    resp = client.get("/api/profile/me", headers=auth_header(token))
    assert resp.get_json()["profile"]["full_name"] == "Persistent Sam"
