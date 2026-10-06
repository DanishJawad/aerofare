from typing import Self

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from .enums import FlightClass


def _to_utc(value: datetime) -> datetime:
    # The client may send an aware datetime with any offset (e.g. "+05:00").
    # PyMySQL writes a datetime's wall-clock digits as-is and ignores tzinfo,
    # so an un-normalised offset gets stored as if it were UTC - silently
    # wrong by however many hours the offset was. Converting here means
    # whatever offset comes in, what lands in the DB is the correct UTC
    # instant. A naive value (no offset) is left alone; it's already treated
    # as UTC by convention.
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value


_FLIGHT_EXAMPLE = {
    "airline_name": "PIA",
    "departure_airport": 1,
    "arrival_airport": 2,
    "start_time": "2030-01-01T08:00:00Z",
    "end_time": "2030-01-01T10:00:00Z",
    "price": "150.00",
    "total_seats": 180,
    "available_seats": 180,
    "flight_class": "economy",
}


class FlightCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_FLIGHT_EXAMPLE]})

    airline_name: str
    departure_airport: int
    arrival_airport: int
    start_time: datetime
    end_time: datetime
    price: Decimal = Field(max_digits=10 , decimal_places=2, ge=0)
    total_seats: int = Field(gt=0)
    available_seats: int = Field(ge=0)
    flight_class: FlightClass

    @field_validator("start_time", "end_time")
    @classmethod
    def normalise_timezone(cls, v: datetime) -> datetime:
        return _to_utc(v)

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
    # Re-declared because the example inherited from FlightCreate has no id.
    model_config = ConfigDict(
        from_attributes=True, json_schema_extra={"examples": [{"id": 1, **_FLIGHT_EXAMPLE}]}
    )

    id: int

class FlightUpdate(BaseModel):
    airline_name: str | None = None
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    total_seats: int | None = Field(default=None, gt=0)
    available_seats: int | None = Field(default=None, ge=0)
    flight_class: FlightClass | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def normalise_timezone(cls, v: datetime | None) -> datetime | None:
        return _to_utc(v) if v is not None else None

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        # A PATCH only has to be internally consistent for the fields it
        # actually sends - checking against the row already in the DB is the
        # service layer's job, not the schema's.
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        if self.total_seats is not None and self.available_seats is not None:
            if self.available_seats > self.total_seats:
                raise ValueError("available_seats cannot exceed total_seats")
        if self.departure_airport is not None and self.arrival_airport is not None:
            if self.departure_airport == self.arrival_airport:
                raise ValueError("departure and arrival airports must differ")
        return self

class FlightSearch(BaseModel):
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    max_price: Decimal | None =  Field(default=None,max_digits=10 , decimal_places=2, ge=0)
    flight_class: FlightClass | None = None
