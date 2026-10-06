from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import BookingStatus


class BookingCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"flight_id": 1, "seats_booked": 2}]})

    flight_id: int
    seats_booked: int = Field(gt=0) 


class BookingResponse(BaseModel):
    # An explicit example because Swagger's auto-generated one for a Decimal
    # field is a number with about 200 digits.
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "user_id": 1,
                    "flight_id": 1,
                    "seats_booked": 2,
                    "total_amount": "300.00",
                    "status": "confirmed",
                    "created_at": "2030-01-01T06:00:00Z",
                }
            ]
        },
    )

    id: int
    user_id: int
    flight_id: int
    seats_booked: int
    total_amount: Decimal
    status: BookingStatus
    created_at: datetime

