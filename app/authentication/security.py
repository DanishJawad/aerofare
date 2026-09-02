import bcrypt
import jwt
from datetime import datetime, timezone, timedelta

from ..database import settings

class InvalidToken(Exception):
    pass

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(subject: str) -> str:
    payload = {"sub": subject,"iat": datetime.now(timezone.utc) , "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expiry_minutes)}

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.InvalidTokenError:
        raise InvalidToken()

    subject = payload.get("sub")

    if subject is None:
        raise InvalidToken()
    return subject

