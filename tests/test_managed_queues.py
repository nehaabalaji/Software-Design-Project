from app.utils import ADMINISTRATOR
from tests.conftest import auth_header, register_and_login


def make_admin(client):
    token, user = register_and_login(client, "admin-q@example.com", role=ADMINISTRATOR)
    return token, user


def test_create_and_list_managed_queues(client):
    token, _ = make_admin(client)
    service = client.post(
        "/api/services/",
        json={"name": "Advising", "description": "Walk-in advising", "duration": 15, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]

    # create_service auto-creates an open queue
    listed = client.get("/api/queues/")
    assert listed.status_code == 200
    assert listed.get_json()["count"] >= 1
    assert any(q["service_id"] == service["id"] for q in listed.get_json()["queues"])


def test_create_queue_requires_existing_service(client):
    token, _ = make_admin(client)
    resp = client.post(
        "/api/queues/",
        json={"service_id": "missing-service"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


def test_update_queue_status(client):
    token, _ = make_admin(client)
    service = client.post(
        "/api/services/",
        json={"name": "Billing", "description": "Billing help", "duration": 10, "priority": "low"},
        headers=auth_header(token),
    ).get_json()["service"]

    queues = client.get("/api/queues/").get_json()["queues"]
    queue = next(q for q in queues if q["service_id"] == service["id"])

    resp = client.put(
        f"/api/queues/{queue['queue_id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["queue"]["status"] == "closed"

    bad = client.put(
        f"/api/queues/{queue['queue_id']}/status",
        json={"status": "paused"},
        headers=auth_header(token),
    )
    assert bad.status_code == 400


def test_get_queue_details(client):
    token, _ = make_admin(client)
    service = client.post(
        "/api/services/",
        json={"name": "Tech", "description": "Support", "duration": 20, "priority": "high"},
        headers=auth_header(token),
    ).get_json()["service"]
    queue = next(
        q for q in client.get("/api/queues/").get_json()["queues"] if q["service_id"] == service["id"]
    )
    resp = client.get(f"/api/queues/{queue['queue_id']}")
    assert resp.status_code == 200
    body = resp.get_json()["queue"]
    assert body["queue_id"] == queue["queue_id"]
    assert body["service"]["name"] == "Tech"


def test_join_rejected_when_queue_closed(client):
    token, _ = make_admin(client)
    service = client.post(
        "/api/services/",
        json={"name": "ClosedSvc", "description": "desc", "duration": 10, "priority": "medium"},
        headers=auth_header(token),
    ).get_json()["service"]
    queue = next(
        q for q in client.get("/api/queues/").get_json()["queues"] if q["service_id"] == service["id"]
    )
    client.put(
        f"/api/queues/{queue['queue_id']}/status",
        json={"status": "closed"},
        headers=auth_header(token),
    )

    user_token, _ = register_and_login(client, "joiner@example.com")
    resp = client.post(
        "/api/queues/join",
        json={"service_id": service["id"]},
        headers=auth_header(user_token),
    )
    assert resp.status_code == 400
    assert "closed" in resp.get_json()["message"].lower()


def test_edit_service_put_returns_updated_object(client):
    """TA feedback: edit must be clearly implemented via PUT."""
    token, _ = make_admin(client)
    created = client.post(
        "/api/services/",
        json={
            "name": "Old Name",
            "description": "Old desc",
            "expected_duration": 12,
            "priority": "low",
        },
        headers=auth_header(token),
    ).get_json()["service"]

    resp = client.put(
        f"/api/services/{created['id']}",
        json={
            "name": "New Name",
            "description": "Updated description",
            "expected_duration": 30,
            "priority_level": 2,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["message"] == "Service updated successfully"
    updated = body["service"]
    assert updated["name"] == "New Name"
    assert updated["description"] == "Updated description"
    assert updated["duration"] == 30
    assert updated["expected_duration"] == 30
    assert updated["priority"] == "high"
    assert updated["priority_level"] == 2


def test_reject_empty_name_and_nonpositive_duration(client):
    token, _ = make_admin(client)
    resp = client.post(
        "/api/services/",
        json={"name": "   ", "description": "x", "duration": 0, "priority": "medium"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    errors = resp.get_json()["errors"]
    assert "name" in errors
    assert "duration" in errors
