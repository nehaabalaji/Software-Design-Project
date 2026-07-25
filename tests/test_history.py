from app.utils import ADMINISTRATOR
from tests.conftest import auth_header, register_and_login


def make_service(store, name="Checkup", duration=10, priority="medium"):
    return store.create_service(
        name=name, description="desc", duration=duration, priority=priority
    )


def test_mine_requires_login(client, store):
    resp = client.get("/api/history/mine")
    assert resp.status_code == 401


def test_mine_records_join_and_leave(client, store):
    service = make_service(store)
    token, user = register_and_login(client, "user1@example.com")

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get("/api/history/mine", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] == 2
    actions = {e["action"] for e in body["history"]}
    assert actions == {"joined", "left"}
    assert all(e["user_id"] == user["id"] for e in body["history"])


def test_mine_only_shows_own_entries(client, store):
    service = make_service(store)
    token1, _ = register_and_login(client, "a@example.com")
    token2, _ = register_and_login(client, "b@example.com")

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2))

    resp = client.get("/api/history/mine", headers=auth_header(token1))
    assert resp.get_json()["count"] == 1


def test_mine_filters_by_action(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "c@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get("/api/history/mine?action=left", headers=auth_header(token))
    body = resp.get_json()
    assert body["count"] == 1
    assert body["history"][0]["action"] == "left"


def test_mine_invalid_action(client, store):
    token, _ = register_and_login(client, "d@example.com")
    resp = client.get("/api/history/mine?action=bogus", headers=auth_header(token))
    assert resp.status_code == 400


def test_all_history_requires_admin(client, store):
    token, _ = register_and_login(client, "e@example.com")
    resp = client.get("/api/history/", headers=auth_header(token))
    assert resp.status_code == 403


def test_all_history_admin_sees_everyone(client, store):
    service = make_service(store)
    token1, _ = register_and_login(client, "f@example.com")
    token2, _ = register_and_login(client, "g@example.com")
    admin_token, _ = register_and_login(client, "admin@example.com", role=ADMINISTRATOR)

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2))

    resp = client.get("/api/history/", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 2


def test_stats_requires_admin(client, store):
    token, _ = register_and_login(client, "h@example.com")
    resp = client.get("/api/history/stats", headers=auth_header(token))
    assert resp.status_code == 403


def test_stats_aggregates(client, store):
    service = make_service(store, duration=10)
    token, _ = register_and_login(client, "i@example.com")
    admin_token, _ = register_and_login(client, "admin2@example.com", role=ADMINISTRATOR)

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(admin_token)
    )

    resp = client.get("/api/history/stats", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_entries"] == 2  # joined + served
    assert body["by_action"]["joined"] == 1
    assert body["by_action"]["served"] == 1
    assert body["by_service"]["Checkup"] == 2
    assert body["average_wait_time_minutes"] == 10.0
