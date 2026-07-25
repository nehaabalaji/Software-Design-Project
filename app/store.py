# In-memory storage for Assignment 3 (no real database yet).
# Auth is implemented here. Other modules can add methods to this same store.

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

_PRIORITY_WEIGHT = {"low": 0, "medium": 1, "high": 2, "urgent": 3}


class InMemoryStore:
    def __init__(self):
        self._lock = Lock()
        self._users = {}
        self._users_by_email = {}
        self._tokens = {}
        self._services = {}
        self._history = {}
        self._queue_entries = {}
        # teammates can add more dicts here later, for example:
        # self._notifications = {}


    def create_user(self, *, email, password_hash, role, first_name="", last_name=""):
        with self._lock:
            email = email.strip().lower()
            if email in self._users_by_email:
                raise ValueError("Email is already registered")

            user_id = str(uuid4())
            user = {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "role": role,
                "first_name": (first_name or "").strip(),
                "last_name": (last_name or "").strip(),
            }
            self._users[user_id] = user
            self._users_by_email[email] = user_id
            return self._public_user(user)

    def get_user_by_email(self, email):
        with self._lock:
            user_id = self._users_by_email.get(email.strip().lower())
            if not user_id:
                return None
            return dict(self._users[user_id])

    def get_user_by_id(self, user_id):
        with self._lock:
            user = self._users.get(user_id)
            return dict(user) if user else None

    def create_token(self, user_id):
        with self._lock:
            token = str(uuid4())
            self._tokens[token] = user_id
            return token

    def get_user_id_for_token(self, token):
        with self._lock:
            return self._tokens.get(token)

    def revoke_token(self, token):
        with self._lock:
            return self._tokens.pop(token, None) is not None

    def clear(self):
        with self._lock:
            self._users.clear()
            self._users_by_email.clear()
            self._tokens.clear()
            self._history.clear()
            self._services.clear()
            self._queue_entries.clear()

    # ------------------------------------------------------------------
    # Services (added for the Service Management Module)
    # ------------------------------------------------------------------

    def create_service(self, *, name, description, duration, priority):
        with self._lock:
            service_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()
            service = {
                "id": service_id,
                "name": name,
                "description": description,
                "duration": duration,
                "priority": priority,
                "created_at": now,
                "updated_at": now,
            }
            self._services[service_id] = service
            self._queue_entries[service_id] = []
            return dict(service)

    def list_services(self):
        with self._lock:
            return [dict(s) for s in self._services.values()]

    def get_service(self, service_id):
        with self._lock:
            service = self._services.get(service_id)
            return dict(service) if service else None

    def service_name_exists(self, name, exclude_id=None):
        with self._lock:
            target = name.strip().lower()
            return any(
                s["id"] != exclude_id and s["name"].strip().lower() == target
                for s in self._services.values()
            )

    def update_service(self, service_id, **fields):
        with self._lock:
            service = self._services.get(service_id)
            if not service:
                return None
            service.update(fields)
            service["updated_at"] = datetime.now(timezone.utc).isoformat()
            return dict(service)

    def delete_service(self, service_id):
        with self._lock:
            if service_id not in self._services:
                return False
            del self._services[service_id]
            self._queue_entries.pop(service_id, None)
            return True

    def get_queue_length(self, service_id):
        """Used by services.py to block deleting a service with people waiting.
        The Queue module is what actually appends/removes entries here."""
        with self._lock:
            return len(self._queue_entries.get(service_id, []))

    # ------------------------------------------------------------------
    # Queue entries (added for the Queue Management Module)
    # ------------------------------------------------------------------

    def join_queue(self, *, user_id, service_id):
        with self._lock:
            service = self._services.get(service_id)
            if not service:
                raise ValueError("Service not found")

            entries = self._queue_entries.setdefault(service_id, [])
            if any(e["user_id"] == user_id and e["status"] == "waiting" for e in entries):
                raise ValueError("Already in this queue")

            entry = {
                "id": str(uuid4()),
                "user_id": user_id,
                "service_id": service_id,
                "priority": service["priority"],
                "status": "waiting",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }
            entries.append(entry)
            position = self._position_locked(service_id, entry["id"])
            return dict(entry), position

    def leave_queue(self, *, user_id, service_id):
        with self._lock:
            entries = self._queue_entries.get(service_id, [])
            for i, entry in enumerate(entries):
                if entry["user_id"] == user_id and entry["status"] == "waiting":
                    return entries.pop(i)
            return None

    def list_queue(self, service_id):
        with self._lock:
            return self._sorted_entries_locked(service_id)

    def get_queue_position(self, *, user_id, service_id):
        with self._lock:
            entries = self._sorted_entries_locked(service_id)
            for i, entry in enumerate(entries):
                if entry["user_id"] == user_id:
                    return i + 1, entry
            return None, None

    def list_queue_entries_for_user(self, user_id):
        with self._lock:
            results = []
            for service_id in self._queue_entries:
                service = self._services.get(service_id)
                duration = service["duration"] if service else 0
                ordered = self._sorted_entries_locked(service_id)
                for i, entry in enumerate(ordered):
                    if entry["user_id"] == user_id and entry["status"] == "waiting":
                        entry["service_name"] = service["name"] if service else None
                        entry["position"] = i + 1
                        entry["estimated_wait_minutes"] = (i + 1) * duration
                        results.append(entry)
            return results

    def serve_next(self, service_id):
        with self._lock:
            entries = self._queue_entries.get(service_id)
            if not entries:
                return None
            ordered = sorted(
                entries,
                key=lambda e: (-_PRIORITY_WEIGHT.get(e["priority"], 0), e["joined_at"]),
            )
            next_entry = ordered[0]
            entries.remove(next_entry)
            next_entry["status"] = "served"
            return dict(next_entry)

    def _sorted_entries_locked(self, service_id):
        """Caller must already hold self._lock."""
        entries = self._queue_entries.get(service_id, [])
        ordered = sorted(
            entries,
            key=lambda e: (-_PRIORITY_WEIGHT.get(e["priority"], 0), e["joined_at"]),
        )
        return [dict(e) for e in ordered]

    def _position_locked(self, service_id, entry_id):
        """Caller must already hold self._lock."""
        for i, entry in enumerate(self._sorted_entries_locked(service_id)):
            if entry["id"] == entry_id:
                return i + 1
        return None

    # ------------------------------------------------------------------
    # History (added for the History Module)
    # ------------------------------------------------------------------

    def add_history_entry(self, *, user_id, service_id, action,
                           wait_time_minutes=None, position_at_join=None, notes=None):
        with self._lock:
            user = self._users.get(user_id)
            service = self._services.get(service_id)
            entry_id = str(uuid4())
            entry = {
                "id": entry_id,
                "user_id": user_id,
                "user_email": user["email"] if user else None,
                "service_id": service_id,
                "service_name": service["name"] if service else None,
                "action": action,
                "wait_time_minutes": wait_time_minutes,
                "position_at_join": position_at_join,
                "notes": notes,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._history[entry_id] = entry
            return dict(entry)

    def list_history(self):
        with self._lock:
            return [dict(e) for e in self._history.values()]


    @staticmethod
    def _public_user(user):
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        }

    