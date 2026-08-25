from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from . import service
from .schema import AirportUpdate, AirportCreate, AirportResponse
from ..database import get_db

router = APIRouter()


@router.get("/airports", response_model=List[AirportResponse])
def read_airports(db: Session = Depends(get_db)):
    airports_list = service.get_all_airports(db)

    if not airports_list:
        raise HTTPException(status_code=404 , detail="Airports not found")

    return airports_list

@router.get("/airports/{airport_id}", response_model=AirportResponse)
def get_airport_by_id(airport_id : int,db: Session = Depends(get_db)):

    db_airport = service.get_airport_by_id(db , airport_id)

    if not db_airport:
            raise HTTPException(status_code=404 , detail="Airports not found")
    
    return db_airport

@router.post("/", response_model=AirportResponse)
def create_airport(new_airport: AirportCreate, db: Session = Depends(get_db)):
    new = service.create_airport(db, new_airport)

    if not new:
        raise HTTPException(status_code=404 , detail="Airport could not be created")
    return new

@router.patch("/airports/{airport_id}", response_model= AirportResponse)
def update_airport(airport_id: int , updated_airport: AirportUpdate, db: Session = Depends(get_db)):
    updated = service.update_airport(airport_id= airport_id, db= db, updated_airport= updated_airport)

    if not updated:
        raise HTTPException(status_code=404 , detail="Airport does not exist")

    return updated