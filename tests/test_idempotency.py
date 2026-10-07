import threading
import uuid

from sqlalchemy import select

from app.bookings import services as booking_services
from app.bookings.schemas import BookingCreate
from app.flights.models import Flight

from .conftest import TestingSessionLocal
from .test_bookings import _make_flight, _race_while_flight_is_locked
from .test_errors import assert_envelope


def _book(client, headers, flight_id, seats=1, key=None):
    sent = {**headers, **({"Idempotency-Key": key} if key else {})}
    return client.post("/bookings", json={"flight_id": flight_id, "seats_booked": seats}, headers=sent)


def _seats_left(client, flight_id) -> int:
    return client.get(f"/flights/{flight_id}").json()["available_seats"]


# -------------------------------------------------------------- a retry after the first request finished


def test_retrying_with_the_same_key_returns_the_original_booking(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    key = str(uuid.uuid4())

    first = _book(client, auth_headers, flight_id, seats=2, key=key)
    second = _book(client, auth_headers, flight_id, seats=2, key=key)

    assert first.status_code == 201
    assert "Idempotent-Replayed" not in first.headers
    assert second.status_code == 200
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json() == first.json()

    # The point of the feature: the retry did not book again or charge again.
    assert _seats_left(client, flight_id) == 8
    assert len(client.get("/bookings/me", headers=auth_headers).json()) == 1
    assert len(client.get("/payments/me", headers=auth_headers).json()) == 1


def test_without_a_key_every_request_books(client, auth_headers, admin_headers):
    """No header means no protection: behaviour stays exactly as before."""
    flight_id = _make_flight(client, admin_headers, seats=10)

    assert _book(client, auth_headers, flight_id).status_code == 201
    assert _book(client, auth_headers, flight_id).status_code == 201

    assert _seats_left(client, flight_id) == 8
    assert len(client.get("/bookings/me", headers=auth_headers).json()) == 2


def test_a_retry_still_succeeds_after_the_flight_sold_out(client, auth_headers, admin_headers):
    """A client retrying a request that already worked must be told so, not
    told 'not enough seats' because its own booking took the last one."""
    flight_id = _make_flight(client, admin_headers, seats=1)
    key = "last-seat"

    first = _book(client, auth_headers, flight_id, seats=1, key=key)
    assert _seats_left(client, flight_id) == 0
    retry = _book(client, auth_headers, flight_id, seats=1, key=key)

    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]


def test_a_replay_returns_the_booking_as_it_is_now(client, auth_headers, admin_headers):
    """The key identifies the attempt, not a frozen answer. If the booking was
    cancelled since, the replay says so."""
    flight_id = _make_flight(client, admin_headers, seats=10)
    first = _book(client, auth_headers, flight_id, key="then-cancelled")
    client.post(f"/bookings/{first.json()['id']}/cancel", headers=auth_headers)

    replay = _book(client, auth_headers, flight_id, key="then-cancelled")

    assert replay.status_code == 200
    assert replay.json()["status"] == "cancelled"
    assert _seats_left(client, flight_id) == 10


# -------------------------------------------------------------- misuse


def test_reusing_a_key_for_a_different_request_is_rejected(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)
    other_flight_id = _make_flight(client, admin_headers, seats=10)
    _book(client, auth_headers, flight_id, seats=2, key="one-key")

    different_seats = _book(client, auth_headers, flight_id, seats=3, key="one-key")
    different_flight = _book(client, auth_headers, other_flight_id, seats=2, key="one-key")

    assert_envelope(different_seats, 422, "idempotency_key_reused")
    assert_envelope(different_flight, 422, "idempotency_key_reused")
    assert _seats_left(client, flight_id) == 8
    assert _seats_left(client, other_flight_id) == 10


def test_two_users_may_use_the_same_key(client, auth_headers, admin_headers, login_as):
    """Keys are scoped to the user. Otherwise one user's key could replay,
    or block, another user's booking."""
    flight_id = _make_flight(client, admin_headers, seats=10)
    other = login_as("someone.else@example.com")

    mine = _book(client, auth_headers, flight_id, key="shared-key")
    theirs = _book(client, other, flight_id, key="shared-key")

    assert mine.status_code == 201 and theirs.status_code == 201
    assert mine.json()["id"] != theirs.json()["id"]
    assert _seats_left(client, flight_id) == 8


