from datetime import datetime, timezone

from tests.conftest import auth_header, register_and_login


def make_service(store, name="Checkup", duration=10, priority="medium"):
    return store.create_service(
        name=name, description="desc", duration=duration, priority=priority
    )


def seed_served(store, user_id, service_id, wait, position):
    store.add_history_entry(
        user_id=user_id, service_id=service_id, action="served",
        wait_time_minutes=wait, position_at_join=position,
    )


def seed_join_at_hour(store, user_id, service_id, hour):
    entry = store.add_history_entry(
        user_id=user_id, service_id=service_id, action="joined"
    )
    # add_history_entry always stamps "now"; tests need controlled hours to
    # exercise the hour-ranking logic, so adjust the stored entry directly.
    ts = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
    store._history[entry["id"]]["timestamp"] = ts.isoformat()


# ---- historical wait estimates in /recommend ----


def test_estimate_uses_historical_pace_over_advertised_duration(client, store):
    # Advertises 10 min/person, but history says ~30 min/person.
    service = make_service(store, name="Slow Reality", duration=10)
    token, user = register_and_login(client, "hist1@example.com")

    for _ in range(3):
        seed_served(store, user["id"], service["id"], wait=30, position=1)

    resp = client.post(
        "/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token)
    )
    assert resp.status_code == 201

    resp = client.get(
        f"/api/smart/recommend?service_id={service['id']}", headers=auth_header(token)
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["estimate_basis"] == "historical"
    # 1 person in queue × 30 min/person learned pace, not × 10 advertised.
    assert body["estimated_wait_minutes"] == 30.0


def test_estimate_falls_back_to_live_without_enough_history(client, store):
    service = make_service(store, name="New Desk", duration=10)
    token, user = register_and_login(client, "hist2@example.com")

    # Only 2 served entries — below MIN_SERVED_SAMPLES.
    for _ in range(2):
        seed_served(store, user["id"], service["id"], wait=30, position=1)

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get(
        f"/api/smart/recommend?service_id={service['id']}", headers=auth_header(token)
    )
    body = resp.get_json()
    assert body["estimate_basis"] == "live"
    assert body["estimated_wait_minutes"] == 10  # 1 in queue × advertised 10


def test_pace_normalizes_by_join_position(client, store):
    service = make_service(store, name="Normalized", duration=5)
    token, user = register_and_login(client, "hist3@example.com")

    # Three visits, all implying 10 min/person: 10@1st, 20@2nd, 30@3rd.
    seed_served(store, user["id"], service["id"], wait=10, position=1)
    seed_served(store, user["id"], service["id"], wait=20, position=2)
    seed_served(store, user["id"], service["id"], wait=30, position=3)

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get(
        f"/api/smart/recommend?service_id={service['id']}", headers=auth_header(token)
    )
    body = resp.get_json()
    assert body["estimate_basis"] == "historical"
    assert body["estimated_wait_minutes"] == 10.0


def test_recommendation_ranks_by_historical_estimates(client, store):
    # "Fast" advertises 5 but history proves 25/person; "Honest" advertises 20
    # and history agrees. Live math would prefer Fast; history knows better.
    fast = make_service(store, name="Fast On Paper", duration=5)
    honest = make_service(store, name="Honest", duration=20)
    token, user = register_and_login(client, "hist4@example.com")

    for _ in range(3):
        seed_served(store, user["id"], fast["id"], wait=25, position=1)
        seed_served(store, user["id"], honest["id"], wait=20, position=1)

    # One person waiting in each queue.
    for email, svc in (("qa@example.com", fast), ("qb@example.com", honest)):
        t, _ = register_and_login(client, email)
        client.post("/api/queues/join", json={"service_id": svc["id"]}, headers=auth_header(t))

    resp = client.get(
        f"/api/smart/recommend?service_id={fast['id']}", headers=auth_header(token)
    )
    body = resp.get_json()
    assert body["estimated_wait_minutes"] == 25.0
    assert body["recommendation"]["service_id"] == honest["id"]
    assert body["recommendation"]["estimated_wait_minutes"] == 20.0
    assert body["recommendation"]["estimate_basis"] == "historical"


# ---- /best-time ----


def test_best_time_requires_service_id(client, store):
    token, _ = register_and_login(client, "bt1@example.com")
    resp = client.get("/api/smart/best-time", headers=auth_header(token))
    assert resp.status_code == 400


def test_best_time_unknown_service(client, store):
    token, _ = register_and_login(client, "bt2@example.com")
    resp = client.get("/api/smart/best-time?service_id=nope", headers=auth_header(token))
    assert resp.status_code == 404


def test_best_time_empty_history(client, store):
    service = make_service(store, name="Fresh")
    token, _ = register_and_login(client, "bt3@example.com")
    resp = client.get(
        f"/api/smart/best-time?service_id={service['id']}", headers=auth_header(token)
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["quietest_hours"] == []
    assert body["busiest_hours"] == []


def test_best_time_ranks_quiet_and_busy_hours(client, store):
    service = make_service(store, name="Clinic")
    token, user = register_and_login(client, "bt4@example.com")

    # 5 joins at 2pm, 2 at 10am, 1 at 8am.
    for _ in range(5):
        seed_join_at_hour(store, user["id"], service["id"], hour=14)
    for _ in range(2):
        seed_join_at_hour(store, user["id"], service["id"], hour=10)
    seed_join_at_hour(store, user["id"], service["id"], hour=8)

    resp = client.get(
        f"/api/smart/best-time?service_id={service['id']}", headers=auth_header(token)
    )
    body = resp.get_json()
    assert body["quietest_hours"][0] == {"hour": 8, "joins": 1}
    assert body["busiest_hours"][0] == {"hour": 14, "joins": 5}
    assert "8am" in body["explanation"]
    assert "2pm" in body["explanation"]


def test_best_time_only_counts_joins_for_that_service(client, store):
    clinic = make_service(store, name="Clinic2")
    other = make_service(store, name="Other")
    token, user = register_and_login(client, "bt5@example.com")

    seed_join_at_hour(store, user["id"], clinic["id"], hour=9)
    for _ in range(4):
        seed_join_at_hour(store, user["id"], other["id"], hour=9)

    resp = client.get(
        f"/api/smart/best-time?service_id={clinic['id']}", headers=auth_header(token)
    )
    body = resp.get_json()
    assert body["busiest_hours"][0]["joins"] == 1