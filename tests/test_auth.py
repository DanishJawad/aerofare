from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import update

from app.authentication.models import User
from app.authentication.security import create_access_token, decode_access_token
from app.database import settings
from app.redis_client import redis_client

from .conftest import TEST_REDIS_URL, TestingSessionLocal
from .test_errors import assert_envelope


def _token(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def _login(client, email: str, password: str = "password123") -> dict:
    r = client.post("/users/login", data={"username": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# -------------------------------------------------------------- logout / revocation


def test_a_logged_out_token_stops_working_immediately(client, auth_headers):
    """The reason Redis is in this project. Without the blacklist the token
    would stay valid until its 30 minutes ran out."""
    assert client.get("/users/me", headers=auth_headers).status_code == 200

    assert client.post("/users/logout", headers=auth_headers).status_code == 204

    r = client.get("/users/me", headers=auth_headers)
    assert_envelope(r, 401, "invalid_token")


def test_logout_stores_the_token_id_in_the_test_redis_with_an_expiry(client, auth_headers):
    """Also proves the suite really talks to the separate test database: the
    key must be visible through the client the app itself uses."""
    jti = decode_access_token(_token(auth_headers)).jti
    client.post("/users/logout", headers=auth_headers)

    assert redis_client.connection_pool.connection_kwargs["db"] == 1
    assert TEST_REDIS_URL.endswith("/1")
    ttl = redis_client.ttl(f"blacklist:{jti}")
    # SETEX gives the key exactly the token's remaining life, so Redis cleans
    # it up on its own. -1 would mean "never expires", -2 "doesn't exist".
    assert 0 < ttl <= settings.access_token_expiry_minutes * 60


def test_logging_out_one_session_leaves_the_users_other_session_alone(client, auth_headers):
    """Each login gets its own jti, so revoking one token is not a logout of
    the whole account."""
    other_session = _login(client, "user@example.com")

    client.post("/users/logout", headers=auth_headers)

    assert client.get("/users/me", headers=auth_headers).status_code == 401
    assert client.get("/users/me", headers=other_session).status_code == 200


# -------------------------------------------------------------- bad tokens


def test_an_expired_token_is_rejected(client, auth_headers):
    user_id = client.get("/users/me", headers=auth_headers).json()["id"]
    long_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = jwt.encode(
        {"sub": str(user_id), "iat": long_ago, "exp": long_ago + timedelta(minutes=30), "jti": "x"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    r = client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert_envelope(r, 401, "invalid_token")


def test_a_token_signed_with_the_wrong_key_is_rejected(client, auth_headers):
    user_id = client.get("/users/me", headers=auth_headers).json()["id"]
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=30), "jti": "x"},
        "not-the-real-secret-key-not-the-real-secret-key",
        algorithm=settings.algorithm,
    )

    r = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})
    assert_envelope(r, 401, "invalid_token")


def test_a_valid_token_for_a_user_that_no_longer_exists_is_rejected(client):
    ghost = create_access_token("999999", version=0)

    r = client.get("/users/me", headers={"Authorization": f"Bearer {ghost}"})
    assert_envelope(r, 401, "invalid_token")


# -------------------------------------------------------------- login


def test_wrong_password_and_unknown_email_look_identical(client, auth_headers):
    """If the two cases answered differently, anyone could use the login form
    to find out which emails have accounts."""
    wrong_password = client.post(
        "/users/login", data={"username": "user@example.com", "password": "nope-nope-nope"}
    )
    unknown_email = client.post(
        "/users/login", data={"username": "nobody@example.com", "password": "nope-nope-nope"}
    )

    a = assert_envelope(wrong_password, 401, "invalid_credentials")
    b = assert_envelope(unknown_email, 401, "invalid_credentials")
    assert a["message"] == b["message"]


def test_signing_up_twice_with_the_same_email_is_a_conflict(client, auth_headers):
    r = client.post(
        "/users/signup",
        json={
            "name": "Again",
            "email": "user@example.com",
            "password": "password123",
            "city": "Lahore",
            "country": "PK",
        },
    )
    assert_envelope(r, 409, "email_already_registered")


def test_changing_password_needs_the_current_one_and_the_new_one_then_works(client, auth_headers):
    wrong = client.post(
        "/users/me/password",
        json={"current_password": "not-my-password", "new_password": "brand-new-pass"},
        headers=auth_headers,
    )
    assert_envelope(wrong, 400, "incorrect_password")

    ok = client.post(
        "/users/me/password",
        json={"current_password": "password123", "new_password": "brand-new-pass"},
        headers=auth_headers,
    )
    assert ok.status_code == 200

    assert client.post(
        "/users/login", data={"username": "user@example.com", "password": "password123"}
    ).status_code == 401
    assert client.post(
        "/users/login", data={"username": "user@example.com", "password": "brand-new-pass"}
    ).status_code == 200


# -------------------------------------------------------------- roles


def _set_admin(email: str, value: bool) -> None:
    db = TestingSessionLocal()
    db.execute(update(User).where(User.email == email).values(is_admin=value))
    db.commit()
    db.close()


def test_admin_rights_are_checked_against_the_database_not_the_token(client, auth_headers):
    """is_admin is never put in the JWT. So the same token gains or loses admin
    access on the very next request, instead of keeping stale rights until it
    expires."""
    assert client.get("/users", headers=auth_headers).status_code == 403

    _set_admin("user@example.com", True)
    assert client.get("/users", headers=auth_headers).status_code == 200

    _set_admin("user@example.com", False)
    assert_envelope(client.get("/users", headers=auth_headers), 403, "admin_required")


def test_a_normal_user_cannot_create_or_edit_flights(client, auth_headers, flight_id):
    flight = client.get(f"/flights/{flight_id}").json()
    flight.pop("id")

    create = client.post("/flights", json=flight, headers=auth_headers)
    assert_envelope(create, 403, "admin_required")

    edit = client.patch(f"/flights/{flight_id}", json={"price": "1.00"}, headers=auth_headers)
    assert_envelope(edit, 403, "admin_required")

    assert client.get(f"/flights/{flight_id}").json()["price"] == flight["price"]
