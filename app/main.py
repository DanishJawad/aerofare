from fastapi import FastAPI
from .database import engine, Base
from .airports import models as airport_models
from .airports.router import router as airport_router

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(airport_router)