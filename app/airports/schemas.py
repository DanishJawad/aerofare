from pydantic import BaseModel, ConfigDict

class AirportCreate(BaseModel):
    name: str
    city: str
    country: str

class AirportUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    country: str | None = None

class AirportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str
    country: str