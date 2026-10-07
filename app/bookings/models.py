from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
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
    # From the client's Idempotency-Key header. NULL when the request had none:
    # MySQL allows any number of NULLs in a unique index, so unkeyed bookings
    # never collide with each other.
    idempotency_key: Mapped[str | None] = mapped_column(String(64))

    # The database, not application code, is what guarantees that one key
    # produces at most one booking per user, however requests interleave.
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_bookings_user_id_idempotency_key"),
    )
