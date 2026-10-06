import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.authentication.security import redis_client
from app.commons.errors import register_error_handlers
from app.commons.middleware import request_context

from .test_bookings import _make_flight


def assert_envelope(response, status: int, code: str) -> dict:
    """Every error must have exactly this shape, and the request id in the
    body must be the one in the response header."""
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == code
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", error["request_id"])
    return error


# -------------------------------------------------------------- raised by our code


def test_missing_resource_uses_a_specific_code(client):
    error = assert_envelope(client.get("/flights/999999"), 404, "flight_not_found")
    assert error["message"] == "Flight not found"
    assert error["details"] is None


def test_conflict_carries_a_code_a_program_can_switch_on(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=1)
    r = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 5}, headers=auth_headers
    )
    assert_envelope(r, 409, "not_enough_seats")


def test_missing_token_is_401_and_keeps_the_www_authenticate_header(client):
    r = client.get("/users/me")
    assert_envelope(r, 401, "unauthorized")
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_a_garbage_token_is_401_invalid_token(client):
    r = client.get("/users/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert_envelope(r, 401, "invalid_token")
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_non_admin_is_403(client, auth_headers):
    r = client.post(
        "/airports", json={"name": "X", "city": "Y", "country": "PK"}, headers=auth_headers
    )
    assert_envelope(r, 403, "admin_required")


# -------------------------------------------------------------- raised by the framework


def test_unknown_url_is_a_404_in_the_same_shape(client):
    assert_envelope(client.get("/no/such/route"), 404, "not_found")


def test_wrong_method_is_a_405_in_the_same_shape(client):
    assert_envelope(client.delete("/airports"), 405, "method_not_allowed")


def test_validation_errors_list_each_bad_field(client):
    r = client.post("/users/signup", json={"name": "A", "email": "not-an-email", "password": "x"})
    error = assert_envelope(r, 422, "validation_error")

    by_field = {d["field"]: d["message"] for d in error["details"]}
    assert {"email", "password", "city", "country"} <= set(by_field)
    assert all(isinstance(m, str) and m for m in by_field.values())


def test_field_names_match_what_the_frontend_reads(client, auth_headers):
    """BookingPanel in the frontend shows fieldErrors.seats_booked under the
    seat input. If this field name changes, that message silently disappears."""
    r = client.post(
        "/bookings", json={"flight_id": 1, "seats_booked": 0}, headers=auth_headers
    )
    error = assert_envelope(r, 422, "validation_error")
    assert [d["field"] for d in error["details"]] == ["seats_booked"]


def test_a_rule_spanning_several_fields_has_no_field_and_no_pydantic_prefix(
    client, admin_headers
):
    """FlightCreate rejects end_time <= start_time as a whole-body rule. That
    error has no single field, and Pydantic's "Value error, " prefix is
    stripped so clients don't have to."""
    r = client.post(
        "/flights",
        json={
            "airline_name": "PIA",
            "departure_airport": 1,
            "arrival_airport": 2,
            "start_time": "2030-01-01T10:00:00+00:00",
            "end_time": "2030-01-01T08:00:00+00:00",
            "price": "150.00",
            "total_seats": 10,
            "available_seats": 10,
            "flight_class": "economy",
        },
        headers=admin_headers,
    )
    error = assert_envelope(r, 422, "validation_error")
    whole_body = [d for d in error["details"] if d["field"] is None]
    assert whole_body, error["details"]
    assert not whole_body[0]["message"].startswith("Value error")


# -------------------------------------------------------------- when things break


def test_redis_down_means_503_not_a_500_and_not_a_free_pass(client, auth_headers, monkeypatch):
    """Authenticated requests check the token blacklist in Redis. With Redis
    down the request must be refused (fail closed), cleanly."""

    def redis_is_down(*args, **kwargs):
        raise RedisConnectionError("Connection refused")

    monkeypatch.setattr(redis_client, "exists", redis_is_down)

    error = assert_envelope(client.get("/users/me", headers=auth_headers), 503, "service_unavailable")
    assert "Connection refused" not in error["message"]


def test_public_routes_still_work_when_redis_is_down(client, monkeypatch):
    def redis_is_down(*args, **kwargs):
        raise RedisConnectionError("Connection refused")

    monkeypatch.setattr(redis_client, "exists", redis_is_down)
    assert client.get("/airports").status_code == 200


@pytest.fixture
def crashing_client():
    """A tiny app with the real middleware and handlers and one route that
    crashes. Kept separate from the main app so no test-only route can ever
    ship in it. raise_server_exceptions=False makes TestClient behave like a
    real server: answer with the 500 instead of re-raising into the test."""
    app = FastAPI()
    app.middleware("http")(request_context)
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("password=hunter2 in SELECT * FROM users")

    return TestClient(app, raise_server_exceptions=False)


def test_a_crash_is_a_generic_500_that_leaks_nothing(crashing_client):
    r = crashing_client.get("/boom")
    error = assert_envelope(r, 500, "internal_error")
    assert "hunter2" not in r.text
    assert "SELECT" not in r.text
    assert "RuntimeError" not in r.text
    assert error["message"] == "Something went wrong on our side."


def test_a_crash_is_logged_with_the_request_id_the_client_received(crashing_client, caplog):
    with caplog.at_level("ERROR"):
        r = crashing_client.get("/boom", headers={"X-Request-ID": "trace-me-123"})

    assert r.json()["error"]["request_id"] == "trace-me-123"
    logged = [rec for rec in caplog.records if rec.name == "aerofare.errors"]
    assert logged and logged[0].exc_info, "the traceback must be in the log"
    assert "hunter2" in str(logged[0].exc_info[1])
