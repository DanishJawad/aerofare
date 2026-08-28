from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Airport
from .schemas import AirportCreate, AirportUpdate, AirportResponse


def get_all_airports(db: Session) -> list[Airport]:
    stmt = select(Airport)
    return list(db.execute(stmt).scalars().all())

def get_airport_by_id(db: Session, airport_id: int) -> Airport:
    return db.get(Airport, airport_id)

def update_airport(db: Session, airport_id: int ,updated_airport: AirportUpdate) -> Airport:
    db_airport = get_airport_by_id(db, airport_id)
    
    if not db_airport:
        return None

    for key, value in updated_airport.model_dump(exclude_unset=True).items():
        setattr(db_airport, key, value)

    db.commit()
    db.refresh(db_airport)
    return db_airport

def create_airport(db: Session , airport: AirportCreate) -> Airport:
    new_airport = Airport(**airport.model_dump())
    db.add(new_airport)
    db.commit()
    db.refresh(new_airport)
    return new_airport