from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .airports.router import router as airport_router
from .authentication.router import router as auth_router
from .bookings import models as _booking_models  # noqa: F401 - registers the table
from .bookings.router import router as booking_router
from .flights.router import router as flight_router
from .payments import models as _payment_models  # noqa: F401 - registers the table
from .payments.router import router as payment_router

app = FastAPI(title="Aerofare")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_headers=["*"],
    allow_methods=["*"]
)

app.include_router(airport_router)
app.include_router(flight_router)
app.include_router(auth_router)
app.include_router(booking_router)
app.include_router(payment_router)
