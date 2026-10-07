import logging
import smtplib

from app.airports.models import Airport
from app.authentication.models import User
from app.bookings.enums import BookingStatus
from app.bookings.models import Booking
from app.database import SessionLocal
from app.flights.models import Flight
from app.payments import models as _payment_models  # noqa: F401 - the worker must load every model
from app.worker import celery_app

from .mailer import send_email

logger = logging.getLogger(__name__)


@celery_app.task(
    # Only errors that mean "the mail server is not answering right now" are
    # retried. A bug in this function should fail loudly, not repeat 3 times.
    autoretry_for=(smtplib.SMTPException, OSError),
    # Waits up to 10s, 20s, 40s between attempts (Celery randomises each wait
    # downwards a little), so a mail server that is down for a minute is survived.
    retry_backoff=10,
    max_retries=3,
)
def send_booking_confirmation(booking_id: int) -> None:
    # The worker is a separate process, so it opens its own database session.
    # It is given the booking's id and reads the rest itself, because the id is
    # small and always serialisable, and the data is fresh when the task runs.
    with SessionLocal() as db:
        booking = db.get(Booking, booking_id)
        if booking is None:
            logger.warning("Booking %s not found, no confirmation sent", booking_id)
            return
        # The task may run a while after the booking: if the user cancelled in
        # between, "your booking is confirmed" would be wrong.
        if booking.status != BookingStatus.CONFIRMED:
            logger.info("Booking %s is %s, no confirmation sent", booking_id, booking.status.value)
            return

        user = db.get(User, booking.user_id)
        flight = db.get(Flight, booking.flight_id)
        departure = db.get(Airport, flight.departure_airport)
        arrival = db.get(Airport, flight.arrival_airport)

        subject = f"Booking confirmed: {departure.city} to {arrival.city}"
        body = (
            f"Hello {user.name},\n\n"
            f"Your booking #{booking.id} is confirmed.\n\n"
            f"Flight: {flight.airline_name}, {departure.city} to {arrival.city}\n"
            f"Departs: {flight.start_time:%Y-%m-%d %H:%M} UTC\n"
            f"Seats: {booking.seats_booked} ({flight.flight_class.value})\n"
            f"Total paid: {booking.total_amount}\n"
        )
        to = user.email

    # Sent after the session closes: the connection to MySQL is not held open
    # while waiting on a mail server.
    send_email(to, subject, body)
    logger.info("Sent confirmation for booking %s", booking_id)


def enqueue_booking_confirmation(booking_id: int) -> None:
    """Queue the email. A failure here must never fail the booking: the seats
    are already reserved and paid for, and the email is only a courtesy."""
    try:
        send_booking_confirmation.delay(booking_id)
    except Exception:
        logger.exception("Could not queue the confirmation for booking %s", booking_id)
