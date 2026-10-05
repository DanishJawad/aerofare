from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    amount: Decimal
    status: PaymentStatus
    paid_at: datetime | None
    created_at: datetime