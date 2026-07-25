from app.utils import ADMINISTRATOR, USER
from tests.conftest import auth_header, register_and_login

VALID_SERVICE = {
    "name": "Passport Renewal",
    "description": "Renew an existing passport.",
    "expected_duration": 25,
    "priority": "Normal",
}


def admin_token(client, email="admin@example.com"):
    token, _ = register_and_login(client, email, role=ADMINISTRATOR)
    return token


def user_token(client, email="user@example.com"):
    token, _ = register_and_login(client, email, role=USER)
    return token


def create_service(client, token, **overrides):
    payload = dict(VALID_SERVICE)
    payload.update(overrides)
    return client.post("/api/services/", json=payload, headers=auth_header(token))


# ---- creation ----


def test_admin_can_create_service(client):
    token = admin_token(client)
    resp = create_service(client, token)
    assert resp.status_code == 201
    service = resp.get_json()["service"]
    assert service["name"] == "Passport Renewal"
    assert service["expected_duration"] == 25
    assert service["priority"] == "Normal"
    assert service["is_open"] is True
    assert service["id"]


def test_create_trims_whitespace(client):
    token = admin_token(client)
    resp = create_service(client, token, name="  Tech Support  ")
    assert resp.get_json()["service"]["name"] == "Tech Support"


def test_regular_user_cannot_create_service(client):
    token = user_token(client)
    assert create_service(client, token).status_code == 403


def test_anonymous_cannot_create_service(client):
    assert client.post("/api/services/", json=VALID_SERVICE).status_code == 401


def test_duplicate_service_name_rejected(client):
    token = admin_token(client)
    assert create_service(client, token).status_code == 201
    assert create_service(client, token).status_code == 409


def test_duplicate_name_is_case_insensitive(client):
    token = admin_token(client)
    create_service(client, token)
    assert create_service(client, token, name="passport renewal").status_code == 409


# ---- validation ----


def test_missing_fields_rejected(client):
    token = admin_token(client)
    resp = client.post("/api/services/", json={}, headers=auth_header(token))
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert "name" in errors
    assert "description" in errors
    assert "expected_duration" in errors
    assert "priority" in errors


def test_blank_name_rejected(client):
    token = admin_token(client)
    resp = create_service(client, token, name="   ")
    assert resp.status_code == 400
    assert "name" in resp.get_json()["errors"]


def test_name_length_limit(client):
    token = admin_token(client)
    resp = create_service(client, token, name="x" * 101)
    assert resp.status_code == 400
    assert "name" in resp.get_json()["errors"]


def test_name_at_limit_accepted(client):
    token = admin_token(client)
    assert create_service(client, token, name="x" * 100).status_code == 201


def test_description_length_limit(client):
    token = admin_token(client)
    resp = create_service(client, token, description="x" * 501)
    assert resp.status_code == 400
    assert "description" in resp.get_json()["errors"]


def test_duration_must_be_integer(client):
    token = admin_token(client)
    resp = create_service(client, token, expected_duration="25")
    assert resp.status_code == 400
    assert "expected_duration" in resp.get_json()["errors"]


def test_duration_rejects_boolean(client):
    token = admin_token(client)
    resp = create_service(client, token, expected_duration=True)
    assert resp.status_code == 400


def test_duration_out_of_range(client):
    token = admin_token(client)
    assert create_service(client, token, expected_duration=0).status_code == 400
    assert create_service(client, token, expected_duration=-5).status_code == 400
    assert create_service(client, token, expected_duration=481).status_code == 400


def test_invalid_priority_rejected(client):
    token = admin_token(client)
    resp = create_service(client, token, priority="Urgent")
    assert resp.status_code == 400
    assert "priority" in resp.get_json()["errors"]


def test_non_object_body_rejected(client):
    token = admin_token(client)
    resp = client.post("/api/services/", json=["not", "an", "object"], headers=auth_header(token))
    assert resp.status_code == 400


# ---- listing and retrieval ----


def test_user_can_list_services(client):
    admin = admin_token(client)
    create_service(client, admin)
    create_service(client, admin, name="Billing Inquiry")

    token = user_token(client)
    resp = client.get("/api/services/", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.get_json()["services"]) == 2


def test_list_requires_login(client):
    assert client.get("/api/services/").status_code == 401


def test_get_single_service(client):
    admin = admin_token(client)
    service_id = create_service(client, admin).get_json()["service"]["id"]

    resp = client.get(f"/api/services/{service_id}", headers=auth_header(admin))
    assert resp.status_code == 200
    assert resp.get_json()["service"]["name"] == "Passport Renewal"


def test_get_missing_service_returns_404(client):
    token = admin_token(client)
    assert client.get("/api/services/nope", headers=auth_header(token)).status_code == 404


# ---- updates ----


def test_admin_can_update_service(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{service_id}",
        json={"expected_duration": 40, "priority": "High"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    service = resp.get_json()["service"]
    assert service["expected_duration"] == 40
    assert service["priority"] == "High"
    assert service["name"] == "Passport Renewal"


def test_partial_update_validates_supplied_fields_only(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{service_id}",
        json={"expected_duration": 900},
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    assert "expected_duration" in resp.get_json()["errors"]


def test_update_can_close_queue(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{service_id}",
        json={"is_open": False},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["service"]["is_open"] is False


def test_update_rejects_non_boolean_is_open(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{service_id}",
        json={"is_open": "yes"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


def test_update_to_existing_name_rejected(client):
    token = admin_token(client)
    create_service(client, token)
    second_id = create_service(client, token, name="Billing Inquiry").get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{second_id}",
        json={"name": "Passport Renewal"},
        headers=auth_header(token),
    )
    assert resp.status_code == 409


def test_service_can_keep_its_own_name_on_update(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(
        f"/api/services/{service_id}",
        json={"name": "Passport Renewal", "priority": "High"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


def test_empty_update_rejected(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    resp = client.put(f"/api/services/{service_id}", json={}, headers=auth_header(token))
    assert resp.status_code == 400


def test_update_missing_service_returns_404(client):
    token = admin_token(client)
    resp = client.put("/api/services/nope", json={"priority": "High"}, headers=auth_header(token))
    assert resp.status_code == 404


def test_regular_user_cannot_update(client):
    admin = admin_token(client)
    service_id = create_service(client, admin).get_json()["service"]["id"]

    token = user_token(client)
    resp = client.put(
        f"/api/services/{service_id}",
        json={"priority": "High"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


# ---- deletion ----


def test_admin_can_delete_service(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]

    assert client.delete(f"/api/services/{service_id}", headers=auth_header(token)).status_code == 200
    assert client.get(f"/api/services/{service_id}", headers=auth_header(token)).status_code == 404


def test_name_freed_after_delete(client):
    token = admin_token(client)
    service_id = create_service(client, token).get_json()["service"]["id"]
    client.delete(f"/api/services/{service_id}", headers=auth_header(token))

    assert create_service(client, token).status_code == 201


def test_delete_missing_service_returns_404(client):
    token = admin_token(client)
    assert client.delete("/api/services/nope", headers=auth_header(token)).status_code == 404


def test_regular_user_cannot_delete(client):
    admin = admin_token(client)
    service_id = create_service(client, admin).get_json()["service"]["id"]

    token = user_token(client)
    assert client.delete(f"/api/services/{service_id}", headers=auth_header(token)).status_code == 403
