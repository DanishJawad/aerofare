from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bookings.enums import BookingStatus
from app.bookings.models import Booking
from app.flights.models import Flight

from .enums import PaymentStatus
from .models import Payment


class PaymentNotFound(Exception):
    pass


class PaymentNotRefundable(Exception):
    pass


def get_payment(db: Session, payment_id: int) -> Payment | None:
    return db.get(Payment, payment_id)


def payment_belongs_to_user(db: Session, payment: Payment, user_id: int) -> bool:
    booking = db.get(Booking, payment.booking_id)
    return booking is not None and booking.user_id == user_id


def get_user_payments(db: Session, user_id: int) -> list[Payment]:
    stmt = (
        select(Payment)
        .join(Booking, Payment.booking_id == Booking.id)
        .where(Booking.user_id == user_id)
    )
    return list(db.execute(stmt).scalars().all())


def get_all_payments(db: Session) -> list[Payment]:
    return list(db.execute(select(Payment)).scalars().all())


def refund_payment(db: Session, payment_id: int) -> Payment:
    # Same lock order as cancel_booking (booking -> payment -> flight), so a
    # concurrent cancel and refund queue up instead of deadlocking. We only
    # know the booking id through the payment, so read it first without a
    # lock: booking_id never changes, so an unlocked read of it is safe.
    booking_id = db.scalar(select(Payment.booking_id).where(Payment.id == payment_id))
    if booking_id is None:
        raise PaymentNotFound()

    booking = db.get(Booking, booking_id, with_for_update=True)
    payment = db.get(Payment, payment_id, with_for_update=True)

    if payment.status != PaymentStatus.COMPLETED:
        raise PaymentNotRefundable()

    flight = db.execute(
        select(Flight).where(Flight.id == booking.flight_id).with_for_update()
    ).scalar_one()

    payment.status = PaymentStatus.REFUNDED
    if booking.status == BookingStatus.CONFIRMED:
        booking.status = BookingStatus.CANCELLED
        flight.available_seats += booking.seats_booked

    db.commit()
    db.refresh(payment)
    return payment
