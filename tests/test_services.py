from app.utils import ADMINISTRATOR
from tests.conftest import auth_header, register_and_login


def make_admin(client):
    token, user = register_and_login(client, "admin@example.com", role=ADMINISTRATOR)
    return token, user


def test_list_services_empty(client):
    resp = client.get("/api/services/")
    assert resp.status_code == 200
    assert resp.get_json() == {"services": [], "count": 0}


def test_create_service_requires_admin(client):
    token, _ = register_and_login(client, "user@example.com")
    resp = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_create_service_as_admin(client):
    token, _ = make_admin(client)
    resp = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    service = resp.get_json()["service"]
    assert service["name"] == "Checkup"
    assert service["queue_length"] == 0


def test_create_service_validation(client):
    token, _ = make_admin(client)
    resp = client.post(
        "/api/services/",
        json={"name": "A", "description": "", "duration": 0, "priority": "urgentish"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert "name" in errors
    assert "description" in errors
    assert "duration" in errors
    assert "priority" in errors


def test_create_service_duplicate_name(client):
    token, _ = make_admin(client)
    payload = {"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"}
    assert client.post("/api/services/", json=payload, headers=auth_header(token)).status_code == 201
    resp = client.post("/api/services/", json=payload, headers=auth_header(token))
    assert resp.status_code == 409


def test_get_service(client):
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    resp = client.get(f"/api/services/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["service"]["name"] == "Checkup"


def test_get_service_not_found(client):
    resp = client.get("/api/services/nope")
    assert resp.status_code == 404


def test_update_service_partial(client):
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    resp = client.put(
        f"/api/services/{created['id']}",
        json={"duration": 20},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    updated = resp.get_json()["service"]
    assert updated["duration"] == 20
    assert updated["name"] == "Checkup"


def test_update_service_requires_admin(client):
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    user_token, _ = register_and_login(client, "user2@example.com")
    resp = client.put(
        f"/api/services/{created['id']}",
        json={"duration": 20},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 403


def test_delete_service(client):
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    resp = client.delete(f"/api/services/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert client.get(f"/api/services/{created['id']}").status_code == 404


def test_delete_service_blocked_with_active_queue(client, store):
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={"name": "Checkup", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    user_token, _ = register_and_login(client, "user3@example.com")
    client.post("/api/queues/join", json={"service_id": created["id"]}, headers=auth_header(user_token))

    resp = client.delete(f"/api/services/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 409
