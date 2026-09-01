from typing import Self

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, model_validator

from .enums import FlightClass

class FlightCreate(BaseModel):
    airline_name: str
    departure_airport: int
    arrival_airport: int
    start_time: datetime
    end_time: datetime
    price: Decimal = Field(max_digits=10 , decimal_places=2, ge=0)
    total_seats: int
    available_seats: int
    flight_class: FlightClass

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.available_seats > self.total_seats:
            raise ValueError("available_seats cannot exceed total_seats")
        if self.departure_airport == self.arrival_airport:
            raise ValueError("departure and arrival airports must differ")
        return self

class FlightResponse(FlightCreate):
    model_config = ConfigDict(from_attributes=True)
    
    id: int

class FlightUpdate(BaseModel):
    airline_name: str | None = None
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    total_seats: int | None = None
    available_seats: int | None = None
    flight_class: FlightClass | None = None

class FlightSearch(BaseModel):
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    max_price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    flight_class: FlightClass | None = None