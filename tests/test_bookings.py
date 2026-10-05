import threading
import time
from decimal import Decimal

from sqlalchemy import select, text

from app.bookings import services as booking_services
from app.bookings.schemas import BookingCreate
from app.flights.models import Flight
from app.payments import services as payment_services

from .conftest import TestingSessionLocal, engine


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


def _wait_for_lock_waits(expected: int, timeout: float = 5.0) -> None:
    """Block until `expected` transactions are stuck waiting on a row lock."""
    deadline = time.monotonic() + timeout
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            # data_lock_waits has one row per blocked lock request. INNODB_TRX
            # looked like the obvious choice but it's served from a cache and
            # missed waits that were really happening.
            waiting = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT REQUESTING_ENGINE_TRANSACTION_ID) "
                    "FROM performance_schema.data_lock_waits"
                )
            ).scalar_one()
            if waiting >= expected:
                return
            time.sleep(0.05)
        state = conn.execute(
            text("SELECT id, state, info FROM information_schema.PROCESSLIST WHERE db = DATABASE()")
        ).all()
    raise AssertionError(f"expected {expected} lock waits, timed out. Connections: {state}")


def _race_while_flight_is_locked(flight_id: int, *operations) -> list[str]:
    """Run each operation in its own thread and session while the test holds
    the flight row lock, so every operation is forced to get past its status
    check before any of them can finish. Without this, two threads almost
    never interleave badly and a race test passes by luck.

    Returns "ok" or the exception class name for each operation."""
    results: list[str] = []
    results_lock = threading.Lock()

    def run(operation) -> None:
        db = TestingSessionLocal()
        try:
            operation(db)
            outcome = "ok"
        except Exception as exc:  # noqa: BLE001 - we want to see whatever it raises
            outcome = type(exc).__name__
        finally:
            db.close()
        with results_lock:
            results.append(outcome)

    holder = TestingSessionLocal()
    holder.execute(select(Flight).where(Flight.id == flight_id).with_for_update())

    threads = [threading.Thread(target=run, args=(op,)) for op in operations]
    try:
        for t in threads:
            t.start()
        _wait_for_lock_waits(expected=len(operations))
    finally:
        # Always release, or a failed wait leaves the lock held and the next
        # test's DROP TABLE hangs on it.
        holder.commit()
        holder.close()
        for t in threads:
            t.join()
    return results


def test_concurrent_cancels_restore_seats_once(client, auth_headers, admin_headers):
    """Two cancels of the same booking at the same moment. Only one may
    succeed; seats must be credited back exactly once."""
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 3}, headers=auth_headers
    ).json()
    user_id = booking["user_id"]

    def cancel(db):
        booking_services.cancel_booking(db, False, user_id, booking["id"])

    results = _race_while_flight_is_locked(flight_id, cancel, cancel)

    assert sorted(results) == ["BookingNotCancellable", "ok"], results
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 10


def test_concurrent_cancel_and_refund_restore_seats_once(client, auth_headers, admin_headers):
    """A user cancels while an admin refunds the same booking. Both paths
    give seats back, so without consistent locking the seats come back twice.
    The two paths must also lock rows in the same order or MySQL deadlocks."""
    flight_id = _make_flight(client, admin_headers, seats=10)
    booking = client.post(
        "/bookings", json={"flight_id": flight_id, "seats_booked": 3}, headers=auth_headers
    ).json()
    payment = client.get("/payments/me", headers=auth_headers).json()[0]

    def cancel(db):
        booking_services.cancel_booking(db, False, booking["user_id"], booking["id"])

    def refund(db):
        payment_services.refund_payment(db, payment["id"])

    results = _race_while_flight_is_locked(flight_id, cancel, refund)

    assert "ok" in results, results
    assert "OperationalError" not in results, f"deadlock: {results}"
    assert client.get(f"/flights/{flight_id}").json()["available_seats"] == 10


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
