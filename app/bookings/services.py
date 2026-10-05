from datetime import datetime, timezone

from sqlalchemy import select
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


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_booking(db: Session, user_id: int, new_booking: BookingCreate) -> Booking:
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
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise BookingNotFound()

    if booking.user_id != user_id and not is_admin:
        raise NotBookingOwner()

    if booking.status != BookingStatus.CONFIRMED:
        raise BookingNotCancellable()

    flight = db.execute(
        select(Flight).where(Flight.id == booking.flight_id).with_for_update()
    ).scalar_one()

    booking.status = BookingStatus.CANCELLED
    flight.available_seats += booking.seats_booked

    payment = db.execute(
        select(Payment).where(Payment.booking_id == booking.id)
    ).scalar_one_or_none()

    if payment is not None and payment.status == PaymentStatus.COMPLETED:
        payment.status = PaymentStatus.REFUNDED

    db.commit()
    db.refresh(booking)

    return booking
