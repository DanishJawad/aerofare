from fastapi import APIRouter, HTTPException

from . import services
from .schemas import AirportUpdate, AirportCreate, AirportResponse
from ..database import DbSession

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("", response_model=list[AirportResponse])
def read_airports(db: DbSession):
    return services.get_all_airports(db)

@router.get("/{airport_id}", response_model=AirportResponse)
def get_airport_by_id(airport_id : int, db: DbSession):

    db_airport = services.get_airport_by_id(db , airport_id)

    if not db_airport:
            raise HTTPException(status_code=404 , detail="Airport not found")
    
    return db_airport

@router.post("", response_model=AirportResponse, status_code=201)
def create_airport(new_airport: AirportCreate, db: DbSession):
    return services.create_airport(db, new_airport)

@router.patch("/{airport_id}", response_model= AirportResponse)
def update_airport(airport_id: int , updated_airport: AirportUpdate, db: DbSession):
    updated = services.update_airport(airport_id= airport_id, db= db, updated_airport= updated_airport)

    if not updated:
        raise HTTPException(status_code=404 , detail="Airport not found")

    return updated