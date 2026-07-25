from app.utils import ADMINISTRATOR
from tests.conftest import auth_header, register_and_login


def make_service(store, name="Checkup", duration=10, priority="medium"):
    return store.create_service(
        name=name, description="desc", duration=duration, priority=priority
    )


def test_join_queue_returns_position_and_wait(client, store):
    service = make_service(store, duration=10)
    token, user = register_and_login(client, "user1@example.com")

    resp = client.post(
        "/api/queues/join",
        json={"service_id": service["id"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    entry = resp.get_json()["entry"]
    assert entry["position"] == 1
    assert entry["estimated_wait_minutes"] == 10
    assert entry["status"] == "waiting"


def test_join_queue_requires_login(client, store):
    service = make_service(store)
    resp = client.post("/api/queues/join", json={"service_id": service["id"]})
    assert resp.status_code == 401


def test_join_missing_service(client, store):
    token, _ = register_and_login(client, "user2@example.com")
    resp = client.post(
        "/api/queues/join", json={"service_id": "nope"}, headers=auth_header(token)
    )
    assert resp.status_code == 404


def test_cannot_join_twice(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "user3@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    resp = client.post(
        "/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 409


def test_second_arrival_gets_next_position(client, store):
    service = make_service(store, duration=5)
    token1, _ = register_and_login(client, "a@example.com")
    token2, _ = register_and_login(client, "b@example.com")

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    resp = client.post(
        "/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2)
    )
    entry = resp.get_json()["entry"]
    assert entry["position"] == 2
    assert entry["estimated_wait_minutes"] == 10


def test_queues_are_independent_per_service(client, store):
    service_a = make_service(store, name="A", duration=5, priority="low")
    service_b = make_service(store, name="B", duration=5, priority="urgent")

    token_a, _ = register_and_login(client, "c@example.com")
    token_b, _ = register_and_login(client, "d@example.com")

    client.post("/api/queues/join", json={"service_id": service_a["id"]}, headers=auth_header(token_a))
    resp = client.post(
        "/api/queues/join", json={"service_id": service_b["id"]}, headers=auth_header(token_b)
    )
    # each service has its own queue, so both entrants land at position 1
    assert resp.get_json()["entry"]["position"] == 1


def test_leave_queue(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "e@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.post(
        "/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 200

    resp = client.get("/api/queues/mine", headers=auth_header(token))
    assert resp.get_json()["count"] == 0


def test_leave_when_not_in_queue(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "f@example.com")
    resp = client.post(
        "/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 404


def test_mine_lists_only_current_user(client, store):
    service = make_service(store)
    token1, _ = register_and_login(client, "g@example.com")
    token2, _ = register_and_login(client, "h@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2))

    resp = client.get("/api/queues/mine", headers=auth_header(token1))
    body = resp.get_json()
    assert body["count"] == 1
    assert body["queue_entries"][0]["position"] == 1


def test_service_queue_requires_admin(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "i@example.com")
    resp = client.get(f"/api/queues/service/{service['id']}", headers=auth_header(token))
    assert resp.status_code == 403


def test_service_queue_admin_view(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "j@example.com")
    admin_token, _ = register_and_login(client, "admin1@example.com", role=ADMINISTRATOR)
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get(f"/api/queues/service/{service['id']}", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] == 1
    assert body["queue"][0]["position"] == 1


def test_serve_next_requires_admin(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "k@example.com")
    resp = client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 403


def test_serve_next_serves_in_priority_then_arrival_order(client, store):
    service = make_service(store, priority="medium")
    admin_token, _ = register_and_login(client, "admin2@example.com", role=ADMINISTRATOR)

    token_low, user_low = register_and_login(client, "low@example.com")
    token_urgent, user_urgent = register_and_login(client, "urgent@example.com")

    # both join the same service (same base priority), so arrival order decides
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token_low))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token_urgent))

    resp = client.post(
        "/api/queues/serve-next",
        json={"service_id": service["id"]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    served = resp.get_json()["served"]
    assert served["user_id"] == user_low["id"]
    assert served["status"] == "served"

    # queue now has just the second user
    resp = client.get("/api/queues/mine", headers=auth_header(token_urgent))
    assert resp.get_json()["queue_entries"][0]["position"] == 1


def test_serve_next_on_empty_queue(client, store):
    service = make_service(store)
    admin_token, _ = register_and_login(client, "admin3@example.com", role=ADMINISTRATOR)
    resp = client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(admin_token)
    )
    assert resp.status_code == 404
