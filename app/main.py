from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .airports import models as airport_models
from .airports.router import router as airport_router
from .flights import models as flight_models
from .flights.router import router as flight_router
from .authentication import models
from .authentication.router import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bookme Replica")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_headers=["*"],
    allow_methods=["*"]
)

app.include_router(airport_router)
app.include_router(flight_router)
app.include_router(auth_router)