def test_a_failed_request_is_not_remembered(client, auth_headers, admin_headers):
    """Only successes are stored, so a failure does not poison the key."""
    flight_id = _make_flight(client, admin_headers, seats=2)

    too_many = _book(client, auth_headers, flight_id, seats=5, key="try-again")
    assert_envelope(too_many, 409, "not_enough_seats")

    fewer = _book(client, auth_headers, flight_id, seats=1, key="try-again")
    assert fewer.status_code == 201


def test_the_key_must_be_between_1_and_64_characters(client, auth_headers, admin_headers):
    flight_id = _make_flight(client, admin_headers, seats=10)

    too_long = _book(client, auth_headers, flight_id, key="k" * 65)
    assert_envelope(too_long, 422, "validation_error")
    assert _book(client, auth_headers, flight_id, key="k" * 64).status_code == 201


# -------------------------------------------------------------- two copies of one request at the same time


def _run_two_identical_requests(client, auth_headers, flight_id):
    """Both copies pass the 'already booked?' lookup (nothing is booked yet) and
    then both wait for the flight lock, which the helper holds until both are
    stuck. So they are guaranteed to overlap, the way a double-click would."""
    user_id = client.get("/users/me", headers=auth_headers).json()["id"]
    outcomes = []
    lock = threading.Lock()

    def request(db):
        result = booking_services.create_booking(
            db, user_id, BookingCreate(flight_id=flight_id, seats_booked=1), "double-click"
        )
        with lock:
            outcomes.append((result.booking.id, result.replayed))

    results = _race_while_flight_is_locked(flight_id, request, request)
    return results, outcomes


def test_simultaneous_duplicates_book_once_when_seats_remain(client, auth_headers, admin_headers):
    """The loser gets as far as inserting, and the unique constraint stops it."""
    flight_id = _make_flight(client, admin_headers, seats=10)

    results, outcomes = _run_two_identical_requests(client, auth_headers, flight_id)

    assert results == ["ok", "ok"], results
    assert len({booking_id for booking_id, _ in outcomes}) == 1
    assert sorted(replayed for _, replayed in outcomes) == [False, True]
    assert _seats_left(client, flight_id) == 9
    assert len(client.get("/bookings/me", headers=auth_headers).json()) == 1
    assert len(client.get("/payments/me", headers=auth_headers).json()) == 1


def test_simultaneous_duplicates_book_once_even_for_the_last_seat(client, auth_headers, admin_headers):
    """The winner took the last seat, so the loser fails the seat check before
    it ever reaches the insert. It must still come back as a success."""
    flight_id = _make_flight(client, admin_headers, seats=1)

    results, outcomes = _run_two_identical_requests(client, auth_headers, flight_id)

    assert results == ["ok", "ok"], results
    assert len({booking_id for booking_id, _ in outcomes}) == 1
    assert sorted(replayed for _, replayed in outcomes) == [False, True]
    assert _seats_left(client, flight_id) == 0
    assert len(client.get("/bookings/me", headers=auth_headers).json()) == 1


def test_a_retry_does_not_wait_for_other_bookings_on_the_flight(client, auth_headers, admin_headers):
    """The retry is answered from the lookup, without taking the flight lock,
    so it comes back immediately even while someone else holds that lock."""
    flight_id = _make_flight(client, admin_headers, seats=10)
    first = _book(client, auth_headers, flight_id, key="quick-retry")
    user_id = first.json()["user_id"]

    holder = TestingSessionLocal()
    holder.execute(select(Flight).where(Flight.id == flight_id).with_for_update())
    answered = []

    def retry():
        db = TestingSessionLocal()
        try:
            answered.append(
                booking_services.create_booking(
                    db, user_id, BookingCreate(flight_id=flight_id, seats_booked=1), "quick-retry"
                )
            )
        finally:
            db.close()

    thread = threading.Thread(target=retry)
    thread.start()
    thread.join(timeout=3)
    still_waiting = thread.is_alive()

    holder.commit()  # release the lock either way, so a failure here cannot hang the suite
    holder.close()
    thread.join()

    assert not still_waiting, "the retry waited for the flight lock"
    assert answered[0].replayed is True
