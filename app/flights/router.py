from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from . import services
from .schemas import FlightCreate, FlightResponse, FlightSearch, FlightUpdate
from ..database import get_db

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=list[FlightResponse])
def get_all_flights(db: Session = Depends(get_db)):
    return services.get_flights(db)


@router.get("/search", response_model=list[FlightResponse])
def search_flights(filters: Annotated[FlightSearch, Query()], db: Session = Depends(get_db)):
    return services.search_flights(filters, db)


@router.get("/{flight_id}", response_model=FlightResponse)
def get_flight_by_id(flight_id: int, db: Session = Depends(get_db)):
    flight = services.get_flight_by_id(flight_id, db)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight


@router.post("", response_model=FlightResponse, status_code=201)
def create_flight(new_flight: FlightCreate, db: Session = Depends(get_db)):
    return services.create_flight(db, new_flight)


@router.patch("/{flight_id}", response_model=FlightResponse)
def update_flight(flight_id: int, updated_flight: FlightUpdate, db: Session = Depends(get_db)):
    flight = services.update_flight(flight_id, db, updated_flight)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight
