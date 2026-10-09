from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from .models import Flight
from .schemas import FlightCreate, FlightSearch, FlightUpdate


def create_flight(db: Session, flight: FlightCreate) -> Flight:
    new_flight = Flight(**flight.model_dump())
    db.add(new_flight)
    db.commit()
    db.refresh(new_flight)
    return new_flight

def get_flights(db: Session) -> list[Flight]:
    stmt = select(Flight)
    return list(db.execute(stmt).scalars().all())

def get_flight_by_id(flight_id: int, db: Session) -> Flight | None:
    return db.get(Flight, flight_id)

def update_flight(flight_id: int , db: Session, flight: FlightUpdate) -> Flight | None:
    db_flight = get_flight_by_id(flight_id, db)

    if not db_flight:
        return None

    for key, value in flight.model_dump(exclude_unset=True).items():
        setattr(db_flight, key, value)

    db.commit()
    db.refresh(db_flight)
    return db_flight

def build_search_query(search_params: FlightSearch) -> Select[tuple[Flight]]:
    """The SELECT behind GET /flights/search. Separate from search_flights so the
    benchmark in scripts/bench_search.py can run, and EXPLAIN, the exact query
    the API runs."""
    stmt = select(Flight)

    if search_params.arrival_airport:
        stmt = stmt.where(Flight.arrival_airport == search_params.arrival_airport)

    if search_params.departure_airport:
        stmt = stmt.where(Flight.departure_airport == search_params.departure_airport)

    if search_params.start_time:
        stmt = stmt.where(Flight.start_time >= search_params.start_time)

    if search_params.end_time:
        stmt = stmt.where(Flight.end_time <= search_params.end_time)

    if search_params.min_price is not None:
        stmt = stmt.where(Flight.price >= search_params.min_price)

    if search_params.max_price is not None:
        stmt = stmt.where(Flight.price <= search_params.max_price)

    if search_params.flight_class:
        stmt = stmt.where(Flight.flight_class == search_params.flight_class)

    # id breaks ties between flights that depart at the same moment. Without it
    # their order is not guaranteed, and a flight could appear on two pages or
    # on none.
    return (
        stmt.order_by(Flight.start_time, Flight.id)
        .limit(search_params.limit)
        .offset(search_params.offset)
    )


def search_flights(search_params: FlightSearch, db: Session) -> list[Flight]:
    return list(db.execute(build_search_query(search_params)).scalars().all())