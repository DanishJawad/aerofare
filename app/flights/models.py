from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .enums import FlightClass

class Flight(Base):
    __tablename__ = "flights"

    id : Mapped[int] = mapped_column(primary_key=True)
    airline_name: Mapped[str] = mapped_column(String(50), index= True)
    departure_airport: Mapped[int] = mapped_column(ForeignKey("airports.id"))
    arrival_airport: Mapped[int] = mapped_column(ForeignKey("airports.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price : Mapped[Decimal] = mapped_column(Numeric(10,2))
    total_seats: Mapped[int]
    available_seats: Mapped[int]
    flight_class: Mapped[FlightClass] = mapped_column(Enum(FlightClass, native_enum=False, length=20))

    # Serves GET /flights/search: two equalities (the route) then a range (the
    # date), which is the order MySQL can walk an index in. See
    # docs/query-optimization.md for the measurements behind it.
    __table_args__ = (
        Index("ix_flights_route_start_time", "departure_airport", "arrival_airport", "start_time"),
    )   