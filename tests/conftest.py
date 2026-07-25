import ensure_deps

ensure_deps.ensure()

import pytest

from app import create_app
from app.store import InMemoryStore
from app.utils import ADMINISTRATOR, USER


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def client(store):
    app = create_app(store=store)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register_and_login(client, email, password="password123", role=USER):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    body = resp.get_json()
    return body["token"], body["user"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
