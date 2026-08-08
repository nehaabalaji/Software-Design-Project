<<<<<<< Updated upstream
import pytest

from app.notifications import (
    ALMOST_READY,
    ALMOST_READY_POSITION,
    JOINED,
    is_almost_ready,
    notify_almost_ready,
    notify_joined,
)
from app.store import InMemoryStore
from app.utils import ADMINISTRATOR, USER
from tests.conftest import auth_header, register_and_login


# ---- endpoint: list ----


def test_list_empty_when_no_notifications(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.get("/api/notifications/", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["notifications"] == []
    assert body["count"] == 0
    assert body["unread_count"] == 0


def test_list_requires_login(client):
    assert client.get("/api/notifications/").status_code == 401


def test_list_returns_users_notifications(client, store):
    token, user = register_and_login(client, "u@example.com")
    store.add_notification(user_id=user["id"], kind=JOINED, message="hello")
    store.add_notification(user_id=user["id"], kind=ALMOST_READY, message="soon")

    resp = client.get("/api/notifications/", headers=auth_header(token))
    body = resp.get_json()
    assert body["count"] == 2
    assert body["unread_count"] == 2


def test_list_only_shows_own_notifications(client, store):
    token_a, user_a = register_and_login(client, "a@example.com")
    _, user_b = register_and_login(client, "b@example.com")
    store.add_notification(user_id=user_a["id"], kind=JOINED, message="for A")
    store.add_notification(user_id=user_b["id"], kind=JOINED, message="for B")

    resp = client.get("/api/notifications/", headers=auth_header(token_a))
    body = resp.get_json()
    assert body["count"] == 1
    assert body["notifications"][0]["message"] == "for A"


def test_list_newest_first(client, store):
    token, user = register_and_login(client, "u@example.com")
    store.add_notification(user_id=user["id"], kind=JOINED, message="first")
    store.add_notification(user_id=user["id"], kind=ALMOST_READY, message="second")

    resp = client.get("/api/notifications/", headers=auth_header(token))
    messages = [n["message"] for n in resp.get_json()["notifications"]]
    assert messages[0] == "second"


def test_unread_filter(client, store):
    token, user = register_and_login(client, "u@example.com")
    n1 = store.add_notification(user_id=user["id"], kind=JOINED, message="one")
    store.add_notification(user_id=user["id"], kind=JOINED, message="two")
    store.mark_notification_read(n1["id"], user["id"])

    resp = client.get("/api/notifications/?unread=true", headers=auth_header(token))
    body = resp.get_json()
    assert body["count"] == 1
    assert body["notifications"][0]["message"] == "two"
    assert body["unread_count"] == 1


# ---- endpoint: mark one read ----


def test_mark_read(client, store):
    token, user = register_and_login(client, "u@example.com")
    n = store.add_notification(user_id=user["id"], kind=JOINED, message="hi")

    resp = client.post(f"/api/notifications/{n['id']}/read", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["notification"]["read"] is True


def test_mark_read_missing_returns_404(client):
    token, _ = register_and_login(client, "u@example.com")
    assert client.post("/api/notifications/nope/read", headers=auth_header(token)).status_code == 404


def test_cannot_mark_someone_elses_read(client, store):
    token_a, _ = register_and_login(client, "a@example.com")
    _, user_b = register_and_login(client, "b@example.com")
    n = store.add_notification(user_id=user_b["id"], kind=JOINED, message="for B")

    # A tries to mark B's notification -- treated as not found, not modified
    resp = client.post(f"/api/notifications/{n['id']}/read", headers=auth_header(token_a))
    assert resp.status_code == 404
    assert store.get_notification(n["id"])["read"] is False


def test_mark_read_requires_login(client):
    assert client.post("/api/notifications/anything/read").status_code == 401


# ---- endpoint: mark all read ----


def test_mark_all_read(client, store):
    token, user = register_and_login(client, "u@example.com")
    store.add_notification(user_id=user["id"], kind=JOINED, message="one")
    store.add_notification(user_id=user["id"], kind=JOINED, message="two")

    resp = client.post("/api/notifications/read-all", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["updated"] == 2

    after = client.get("/api/notifications/", headers=auth_header(token)).get_json()
    assert after["unread_count"] == 0


def test_mark_all_read_only_affects_caller(client, store):
    token_a, user_a = register_and_login(client, "a@example.com")
    _, user_b = register_and_login(client, "b@example.com")
    store.add_notification(user_id=user_a["id"], kind=JOINED, message="A")
    n_b = store.add_notification(user_id=user_b["id"], kind=JOINED, message="B")

    client.post("/api/notifications/read-all", headers=auth_header(token_a))
    assert store.get_notification(n_b["id"])["read"] is False


def test_mark_all_read_with_none_returns_zero(client):
    token, _ = register_and_login(client, "u@example.com")
    resp = client.post("/api/notifications/read-all", headers=auth_header(token))
    assert resp.get_json()["updated"] == 0


# ---- store methods directly ----


def test_add_notification_captures_service_name():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    service = store.create_service(name="Passport", description="d", duration=15, priority="high")

    n = store.add_notification(user_id=user["id"], service_id=service["id"], kind=JOINED, message="m")
    assert n["service_name"] == "Passport"
    assert n["read"] is False


def test_add_notification_without_service():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    n = store.add_notification(user_id=user["id"], kind=JOINED, message="m")
    assert n["service_id"] is None
    assert n["service_name"] is None


# ---- queue-facing helpers ----


def test_notify_joined_writes_notification():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    service = store.create_service(name="Passport", description="d", duration=15, priority="high")

    n = notify_joined(store, user_id=user["id"], service_id=service["id"], position=3)
    assert n["kind"] == JOINED
    assert "position 3" in n["message"]
    assert store.list_notifications(user["id"])[0]["id"] == n["id"]


def test_notify_almost_ready_messages():
    store = InMemoryStore()
    user = store.create_user(email="u@x.com", password_hash="h", role=USER)
    service = store.create_service(name="Passport", description="d", duration=15, priority="high")

    next_up = notify_almost_ready(store, user_id=user["id"], service_id=service["id"], position=1)
    assert "next" in next_up["message"].lower()

    one_ahead = notify_almost_ready(store, user_id=user["id"], service_id=service["id"], position=2)
    assert "1 person ahead" in one_ahead["message"]

    several = notify_almost_ready(store, user_id=user["id"], service_id=service["id"], position=4)
    assert "3 people ahead" in several["message"]


def test_is_almost_ready_threshold():
    assert is_almost_ready(1) is True
    assert is_almost_ready(ALMOST_READY_POSITION) is True
    assert is_almost_ready(ALMOST_READY_POSITION + 1) is False


def test_is_almost_ready_rejects_bad_input():
    with pytest.raises(ValueError):
        is_almost_ready(0)
    with pytest.raises(ValueError):
        is_almost_ready("2")
    with pytest.raises(ValueError):
        is_almost_ready(True)
=======
from tests.conftest import auth_header, register_and_login


def make_service(store, name="Checkup", duration=10, priority="medium"):
    return store.create_service(
        name=name, description="desc", duration=duration, priority=priority
    )


def test_notifications_require_login(client, store):
    resp = client.get("/api/notifications/")
    assert resp.status_code == 401


def test_list_notifications_after_join(client, store):
    service = make_service(store)
    token, user = register_and_login(client, "note1@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get("/api/notifications/", headers=auth_header(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] >= 1
    assert all(n["status"] == "sent" for n in body["notifications"])


def test_mark_notification_read(client, store):
    service = make_service(store)
    token, user = register_and_login(client, "note2@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    notification_id = store.list_notifications(user["id"])[0]["id"]
    resp = client.post(f"/api/notifications/{notification_id}/read", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["notification"]["status"] == "viewed"


def test_mark_notification_read_requires_login(client, store):
    resp = client.post("/api/notifications/some-id/read")
    assert resp.status_code == 401


def test_mark_notification_read_not_found(client, store):
    token, _ = register_and_login(client, "note3@example.com")
    resp = client.post("/api/notifications/does-not-exist/read", headers=auth_header(token))
    assert resp.status_code == 404


def test_cannot_mark_another_users_notification_read(client, store):
    service = make_service(store)
    token1, user1 = register_and_login(client, "note4@example.com")
    token2, _ = register_and_login(client, "note5@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token1))

    notification_id = store.list_notifications(user1["id"])[0]["id"]
    resp = client.post(f"/api/notifications/{notification_id}/read", headers=auth_header(token2))
    assert resp.status_code == 404


def test_mark_all_notifications_read(client, store):
    service = make_service(store)
    token, user = register_and_login(client, "note6@example.com")
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.post("/api/notifications/read-all", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["updated"] >= 1

    notifications = store.list_notifications(user["id"])
    assert all(n["status"] == "viewed" for n in notifications)


def test_mark_all_notifications_read_requires_login(client, store):
    resp = client.post("/api/notifications/read-all")
    assert resp.status_code == 401
>>>>>>> Stashed changes
