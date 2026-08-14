from tests.conftest import auth_header, register_and_login
from app.utils import ADMINISTRATOR


def _admin_service(client, name, duration):
    slug = name.lower().replace(" ", "-")
    token, _ = register_and_login(client, f"admin-{slug}@example.com", role=ADMINISTRATOR)
    resp = client.post(
        "/api/services/",
        json={"name": name, "description": f"{name} desc", "duration": duration, "priority": "medium"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    return resp.get_json()["service"], token


def test_recommend_requires_service_id(client):
    token, _ = register_and_login(client, "u1@example.com")
    resp = client.get("/api/smart/recommend", headers=auth_header(token))
    assert resp.status_code == 400


def test_recommend_suggests_shorter_wait(client):
    busy, admin_token = _admin_service(client, "Busy Desk", 20)
    quiet, _ = _admin_service(client, "Quiet Desk", 10)

    # Put two people in the busy queue so wait = 2 * 20 = 40
    for email in ("a@example.com", "b@example.com"):
        t, _ = register_and_login(client, email)
        assert client.post(
            "/api/queues/join",
            json={"service_id": busy["id"]},
            headers=auth_header(t),
        ).status_code == 201

    user_token, _ = register_and_login(client, "chooser@example.com")
    resp = client.get(
        f"/api/smart/recommend?service_id={busy['id']}",
        headers=auth_header(user_token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["estimated_wait_minutes"] == 40
    assert body["recommendation"] is not None
    assert body["recommendation"]["service_id"] == quiet["id"]
    assert body["recommendation"]["estimated_wait_minutes"] == 0
    assert body["recommendation"]["minutes_saved"] == 40


def test_recommend_none_when_already_shortest(client):
    only, _ = _admin_service(client, "Only Desk", 15)
    token, _ = register_and_login(client, "alone@example.com")
    resp = client.get(
        f"/api/smart/recommend?service_id={only['id']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["recommendation"] is None
    assert resp.get_json()["alternatives"] == []
