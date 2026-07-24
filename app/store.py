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

    def clear(self):
        with self._lock:
            self._users.clear()
            self._users_by_email.clear()
            self._tokens.clear()

    @staticmethod
    def _public_user(user):
        return {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
        }
