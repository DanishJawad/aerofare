from datetime import datetime, timezone
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import FlightClass


def _to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC."""
    return value.astimezone(timezone.utc)


class FlightBase(BaseModel):
    airline_name: str = Field(min_length=2, max_length=50)
    departure_airport: int
    arrival_airport: int
    start_time: datetime
    end_time: datetime
    price: Decimal = Field(max_digits=10, decimal_places=2, ge=0)
    total_seats: int = Field(gt=0)
    available_seats: int = Field(ge=0)
    flight_class: FlightClass


class FlightCreate(FlightBase):
    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "datetime must include a timezone offset, "
                "e.g. 2026-09-01T08:00:00+05:00"
            )
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


class FlightResponse(FlightBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @field_validator("start_time", "end_time")
    @classmethod
    def stamp_utc(cls, v: datetime) -> datetime:
        # MySQL returns naive datetimes; everything we store is already UTC.
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return _to_utc(v)


class FlightUpdate(BaseModel):
    airline_name: str | None = Field(default=None, min_length=2, max_length=50)
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, ge=0)
    total_seats: int | None = Field(default=None, gt=0)
    available_seats: int | None = Field(default=None, ge=0)
    flight_class: FlightClass | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("datetime must include a timezone offset")
        return _to_utc(v)

    @model_validator(mode="after")
    def check_time_order(self) -> Self:
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class FlightSearch(BaseModel):
    departure_airport: int | None = None
    arrival_airport: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, ge=0)
    max_price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, ge=0)
    flight_class: FlightClass | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def assume_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else _to_utc(v)
