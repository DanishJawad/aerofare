from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ..authentication.dependencies import AdminUser
from ..database import DbSession
from . import services
from .schemas import FlightCreate, FlightResponse, FlightSearch, FlightUpdate

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=list[FlightResponse])
def get_all_flights(db: DbSession):
    return services.get_flights(db)


@router.get("/search", response_model=list[FlightResponse])
def search_flights(filters: Annotated[FlightSearch, Query()], db: DbSession):
    return services.search_flights(filters, db)


@router.get("/{flight_id}", response_model=FlightResponse)
def get_flight_by_id(flight_id: int, db: DbSession):
    flight = services.get_flight_by_id(flight_id, db)
    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")
    return flight


@router.post("", response_model=FlightResponse, status_code=201)
def create_flight(new_flight: FlightCreate, admin: AdminUser, db: DbSession):
    return services.create_flight(db, new_flight)


@router.patch("/{flight_id}", response_model=FlightResponse)
def update_flight(flight_id: int, updated_flight: FlightUpdate, admin: AdminUser, db: DbSession):
    flight = services.update_flight(flight_id, db, updated_flight)
    if not flight:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found")
    return flight
