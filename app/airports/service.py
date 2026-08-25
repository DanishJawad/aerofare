from .models import Airport
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from .schema import AirportCreate, AirportUpdate

def get_all_airports(db: Session):
    return db.query(Airport).all()

def get_airport_by_id(db: Session, airport_id: int):
    return db.query(Airport).filter(Airport.id == airport_id).first()

def update_airport(db: Session, airport_id: int ,updated_airport: AirportUpdate) -> Airport:
    db_airport = get_airport_by_id(db, airport_id)
    
    if not db_airport:
        return None

    update_data = updated_airport.model_dump(exclude_unset=True)

    if not update_data:
        return db_airport

    for key, value in update_data.items():
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