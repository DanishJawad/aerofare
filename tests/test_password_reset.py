import hashlib
import re

from app.authentication.password_reset import RESET_TOKEN_TTL_SECONDS
from app.redis_client import redis_client

EMAIL = "user@example.com"
OLD = "password123"
NEW = "a-brand-new-password"


def _forgot(client, email=EMAIL):
    return client.post("/users/forgot-password", json={"email": email})


def _reset(client, token, password=NEW):
    return client.post("/users/reset-password", json={"token": token, "new_password": password})


def _login(client, password, email=EMAIL):
    return client.post("/users/login", data={"username": email, "password": password})


def _token_from(mail) -> str:
    return re.search(r"reset-password#token=([\w-]+)", mail.text).group(1)


def _request_token(client, mail_outbox) -> str:
    assert _forgot(client).status_code == 202
    return _token_from(mail_outbox[-1])


# ---------------------------------------------------------------- the happy path


def test_full_reset_flow(client, auth_headers, mail_outbox):
    r = _forgot(client)
    assert r.status_code == 202

    assert len(mail_outbox) == 1
    mail = mail_outbox[0]
    assert mail.to == EMAIL
    assert mail.subject == "Reset your Aerofare password"
    token = _token_from(mail)
    assert f"http://localhost:5173/reset-password#token={token}" in mail.html  # the button and the plain link

    assert _reset(client, token).status_code == 204
    assert _login(client, NEW).status_code == 200
    assert _login(client, OLD).status_code == 401


def test_the_link_puts_the_token_in_the_fragment_not_the_query_string(client, auth_headers, mail_outbox):
    _forgot(client)
    assert "reset-password?token" not in mail_outbox[0].text
    assert "reset-password#token=" in mail_outbox[0].text


# ---------------------------------------------------------------- no account enumeration


def test_unknown_email_gets_the_same_answer_and_no_email(client, auth_headers, mail_outbox):
    known = _forgot(client, EMAIL)
    unknown = _forgot(client, "nobody@example.com")

    assert (unknown.status_code, unknown.json()) == (known.status_code, known.json())
    assert [m.to for m in mail_outbox] == [EMAIL]


def test_the_email_lookup_ignores_case(client, auth_headers, mail_outbox):
    assert _forgot(client, "USER@Example.com").status_code == 202
    assert len(mail_outbox) == 1


# ---------------------------------------------------------------- token rules


def test_a_token_works_only_once(client, auth_headers, mail_outbox):
    token = _request_token(client, mail_outbox)

    assert _reset(client, token).status_code == 204
    again = _reset(client, token, "another-password-1")
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_reset_token"
    assert _login(client, NEW).status_code == 200  # the second attempt changed nothing


def test_an_unknown_token_is_rejected(client, auth_headers):
    r = _reset(client, "not-a-real-token")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_reset_token"


def test_a_rejected_new_password_does_not_use_up_the_token(client, auth_headers, mail_outbox):
    token = _request_token(client, mail_outbox)

    assert _reset(client, token, "short").status_code == 422
    assert _reset(client, token).status_code == 204


def test_the_token_expires_after_15_minutes(client, auth_headers, mail_outbox):
    token = _request_token(client, mail_outbox)

    ttl = redis_client.ttl("pwreset:" + hashlib.sha256(token.encode()).hexdigest())
    assert 0 < ttl <= RESET_TOKEN_TTL_SECONDS == 900


def test_redis_never_holds_the_raw_token(client, auth_headers, mail_outbox):
    token = _request_token(client, mail_outbox)

    for key in redis_client.keys("*"):
        assert token not in key
        value = redis_client.get(key) if redis_client.type(key) == "string" else ""
        assert token not in (value or "")


def test_a_token_for_a_deleted_account_is_rejected(client, auth_headers, mail_outbox):
    from sqlalchemy import delete

    from app.authentication.models import User

    from .conftest import TestingSessionLocal

    token = _request_token(client, mail_outbox)
    db = TestingSessionLocal()
    db.execute(delete(User).where(User.email == EMAIL))
    db.commit()
    db.close()

    assert _reset(client, token).status_code == 400


# ---------------------------------------------------------------- sessions end


def test_a_reset_ends_every_existing_login(client, auth_headers, mail_outbox):
    assert client.get("/users/me", headers=auth_headers).status_code == 200
    token = _request_token(client, mail_outbox)

    _reset(client, token)

    r = client.get("/users/me", headers=auth_headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"

    new_token = _login(client, NEW).json()["access_token"]
    assert client.get("/users/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200


def test_changing_the_password_ends_other_logins_but_not_this_one(client, auth_headers):
    other_device = _login(client, OLD).json()["access_token"]

    r = client.post(
        "/users/me/password",
        json={"current_password": OLD, "new_password": NEW},
        headers=auth_headers,
    )
    assert r.status_code == 200

    assert client.get("/users/me", headers=auth_headers).status_code == 401  # the token it was sent with
    assert client.get("/users/me", headers={"Authorization": f"Bearer {other_device}"}).status_code == 401
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/users/me", headers=fresh).status_code == 200


def test_tokens_issued_before_versioning_still_work(client, auth_headers):
    """A token with no `ver` claim (issued before this feature existed) counts as version 0."""
    import jwt

    from app.database import settings

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    del claims["ver"]
    legacy = jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)

    assert client.get("/users/me", headers={"Authorization": f"Bearer {legacy}"}).status_code == 200


# ---------------------------------------------------------------- rate limiting


def test_the_fourth_request_for_one_address_in_a_window_is_refused(client, auth_headers, mail_outbox):
    for _ in range(3):
        assert _forgot(client).status_code == 202

    r = _forgot(client)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert 0 < int(r.headers["Retry-After"]) <= 900
    assert len(mail_outbox) == 3  # the refused one sent nothing


def test_the_limit_is_the_same_for_an_address_with_no_account(client, mail_outbox):
    codes = [_forgot(client, "nobody@example.com").status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]


def test_the_limit_is_per_address(client, auth_headers):
    for _ in range(3):
        _forgot(client)
    assert _forgot(client, "someone-else@example.com").status_code == 202


def test_one_ip_cannot_try_unlimited_addresses(client):
    codes = [_forgot(client, f"person{i}@example.com").status_code for i in range(11)]
    assert codes == [202] * 10 + [429]


def test_the_limit_resets_after_the_window(client, auth_headers):
    for _ in range(3):
        _forgot(client)
    assert _forgot(client).status_code == 429

    redis_client.delete(*redis_client.keys("ratelimit:*"))  # what the TTL expiring does
    assert _forgot(client).status_code == 202


def test_a_counter_always_gets_an_expiry(client, auth_headers):
    _forgot(client)
    keys = redis_client.keys("ratelimit:*")
    assert len(keys) == 2  # one per address, one per IP
    assert all(0 < redis_client.ttl(k) <= 900 for k in keys)
