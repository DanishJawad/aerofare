from fastapi import APIRouter, HTTPException

from app.authentication.dependencies import AdminUser, CurrentUser
from app.database import DbSession

from . import services
from .schemas import BookingCreate, BookingResponse

router = APIRouter(prefix="/bookings", tags=["bookings"])


# "/me" must be declared before "/{booking_id}", or GET /bookings/me would match
# "/{booking_id}" with booking_id="me" and fail int conversion.
@router.get("/me", response_model=list[BookingResponse])
def read_my_bookings(current_user: CurrentUser, db: DbSession):
    return services.get_user_bookings(db, current_user.id)


@router.get("", response_model=list[BookingResponse])
def read_all_bookings(admin: AdminUser, db: DbSession):
    return services.get_all_bookings(db)


@router.get("/{booking_id}", response_model=BookingResponse)
def read_booking(booking_id: int, current_user: CurrentUser, db: DbSession):
    booking = services.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not your booking")
    return booking


@router.post("", response_model=BookingResponse, status_code=201)
def create_booking(new_booking: BookingCreate, current_user: CurrentUser, db: DbSession):
    try:
        return services.create_booking(db, current_user.id, new_booking)
    except services.FlightNotFound:
        raise HTTPException(status_code=404, detail="Flight not found")
    except services.FlightDeparted:
        raise HTTPException(status_code=409, detail="Flight has already departed")
    except services.NotEnoughSeats:
        raise HTTPException(status_code=409, detail="Not enough seats available")


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(booking_id: int, current_user: CurrentUser, db: DbSession):
    try:
        return services.cancel_booking(db, current_user.is_admin, current_user.id, booking_id)
    except services.BookingNotFound:
        raise HTTPException(status_code=404, detail="Booking not found")
    except services.NotBookingOwner:
        raise HTTPException(status_code=403, detail="Not your booking")
    except services.BookingNotCancellable:
        raise HTTPException(status_code=409, detail="Booking cannot be cancelled")
