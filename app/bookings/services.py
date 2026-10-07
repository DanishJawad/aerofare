from datetime import datetime, timezone
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bookings.enums import BookingStatus
from app.bookings.models import Booking
from app.bookings.schemas import BookingCreate
from app.flights.models import Flight
from app.payments.enums import PaymentStatus
from app.payments.models import Payment


class FlightNotFound(Exception):
    pass


class FlightDeparted(Exception):
    pass


class NotEnoughSeats(Exception):
    pass


class BookingNotFound(Exception):
    pass


class NotBookingOwner(Exception):
    pass


class BookingNotCancellable(Exception):
    pass


class IdempotencyKeyReused(Exception):
    """The same Idempotency-Key arrived with a different request."""


class CreatedBooking(NamedTuple):
    booking: Booking
    replayed: bool  # True when this is an earlier booking returned again, not a new one


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _find_by_key(db: Session, user_id: int, key: str) -> Booking | None:
    return db.execute(
        select(Booking).where(Booking.user_id == user_id, Booking.idempotency_key == key)
    ).scalar_one_or_none()


def _replay(existing: Booking, requested: BookingCreate) -> CreatedBooking:
    # A key stands for ONE request. Reusing it for a different one is a client
    # bug, and quietly returning the old booking would hide it.
    if existing.flight_id != requested.flight_id or existing.seats_booked != requested.seats_booked:
        raise IdempotencyKeyReused()
    return CreatedBooking(existing, replayed=True)


def create_booking(
    db: Session, user_id: int, new_booking: BookingCreate, idempotency_key: str | None = None
) -> CreatedBooking:
    """Book seats. With an idempotency key, retrying the same request returns the
    original booking instead of booking again.

    Only successful bookings are remembered. A request that failed (no seats
    left, flight gone) stores nothing, so it can simply be tried again."""
    if idempotency_key is None:
        return CreatedBooking(_insert_booking(db, user_id, new_booking, None), replayed=False)

    # 1. The usual case: the client is retrying a request that finished earlier.
    #    A plain lookup answers it without locking the flight, so a retry never
    #    queues behind other people's bookings.
    existing = _find_by_key(db, user_id, idempotency_key)
    if existing is not None:
        return _replay(existing, new_booking)

    try:
        return CreatedBooking(
            _insert_booking(db, user_id, new_booking, idempotency_key), replayed=False
        )
    except (FlightDeparted, NotEnoughSeats, IntegrityError):
        # 2. The rare case: two copies of the same request ran at the same time.
        #    The loser can fail in two ways, because the winner already committed:
        #      - IntegrityError: it got far enough to insert, and the unique
        #        constraint on (user_id, idempotency_key) rejected it;
        #      - NotEnoughSeats: the winner took the last seats first.
        #    Either way the loser should not report a failure if its twin
        #    succeeded. Roll back to end this transaction, which also drops its
        #    old view of the data (MySQL's default isolation level can't see
        #    rows committed after the transaction began), and look again.
        db.rollback()
        existing = _find_by_key(db, user_id, idempotency_key)
        if existing is None:
            raise  # a genuine failure: nothing was booked under this key
        return _replay(existing, new_booking)


def _insert_booking(
    db: Session, user_id: int, new_booking: BookingCreate, idempotency_key: str | None
) -> Booking:
    # FOR UPDATE locks this flight row until commit, so a second concurrent
    # booking on the same flight blocks here instead of racing the seat count.
    flight = db.execute(
        select(Flight).where(Flight.id == new_booking.flight_id).with_for_update()
    ).scalar_one_or_none()

    if flight is None:
        raise FlightNotFound()

    if flight.start_time <= _utc_naive_now():
        raise FlightDeparted()

    if new_booking.seats_booked > flight.available_seats:
        raise NotEnoughSeats()

    flight.available_seats -= new_booking.seats_booked

    booking = Booking(
        user_id=user_id,
        flight_id=flight.id,
        seats_booked=new_booking.seats_booked,
        total_amount=flight.price * new_booking.seats_booked,
        status=BookingStatus.CONFIRMED,
        idempotency_key=idempotency_key,
    )
    db.add(booking)
    db.flush()

    payment = Payment(
        booking_id=booking.id,
        amount=booking.total_amount,
        status=PaymentStatus.COMPLETED,
        paid_at=_utc_naive_now(),
    )
    db.add(payment)

    db.commit()
    db.refresh(booking)
    return booking


def get_booking(db: Session, booking_id: int) -> Booking | None:
    return db.get(Booking, booking_id)


def get_user_bookings(db: Session, user_id: int) -> list[Booking]:
    return list(db.execute(select(Booking).where(Booking.user_id == user_id)).scalars().all())


def get_all_bookings(db: Session) -> list[Booking]:
    return list(db.execute(select(Booking)).scalars().all())


def cancel_booking(db: Session, is_admin: bool, user_id: int, booking_id: int) -> Booking:
    # Lock the booking before checking its status. Without the lock, two
    # concurrent cancels both read CONFIRMED and both give the seats back.
    #
    # Lock order is booking -> payment -> flight here and in refund_payment.
    # If the two paths took locks in different orders, a cancel and a refund
    # of the same booking could each hold what the other needs: a deadlock.
    booking = db.get(Booking, booking_id, with_for_update=True)

    if booking is None:
        raise BookingNotFound()

    if booking.user_id != user_id and not is_admin:
        raise NotBookingOwner()

    if booking.status != BookingStatus.CONFIRMED:
        raise BookingNotCancellable()

    payment = db.execute(
        select(Payment).where(Payment.booking_id == booking.id).with_for_update()
    ).scalar_one_or_none()

    flight = db.execute(
        select(Flight).where(Flight.id == booking.flight_id).with_for_update()
    ).scalar_one()

    booking.status = BookingStatus.CANCELLED
    flight.available_seats += booking.seats_booked

    if payment is not None and payment.status == PaymentStatus.COMPLETED:
        payment.status = PaymentStatus.REFUNDED

    db.commit()
    db.refresh(booking)

    return booking
