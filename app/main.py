from fastapi import FastAPI

from .database import engine, Base
from .airports import models as airport_models
from .airports.router import router as airport_router
from .flights import models as flight_models
from .flights.router import router as flight_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bookme Replica")

app.include_router(airport_router)
app.include_router(flight_router)