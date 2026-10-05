from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from ..commons.mixins import TimestampMixin
from ..database import Base
from .enums import BookingStatus


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    seats_booked: Mapped[int]
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, native_enum=False, length=20)
    )
