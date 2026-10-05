from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .enums import BookingStatus


class BookingCreate(BaseModel):
    flight_id: int
    seats_booked: int = Field(gt=0) 


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    flight_id: int
    seats_booked: int
    total_amount: Decimal
    status: BookingStatus
    created_at: datetime

