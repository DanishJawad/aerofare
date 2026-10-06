from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import PaymentStatus


class PaymentResponse(BaseModel):
    # Explicit example: see BookingResponse for why.
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "booking_id": 1,
                    "amount": "300.00",
                    "status": "completed",
                    "paid_at": "2030-01-01T06:00:00Z",
                    "created_at": "2030-01-01T06:00:00Z",
                }
            ]
        },
    )

    id: int
    booking_id: int
    amount: Decimal
    status: PaymentStatus
    paid_at: datetime | None
    created_at: datetime