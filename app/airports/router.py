from fastapi import APIRouter

from . import services
from .schemas import AirportUpdate, AirportCreate, AirportResponse
from ..authentication.dependencies import AdminUser
from ..commons.errors import ApiError, error_responses
from ..database import DbSession

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("", response_model=list[AirportResponse])
def read_airports(db: DbSession):
    """List all airports."""
    return services.get_all_airports(db)

@router.get("/{airport_id}", response_model=AirportResponse, responses=error_responses(404))
def get_airport_by_id(airport_id : int, db: DbSession):
    """Get one airport by id."""

    db_airport = services.get_airport_by_id(db , airport_id)

    if not db_airport:
            raise ApiError(404, "airport_not_found", "Airport not found")
    
    return db_airport

@router.post("", response_model=AirportResponse, status_code=201, responses=error_responses(401, 403, 503))
def create_airport(new_airport: AirportCreate, admin: AdminUser, db: DbSession):
    """Create an airport. Admin only."""
    return services.create_airport(db, new_airport)

@router.patch("/{airport_id}", response_model= AirportResponse, responses=error_responses(401, 403, 404, 503))
def update_airport(airport_id: int , updated_airport: AirportUpdate, admin: AdminUser, db: DbSession):
    """Update any subset of an airport's fields. Admin only."""
    updated = services.update_airport(airport_id= airport_id, db= db, updated_airport= updated_airport)

    if not updated:
        raise ApiError(404, "airport_not_found", "Airport not found")

    return updated