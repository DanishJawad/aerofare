from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import bcrypt
import jwt

from ..database import settings
from ..redis_client import redis_client


class InvalidToken(Exception):
    pass


@dataclass(frozen=True)
class TokenPayload:
    subject: str
    jti: str
    expires_at: datetime
    version: int  # the user's token_version when this token was issued


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(subject: str, version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expiry_minutes),
        "jti": str(uuid4()),  # unique id for this token; what the blacklist keys on
        "ver": version,
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp", "jti"]},
        )
    except jwt.InvalidTokenError:
        raise InvalidToken()

    if is_token_revoked(payload["jti"]):
        raise InvalidToken()

    return TokenPayload(
        subject=payload["sub"],
        jti=payload["jti"],
        # jwt.decode gives exp back as a Unix timestamp (int), not a datetime
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        # Tokens issued before this claim existed count as version 0.
        version=payload.get("ver", 0),
    )


def revoke_token(jti: str, expires_at: datetime) -> None:
    """Blacklist this token's jti until it would have expired anyway.
    SET with EX writes the key AND its TTL in one atomic command; Redis deletes
    it by itself once the TTL hits zero, so a revoked token never needs manual
    cleanup. (This replaces SETEX, which redis-py now marks as deprecated.)"""
    ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl_seconds > 0:
        redis_client.set(f"blacklist:{jti}", "1", ex=ttl_seconds)


def is_token_revoked(jti: str) -> bool:
    return redis_client.exists(f"blacklist:{jti}") == 1
