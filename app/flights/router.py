from typing import Annotated

from fastapi import APIRouter, Query

from ..authentication.dependencies import AdminUser
from ..commons.errors import ApiError, error_responses
from ..database import DbSession
from . import services
from .schemas import FlightCreate, FlightResponse, FlightSearch, FlightUpdate

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=list[FlightResponse])
def get_all_flights(db: DbSession):
    """List all flights."""
    return services.get_flights(db)


@router.get("/search", response_model=list[FlightResponse])
def search_flights(filters: Annotated[FlightSearch, Query()], db: DbSession):
    """Search flights. Every filter is optional and filters combine with AND. Times are compared in UTC."""
    return services.search_flights(filters, db)


@router.get("/{flight_id}", response_model=FlightResponse, responses=error_responses(404))
def get_flight_by_id(flight_id: int, db: DbSession):
    """Get one flight by id."""
    flight = services.get_flight_by_id(flight_id, db)
    if not flight:
        raise ApiError(404, "flight_not_found", "Flight not found")
    return flight


@router.post("", response_model=FlightResponse, status_code=201, responses=error_responses(401, 403, 503))
def create_flight(new_flight: FlightCreate, admin: AdminUser, db: DbSession):
    """Create a flight. Admin only. Times with a UTC offset are converted to UTC."""
    return services.create_flight(db, new_flight)


@router.patch("/{flight_id}", response_model=FlightResponse, responses=error_responses(401, 403, 404, 503))
def update_flight(flight_id: int, updated_flight: FlightUpdate, admin: AdminUser, db: DbSession):
    """Update any subset of a flight's fields. Admin only. The fields sent must be consistent with each other."""
    flight = services.update_flight(flight_id, db, updated_flight)
    if not flight:
        raise ApiError(404, "flight_not_found", "Flight not found")
    return flight
