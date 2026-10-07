import os
import re
from urllib.parse import urlparse

# Must run before any `app` import: the app reads REDIS_URL once, when
# app.database loads. Environment variables beat the .env file, so this points
# the whole app (not just the tests) at a separate Redis database, and the
# per-test flush below can never touch the one the dev server uses (db 0).
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")
os.environ["REDIS_URL"] = TEST_REDIS_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import URL, create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402 - importing app registers every model on Base.metadata
from app.redis_client import redis_client  # noqa: E402

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/aerofare_test"
)

engine = create_engine(TEST_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine)

# These tests drop every table and flush Redis. Refuse to run at all if either
# target doesn't look like a throwaway one, rather than trust that nobody ever
# mis-sets an environment variable.
if not (engine.url.database or "").endswith("_test"):
    raise RuntimeError(f"Refusing to run: test database must end in '_test', got {engine.url.database!r}")
if urlparse(TEST_REDIS_URL).path in ("", "/", "/0"):
    raise RuntimeError("Refusing to run: Redis db 0 is the dev server's database; use /1 or higher")


def _create_test_database_if_missing() -> None:
    """A fresh MySQL (a new teammate's machine, a CI container) has no
    aerofare_test yet, and create_all can't create the database itself. The
    name already passed the '_test' check above, and is restricted to plain
    identifier characters before it goes into the statement."""
    name = engine.url.database
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise RuntimeError(f"Unexpected characters in test database name {name!r}")
    # URL.set(database=None) would mean "leave it unchanged", not "remove it",
    # so the database-less URL has to be built from scratch.
    url = engine.url
    server_url = URL.create(
        url.drivername, url.username, url.password, url.host, url.port, database=None, query=url.query
    )
    server_only = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with server_only.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}`"))
    server_only.dispose()


_create_test_database_if_missing()


@pytest.fixture(autouse=True)
def fresh_schema():
    """Drop and recreate every table before each test so tests don't leak
    into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def fresh_redis():
    """The token blacklist lives in Redis, so it needs the same per-test reset
    as the tables: a revoked token from one test must not exist in the next."""
    redis_client.flushdb()
    yield


@pytest.fixture(autouse=True)
def mail_outbox(monkeypatch):
    """Run Celery tasks inline and catch outgoing email, for every test.

    Without this, a booking test would push a task onto the Redis broker and
    nothing would run it, and the task would read the dev database instead of
    the test one. Returns the list of (to, subject, body) that would have been
    sent."""
    from app.notifications import tasks
    from app.worker import celery_app

    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(tasks, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tasks, "send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


@pytest.fixture
def client():
    """A TestClient whose get_db points at the test database instead of the
    real one. dependency_overrides swaps a dependency without touching app
    code."""

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _signup_and_login(client: TestClient, email: str, password: str = "password123") -> dict:
    client.post(
        "/users/signup",
        json={
            "name": "Test User",
            "email": email,
            "password": password,
            "phone_number": None,
            "city": "Lahore",
            "country": "PK",
        },
    )
    r = client.post("/users/login", data={"username": email, "password": password})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def login_as(client):
    """Factory fixture: call it in a test to create + log in an extra user.
        headers = login_as("someone@example.com")
    """

    def _login_as(email: str, password: str = "password123") -> dict:
        return _signup_and_login(client, email, password)

    return _login_as


@pytest.fixture
def auth_headers(client) -> dict:
    return _signup_and_login(client, email="user@example.com")


@pytest.fixture
def admin_headers(client) -> dict:
    from sqlalchemy import update

    from app.authentication.models import User

    headers = _signup_and_login(client, email="admin@example.com")
    db = TestingSessionLocal()
    db.execute(update(User).where(User.email == "admin@example.com").values(is_admin=True))
    db.commit()
    db.close()
    return headers


@pytest.fixture
def flight_id(client, admin_headers) -> int:
    """A future flight with 10 seats owned by no particular test. Returns its id."""
    ap1 = client.post(
        "/airports",
        json={"name": "Allama Iqbal Intl", "city": "Lahore", "country": "PK"},
        headers=admin_headers,
    ).json()["id"]
    ap2 = client.post(
        "/airports",
        json={"name": "Jinnah Intl", "city": "Karachi", "country": "PK"},
        headers=admin_headers,
    ).json()["id"]
    r = client.post(
        "/flights",
        json={
            "airline_name": "PIA",
            "departure_airport": ap1,
            "arrival_airport": ap2,
            "start_time": "2030-01-01T08:00:00+00:00",
            "end_time": "2030-01-01T10:00:00+00:00",
            "price": "150.00",
            "total_seats": 10,
            "available_seats": 10,
            "flight_class": "economy",
        },
        headers=admin_headers,
    )
    return r.json()["id"]
