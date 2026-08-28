from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

class Airport(Base):
    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    city: Mapped[str] = mapped_column(String(50), index=True)
    country: Mapped[str] = mapped_column(String(50), index=True)