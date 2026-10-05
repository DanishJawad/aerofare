import threading
from decimal import Decimal

from app.bookings import services as booking_services
from app.bookings.schemas import BookingCreate

from .conftest import TestingSessionLocal


def _make_flight(
    client,
    admin_headers,
    seats=10,
    start="2030-01-01T08:00:00+00:00",
    end="2030-01-01T10:00:00+00:00",
):
    ap1 = client.post(
        "/airports", json={"name": "A", "city": "Lahore", "country": "PK"}, headers=admin_headers
    ).json()["id"]
    ap2 = client.post(
        "/airports", json={"name": "B", "city": "Karachi", "country": "PK"}, headers=admin_headers
    ).json()["id"]
    r = client.post(
        "/flights",
        json={
            "airline_name": "PIA",
            "departure_airport": ap1,
            "arrival_airport": ap2,
            "start_time": start,
            "end_time": end,
            "price": "150.00",
            "total_seats": seats,
            "available_seats": seats,
            "flight_class": "economy",
        },
        headers=admin_headers,
    )
    return r.json()["id"]


# -------------------------------------------------------------- the headline case


def test_concurrent_bookings_cannot_oversell_the_last_seat(client, admin_headers, login_as):
    """Two users race for the same single remaining seat. The row lock in
    create_booking must serialise them: exactly one booking succeeds, the
    other is rejected, and the flight never goes negative - regardless of
    exactly how the two threads happen to interleave."""
    flight_id = _make_flight(client, admin_headers, seats=1)

    headers_a = login_as("racer_a@example.com")
    headers_b = login_as("racer_b@example.com")
    user_a = client.get("/users/me", headers=headers_a).json()["id"]
    user_b = client.get("/users/me", headers=headers_b).json()["id"]

    results: list[tuple[str, str]] = []
    results_lock = threading.Lock()

    def attempt(user_id: int) -> None:
        db = TestingSessionLocal()
        try:
            booking = booking_services.create_booking(
                db, user_id, BookingCreate(flight_id=flight_id, seats_booked=1)
            )
            outcome = ("ok", str(booking.id))
        except Exception as exc:  # noqa: BLE001 - we want to see whatever it raises
            outcome = ("error", type(exc).__name__)
        finally:
            db.close()
        with results_lock:
            results.append(outcome)

    t1 = threading.Thread(target=attempt, args=(user_a,))
    t2 = threading.Thread(target=attempt, args=(user_b,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r[0] == "ok"]
    failures = [r for r in results if r[0] == "error"]

    assert len(successes) == 1, f"expected exactly one successful booking, got {results}"
    assert len(failures) == 1, f"expected exactly one rejected booking, got {results}"
    assert failures[0][1] == "NotEnoughSeats"

    flight = client.get(f"/flights/{flight_id}").json()
    assert flight["available_seats"] == 0


# -------------------------------------------------------------- create


def test_create_booking_decrements_seats(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)

    r = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 3}, headers=auth_headers
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "confirmed"
    assert Decimal(str(body["total_amount"])) == Decimal("450.00")  # 3 * 150.00

    flight = client.get(f"/flights/{flight_id}").json()
    assert flight["available_seats"] == 7


def test_booking_exactly_the_last_seats_succeeds(client, auth_headers, admin_headers):
    """Regression test for the off-by-one bug: seats_booked == available_seats
    must be allowed, not rejected."""
    flight_id = _make_flight(client, admin_headers, seats=2)

    r = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 2}, headers=auth_headers
    )
    assert r.status_code == 201
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 0


def test_overbooking_is_rejected(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=2)

    r = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 5}, headers=auth_headers
    )
    assert r.status_code == 409
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 2


def test_cannot_book_a_departed_flight(client, auth_headers, admin_headers):
    flight_id = _make_flight(
        client,
        admin_headers,
        seats=10,
        start="2000-01-01T08:00:00+00:00",
        end="2000-01-01T10:00:00+00:00",
    )

    r = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 1}, headers=auth_headers
    )
    assert r.status_code == 409


def test_booking_a_missing_flight_is_404(client, auth_headers):
    r = client.post("/bookings", json={"flight_id": 999999, "seats_booked": 1}, headers=auth_headers)
    assert r.status_code == 404


# -------------------------------------------------------------- cancel


def test_cancel_restores_seats(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 4}, headers=auth_headers
    ).json()

    r = client.post(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 10


def test_cannot_cancel_twice(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 1}, headers=auth_headers
    ).json()

    client.post(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    r = client.post(f"/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert r.status_code == 409


def test_other_user_cannot_see_or_cancel_your_booking(client, auth_headers, admin_headers, login_as):
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 1}, headers=auth_headers
    ).json()

    other = login_as("other@example.com")
    assert client.get(f"/bookings/{booking['id']}", headers=other).status_code == 403
    assert client.post(f"/bookings/{booking['id']}/cancel", headers=other).status_code == 403
