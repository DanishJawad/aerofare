from sqlalchemy import Column, Integer, String
from ..database import Base

class Airport(Base):
    __tablename__ = "airports"

    id: int = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name: str = Column(String(50), index=True)
    city: str = Column(String(50), index=True)
    country: str = Column(String(50), index=True)