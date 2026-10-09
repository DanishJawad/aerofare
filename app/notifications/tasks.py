import logging
import smtplib
from collections.abc import Callable

from app.airports.models import Airport
from app.authentication.models import User
from app.authentication.password_reset import RESET_TOKEN_TTL_SECONDS
from app.commons.log_config import request_id_var
from app.bookings.enums import BookingStatus
from app.bookings.models import Booking
from app.database import SessionLocal, settings
from app.flights.models import Flight
from app.payments import models as _payment_models  # noqa: F401 - the worker must load every model
from app.worker import REQUEST_ID_HEADER, celery_app

from .mailer import send_email
from .rendering import render_email

logger = logging.getLogger(__name__)

# Only errors that mean "the mail server is not answering right now" are
# retried. A bug in a task should fail loudly, not repeat 3 times.
# retry_backoff=10 waits up to 10s, 20s, 40s between attempts (Celery
# randomises each wait downwards a little), so a mail server that is down for
# a minute is survived.
_RETRY_ON_MAIL_ERRORS = {
    "autoretry_for": (smtplib.SMTPException, OSError),
    "retry_backoff": 10,
    "max_retries": 3,
}


@celery_app.task(**_RETRY_ON_MAIL_ERRORS)
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

        route = f"{departure.city} to {arrival.city}"
        subject = f"Booking confirmed: {route}"
        text, html = render_email(
            "booking_confirmation",
            name=user.name,
            booking_id=booking.id,
            details=[
                ("Flight", f"{flight.airline_name}, {route}"),
                ("Departs", f"{flight.start_time:%Y-%m-%d %H:%M} UTC"),
                ("Seats", f"{booking.seats_booked} ({flight.flight_class.value})"),
                ("Total paid", str(booking.total_amount)),
            ],
        )
        to = user.email

    # Sent after the session closes: the connection to MySQL is not held open
    # while waiting on a mail server.
    send_email(to, subject, text, html)
    logger.info("Sent confirmation for booking %s", booking_id)


@celery_app.task(**_RETRY_ON_MAIL_ERRORS)
def send_password_reset(user_id: int, token: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            logger.warning("User %s not found, no reset email sent", user_id)
            return
        name, to = user.name, user.email

    # In the fragment (#), not the query string (?): browsers never send the
    # fragment to a server, so the token stays out of access logs and Referer
    # headers. The React page reads it from the address bar.
    link = f"{settings.frontend_url.rstrip('/')}/reset-password#token={token}"
    text, html = render_email(
        "password_reset", name=name, link=link, expires_minutes=RESET_TOKEN_TTL_SECONDS // 60
    )
    send_email(to, "Reset your Aerofare password", text, html)
    logger.info("Sent password reset email to user %s", user_id)


def _enqueue(task: Callable[..., object], label: str, *args: object) -> None:
    """Queue a task. A failure here must never fail the request: whatever the
    request did is already committed, and the email is the best-effort part.
    `label` is what gets logged: the args can hold a secret (a reset token)."""
    try:
        # The current request's id travels with the task as a message header,
        # so the worker's log lines for it can be matched to this request.
        task.apply_async(args, headers={REQUEST_ID_HEADER: request_id_var.get()})  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Could not queue %s", label)


def enqueue_booking_confirmation(booking_id: int) -> None:
    _enqueue(send_booking_confirmation, f"the confirmation for booking {booking_id}", booking_id)


def enqueue_password_reset(user_id: int, token: str) -> None:
    _enqueue(send_password_reset, f"the password reset email for user {user_id}", user_id, token)
