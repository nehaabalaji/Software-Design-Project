# In-memory storage for Assignment 3 (no real database yet).
# Auth is implemented here. Other modules can add methods to this same store.

from threading import Lock
from uuid import uuid4


class InMemoryStore:
    def __init__(self):
        self._lock = Lock()
        self._users = {}
        self._users_by_email = {}
        self._tokens = {}
        self._services = {}
        self._services_by_name = {}
        # teammates can add more dicts here later, for example:
        # self._services = {}
        # self._queue_entries = {}
        # self._notifications = {}
        # self._history = {}

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

    # ---- Service Management (Samuel) ----

    def create_service(self, *, name, description, expected_duration, priority):
        with self._lock:
            key = name.strip().lower()
            if key in self._services_by_name:
                raise ValueError("A service with that name already exists")

            service_id = str(uuid4())
            service = {
                "id": service_id,
                "name": name.strip(),
                "description": description.strip(),
                "expected_duration": expected_duration,
                "priority": priority,
                "is_open": True,
            }
            self._services[service_id] = service
            self._services_by_name[key] = service_id
            return dict(service)

    def get_service(self, service_id):
        with self._lock:
            service = self._services.get(service_id)
            return dict(service) if service else None

    def list_services(self):
        with self._lock:
            return [dict(s) for s in self._services.values()]

    def update_service(self, service_id, **fields):
        with self._lock:
            service = self._services.get(service_id)
            if service is None:
                return None

            new_name = fields.get("name")
            if new_name is not None:
                key = new_name.strip().lower()
                existing = self._services_by_name.get(key)
                if existing is not None and existing != service_id:
                    raise ValueError("A service with that name already exists")
                self._services_by_name.pop(service["name"].strip().lower(), None)
                self._services_by_name[key] = service_id

            service.update(fields)
            return dict(service)

    def delete_service(self, service_id):
        with self._lock:
            service = self._services.pop(service_id, None)
            if service is None:
                return False
            self._services_by_name.pop(service["name"].strip().lower(), None)
            return True

    def clear(self):
        with self._lock:
            self._users.clear()
            self._users_by_email.clear()
            self._tokens.clear()
            self._services.clear()
            self._services_by_name.clear()

    @staticmethod
    def _public_user(user):
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        }
