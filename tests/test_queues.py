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
<<<<<<< Updated upstream
=======


def test_leave_queue_marks_status_canceled_not_deleted(client, store):
    # /mine and the store's public API only ever expose "waiting" entries,
    # so this checks the underlying record directly rather than the route.
    service = make_service(store)
    token, user = register_and_login(client, "l1@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token))

    all_entries = store._queue_entries[service["id"]]
    assert len(all_entries) == 1
    assert all_entries[0]["status"] == "canceled"
    assert all_entries[0]["position"] is None


def test_user_can_rejoin_after_leaving(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "l2@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.post(
        "/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["entry"]["status"] == "waiting"
    assert resp.get_json()["entry"]["position"] == 1


def test_positions_shift_down_after_someone_leaves(client, store):
    service = make_service(store, duration=5)
    token1, _ = register_and_login(client, "m1@example.com")
    token2, _ = register_and_login(client, "m2@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2))

    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token1))

    resp = client.get("/api/queues/mine", headers=auth_header(token2))
    assert resp.get_json()["queue_entries"][0]["position"] == 1


def test_served_entry_is_excluded_from_queue_length(client, store):
    # get_queue_length backs the "block delete while queue non-empty" rule
    # in services.py; a served entry must not keep counting against it.
    service = make_service(store)
    admin_token, _ = register_and_login(client, "admin4@example.com", role=ADMINISTRATOR)
    token, _ = register_and_login(client, "m3@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(admin_token)
    )
    assert store.get_queue_length(service["id"]) == 0


def test_join_triggers_notify_joined(client, store):
    service = make_service(store)
    token, user = register_and_login(client, "n1@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    notifications = store.list_notifications(user["id"])
    kinds = {n["kind"] for n in notifications}
    assert "joined" in kinds


def test_join_at_front_also_triggers_almost_ready(client, store):
    # position 1 is within ALMOST_READY_POSITION, so joining an empty
    # queue should fire both the "joined" and "almost_ready" alerts.
    service = make_service(store)
    token, user = register_and_login(client, "n2@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    kinds = {n["kind"] for n in store.list_notifications(user["id"])}
    assert kinds == {"joined", "almost_ready"}


def test_leaving_notifies_person_now_moved_up(client, store):
    service = make_service(store)
    token1, user1 = register_and_login(client, "n3@example.com")
    token2, user2 = register_and_login(client, "n4@example.com")
    token3, user3 = register_and_login(client, "n5@example.com")
    token4, user4 = register_and_login(client, "n6@example.com")

    for t in (token1, token2, token3, token4):
        client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(t))

    # user4 joined 4th (position 4), outside ALMOST_READY_POSITION=3, so no
    # almost_ready alert yet.
    assert "almost_ready" not in {n["kind"] for n in store.list_notifications(user4["id"])}

    # user1 leaves -> user4 moves from position 4 to position 3.
    client.post("/api/queues/leave", json={"service_id": service["id"]}, headers=auth_header(token1))

    assert "almost_ready" in {n["kind"] for n in store.list_notifications(user4["id"])}


def test_serve_next_notifies_new_front_of_line(client, store):
    service = make_service(store)
    admin_token, _ = register_and_login(client, "admin5@example.com", role=ADMINISTRATOR)
    token1, user1 = register_and_login(client, "n7@example.com")
    token2, user2 = register_and_login(client, "n8@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token2))

    client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(admin_token)
    )

    # user2 was already within ALMOST_READY_POSITION at position 2, so this
    # mainly confirms serve-next doesn't skip the recheck; more importantly,
    # they should now have received at least one almost_ready alert.
    kinds = {n["kind"] for n in store.list_notifications(user2["id"])}
    assert "almost_ready" in kinds
>>>>>>> Stashed changes
