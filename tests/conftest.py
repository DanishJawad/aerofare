import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app  # importing app registers every model on Base.metadata

TEST_URL = "mysql+pymysql://root:root@localhost:3306/aerofare_test"

engine = create_engine(TEST_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def fresh_schema():
    """Drop and recreate every table before each test so tests don't leak
    into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


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
