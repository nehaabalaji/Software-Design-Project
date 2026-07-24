# QueueSmart - Assignment 3 Backend (Authentication)

Team: Vasavi Chenna, Nehaa Balaji, Samuel Parsons, Mahmoud Masoud

Python/Flask backend. No real database — data stays in memory while the server runs.

## Done in this repo (Authentication Module)

- User registration
- Login / logout
- Roles: User and Administrator
- Basic input validation (email + password)

## Left open for the rest of the team

These files are stubs with notes so other modules can plug in easily:

- `app/services.py` — create/update/list services
- `app/queues.py` — join/leave queue, serve next, wait-time estimation
- `app/notifications.py` — join / almost-ready notifications
- `app/history.py` — participation history

To wire a new module in, import its blueprint in `app/__init__.py` and register it
(same pattern as auth). You can also reuse `login_required` and `admin_required`
from `app/utils.py`, and add data onto `InMemoryStore` in `app/store.py`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

API runs at http://127.0.0.1:5000

## Tests

```bash
pytest -v
```

## Auth endpoints

- POST `/api/auth/register`
- POST `/api/auth/login`
- GET  `/api/auth/me`
- POST `/api/auth/logout`

Register body example:
```json
{
  "email": "user@test.com",
  "password": "password123",
  "role": "User"
}
```

`role` is optional (defaults to User). Allowed: `User`, `Administrator`.
Password must be at least 8 characters.

Login returns a `token`. For protected routes:
`Authorization: Bearer <token>`
