from collections.abc import Generator
from typing import Annotated, Literal

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    algorithm: str
    secret_key: str
    access_token_expiry_minutes: int
    redis_url: str
    log_level: str = "INFO"
    log_format: Literal["pretty", "json"] = "pretty"
    # Defaults match Mailpit running on this machine (SMTP on 1025).
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "Aerofare <noreply@aerofare.local>"
    # Where the React app is served: password reset emails link to it.
    frontend_url: str = "http://localhost:5173"

settings = Settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session]:
    with SessionLocal() as db:
        yield db

DbSession = Annotated[Session, Depends(get_db)]