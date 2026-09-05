from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .airports.router import router as airport_router
from .flights.router import router as flight_router
from .authentication.router import router as auth_router

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
