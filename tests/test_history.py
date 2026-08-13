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


# ---- reporting module: /report and /report.csv ----


def test_report_requires_admin(client, store):
    token, _ = register_and_login(client, "rep1@example.com")
    resp = client.get("/api/history/report", headers=auth_header(token))
    assert resp.status_code == 403


def test_report_csv_requires_admin(client, store):
    token, _ = register_and_login(client, "rep2@example.com")
    resp = client.get("/api/history/report.csv", headers=auth_header(token))
    assert resp.status_code == 403


def test_report_includes_summary_services_and_users(client, store):
    service = make_service(store, name="Advising", duration=20)
    token, user = register_and_login(client, "rep3@example.com")
    admin_token, _ = register_and_login(client, "admin3@example.com", role=ADMINISTRATOR)

    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))
    client.post(
        "/api/queues/serve-next", json={"service_id": service["id"]}, headers=auth_header(admin_token)
    )

    resp = client.get("/api/history/report", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["summary"]["total_entries"] == 2
    assert body["summary"]["by_action"]["joined"] == 1
    assert body["summary"]["by_action"]["served"] == 1
    assert body["summary"]["average_wait_time_minutes"] == 20.0

    assert len(body["services"]) == 1
    svc_row = body["services"][0]
    assert svc_row["service_name"] == "Advising"
    assert svc_row["total_entries"] == 2
    assert svc_row["by_action"]["joined"] == 1
    assert svc_row["by_action"]["served"] == 1
    assert svc_row["average_wait_time_minutes"] == 20.0

    assert len(body["users"]) == 1
    user_row = body["users"][0]
    assert user_row["user_id"] == user["id"]
    assert user_row["email"] == user["email"]
    assert user_row["total_entries"] == 2
    assert len(user_row["entries"]) == 2

    assert body["filters"]["service_id"] is None
    assert "generated_at" in body


def test_report_filters_by_service(client, store):
    service_a = make_service(store, name="A")
    service_b = make_service(store, name="B")
    token, _ = register_and_login(client, "rep4@example.com")
    admin_token, _ = register_and_login(client, "admin4@example.com", role=ADMINISTRATOR)

    client.post("/api/queues/join", json={"service_id": service_a["id"]}, headers=auth_header(token))
    client.post("/api/queues/join", json={"service_id": service_b["id"]}, headers=auth_header(token))

    resp = client.get(
        f"/api/history/report?service_id={service_a['id']}", headers=auth_header(admin_token)
    )
    body = resp.get_json()
    assert body["summary"]["total_entries"] == 1
    assert len(body["services"]) == 1
    assert body["services"][0]["service_name"] == "A"


def test_report_filters_by_date_range_excludes_out_of_range(client, store):
    service = make_service(store)
    token, _ = register_and_login(client, "rep5@example.com")
    admin_token, _ = register_and_login(client, "admin5@example.com", role=ADMINISTRATOR)
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    # A window that can't contain "now" should exclude the entry just created.
    resp = client.get(
        "/api/history/report?start_date=2000-01-01&end_date=2000-01-02",
        headers=auth_header(admin_token),
    )
    assert resp.get_json()["summary"]["total_entries"] == 0

    resp = client.get("/api/history/report?start_date=2000-01-01", headers=auth_header(admin_token))
    assert resp.get_json()["summary"]["total_entries"] == 1


def test_report_rejects_invalid_date(client, store):
    admin_token, _ = register_and_login(client, "admin6@example.com", role=ADMINISTRATOR)
    resp = client.get("/api/history/report?start_date=not-a-date", headers=auth_header(admin_token))
    assert resp.status_code == 400


def test_report_csv_returns_downloadable_csv(client, store):
    service = make_service(store, name="Checkup")
    token, user = register_and_login(client, "rep6@example.com")
    admin_token, _ = register_and_login(client, "admin7@example.com", role=ADMINISTRATOR)
    client.post("/api/queues/join", json={"service_id": service["id"]}, headers=auth_header(token))

    resp = client.get("/api/history/report.csv", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers["Content-Disposition"]

    body = resp.get_data(as_text=True)
    lines = body.strip().splitlines()
    assert lines[0] == "timestamp,user_email,service_name,action,wait_time_minutes,position_at_join,notes"
    assert any(user["email"] in line and "Checkup" in line and "joined" in line for line in lines[1:])
