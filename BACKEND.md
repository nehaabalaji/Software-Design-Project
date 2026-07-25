# Backend Guide — Services, Queues & History

Covers the three working backend modules: **Service Management**, **Queue Management**,
and **History**. Auth is documented in `README.md`; `app/notifications.py` is still an
unimplemented stub.

---

## 1. Setup

```bash
chmod +x setup.sh
./setup.sh
source .venv/bin/activate
python run.py
```

API runs at `http://127.0.0.1:5000`. Health check: `GET /api/health`.

> **macOS note:** port 5000 is often taken by AirPlay Receiver
> (System Settings → General → AirDrop & Handoff → turn it off), or run
> `app.run(port=5001)` temporarily.

Data lives in memory only — restarting the server (or the Flask debug
auto-reloader picking up a file save) wipes all users/services/queues/history.

---

## 2. How it fits together

```
app/__init__.py     creates the Flask app, holds the shared InMemoryStore,
                     registers each module's blueprint under /api/<name>

app/store.py         InMemoryStore — the single source of truth.
                      Every module reads/writes through this, never through
                      its own state. All mutations go through self._lock.

app/utils.py          login_required / admin_required decorators.
                       They call the wrapped view as fn(user, *args, **kwargs) —
                       the current user dict is always the view's first argument.

app/services.py  -->  /api/services   admin manages services (name, duration, priority)
app/queues.py    -->  /api/queues     users join/leave; admin monitors + serves
app/history.py   -->  /api/history    read-only log of what queues.py recorded
```

Each request pulls the store off the app, not a global:

```python
store = current_app.config["STORE"]
```

This is what makes `tests/conftest.py`'s `client` fixture work — every test
gets a fresh `InMemoryStore()`, so tests never leak state into each other.

### Data model (all IDs are UUID strings, not ints)

| Entity | Created by | Key fields |
|---|---|---|
| `service` | `store.create_service()` | `id, name, description, duration, priority` |
| `queue entry` | `store.join_queue()` | `id, user_id, service_id, priority, status, joined_at` |
| `history entry` | `store.add_history_entry()` | `id, user_id, service_id, action, wait_time_minutes, position_at_join, timestamp` |

### Queue ordering & wait-time estimate

- Each service's queue is sorted by **priority weight, then arrival time**
  (`_PRIORITY_WEIGHT` in `store.py`: low=0 … urgent=3).
- Priority lives on the **service**, not the individual entry — so within one
  service's queue, everyone shares the same priority and ordering reduces to
  plain FIFO. This matters if a cross-service "serve the most urgent service
  first" view gets added later.
- Estimated wait = `position * service.duration` (position is 1-indexed).

### Request flow example — joining a queue

1. `POST /api/queues/join` with `{"service_id": ...}` and a bearer token.
2. `login_required` resolves the token → user dict, passed as the view's first arg.
3. `store.get_service()` confirms the service exists (404 if not).
4. `store.join_queue()` appends the entry and returns its computed position.
5. `store.add_history_entry(action="joined", ...)` logs it — this is the same
   call `history.py` reads back from later.
6. Response includes `position` and `estimated_wait_minutes`.

`leave` and `serve-next` (admin-only) follow the same shape: mutate via the
store, then log to history.

---

## 3. Testing

### Automated (run this after any change)

```bash
source .venv/bin/activate
pytest -v                 # everything
pytest -v tests/test_queues.py    # one module
```

Currently: **42 tests** across `test_auth.py`, `test_services.py`,
`test_queues.py`, `test_history.py`. Each test gets its own in-memory store
via the `store`/`client` fixtures in `tests/conftest.py`, so tests never see
each other's data — no cleanup step needed between them.

What's covered per module:
- **services** — CRUD, admin-only writes, validation errors, duplicate-name
  conflicts, delete blocked while a queue is non-empty
- **queues** — join/leave, position & wait-time math, per-service queue
  isolation, duplicate-join rejection, admin-only routes, serve-next ordering
- **history** — join/leave/serve get logged, `/mine` scoped to the caller,
  `/`, `/stats` admin-only, filtering by action

### Manual, against the running server

```bash
BASE=http://127.0.0.1:5000

# admin creates a service
TOKEN=$(curl -s -X POST $BASE/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -s -X POST $BASE/api/services/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Passport Renewal","description":"Renew a passport","duration":15,"priority":"high"}'

# a user joins its queue, then checks their own history
curl -s -X POST $BASE/api/queues/join -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" -d '{"service_id":"<id from above>"}'

curl -s $BASE/api/history/mine -H "Authorization: Bearer $USER_TOKEN"
```

Remember: every server restart (or debug-mode auto-reload after saving a
file) clears the store, so tokens and IDs from a previous session stop
working — register/login again.

---

## 4. Known gaps

- `app/notifications.py` is an unimplemented stub (no blueprint registered).
- No persistence — everything resets when the process restarts. Real DB is
  planned for Assignment 4.
- Frontend (`homescreen.html`, `admin.html`, etc.) is not yet wired to these
  live endpoints.
