from typing import Annotated

from fastapi import APIRouter, Header, Response

from app.authentication.dependencies import AdminUser, CurrentUser
from app.commons.errors import ApiError, error_responses
from app.database import DbSession

from . import services
from .schemas import BookingCreate, BookingResponse

router = APIRouter(prefix="/bookings", tags=["bookings"])


# "/me" must be declared before "/{booking_id}", or GET /bookings/me would match
# "/{booking_id}" with booking_id="me" and fail int conversion.
@router.get("/me", response_model=list[BookingResponse], responses=error_responses(401, 503))
def read_my_bookings(current_user: CurrentUser, db: DbSession):
    """The logged-in user's bookings."""
    return services.get_user_bookings(db, current_user.id)


@router.get("", response_model=list[BookingResponse], responses=error_responses(401, 403, 503))
def read_all_bookings(admin: AdminUser, db: DbSession):
    """List every booking. Admin only."""
    return services.get_all_bookings(db)


@router.get("/{booking_id}", response_model=BookingResponse, responses=error_responses(401, 403, 404, 503))
def read_booking(booking_id: int, current_user: CurrentUser, db: DbSession):
    """Get one booking. Only its owner or an admin can read it."""
    booking = services.get_booking(db, booking_id)
    if booking is None:
        raise ApiError(404, "booking_not_found", "Booking not found")
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise ApiError(403, "not_booking_owner", "Not your booking")
    return booking


@router.post(
    "",
    response_model=BookingResponse,
    status_code=201,
    responses={
        200: {"model": BookingResponse, "description": "Replay: the original booking, returned again"},
        **error_responses(401, 404, 409, 503),
    },
)
def create_booking(
    new_booking: BookingCreate,
    current_user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str | None,
        Header(
            min_length=1,
            max_length=64,
            description="Any unique value (a UUID works), chosen by the client for one booking attempt. "
            "Sending the same key again returns the original booking (200) instead of booking twice.",
        ),
    ] = None,
):
    """Book seats on a flight. Seats are reserved and a payment is recorded in one transaction.

    Send an `Idempotency-Key` header to make retries safe: if the first request succeeded but
    its response was lost, retrying with the same key returns that booking with status 200 and
    `Idempotent-Replayed: true`. Conflicts: `not_enough_seats`, `flight_departed`.
    Using one key for a different request is `idempotency_key_reused`."""
    try:
        result = services.create_booking(db, current_user.id, new_booking, idempotency_key)
    except services.FlightNotFound:
        raise ApiError(404, "flight_not_found", "Flight not found")
    except services.FlightDeparted:
        raise ApiError(409, "flight_departed", "Flight has already departed")
    except services.NotEnoughSeats:
        raise ApiError(409, "not_enough_seats", "Not enough seats available")
    except services.IdempotencyKeyReused:
        raise ApiError(
            422,
            "idempotency_key_reused",
            "This Idempotency-Key was already used for a different request",
        )

    if result.replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return result.booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse, responses=error_responses(401, 403, 404, 409, 503))
def cancel_booking(booking_id: int, current_user: CurrentUser, db: DbSession):
    """Cancel a booking: seats go back to the flight and a completed payment is refunded. `booking_not_cancellable` if it is already cancelled."""
    try:
        return services.cancel_booking(db, current_user.is_admin, current_user.id, booking_id)
    except services.BookingNotFound:
        raise ApiError(404, "booking_not_found", "Booking not found")
    except services.NotBookingOwner:
        raise ApiError(403, "not_booking_owner", "Not your booking")
    except services.BookingNotCancellable:
        raise ApiError(409, "booking_not_cancellable", "Booking cannot be cancelled")
