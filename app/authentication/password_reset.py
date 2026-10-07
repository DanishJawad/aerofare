import hashlib
import secrets

from ..redis_client import redis_client

RESET_TOKEN_TTL_SECONDS = 15 * 60


def _key(token: str) -> str:
    # Redis holds a SHA-256 hash of the token, never the token. Anyone who can
    # read Redis (a backup, a leaked dump, a stray KEYS command) then sees
    # hashes that cannot be turned into working reset links. A fast hash is
    # enough here, unlike for passwords: the token is 256 random bits, so there
    # is nothing to guess and nothing for a slow hash to protect.
    return "pwreset:" + hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(user_id: int) -> str:
    """Make a one-time token for this user. It expires on its own: Redis
    deletes the key when the TTL runs out, so there is nothing to clean up."""
    token = secrets.token_urlsafe(32)
    redis_client.set(_key(token), str(user_id), ex=RESET_TOKEN_TTL_SECONDS)
    return token


def consume_reset_token(token: str) -> int | None:
    """Return the user id the token was issued for, and destroy the token.

    GETDEL reads and deletes in one atomic command, so two requests that
    arrive together with the same token cannot both succeed: only one of them
    gets a value back. (GET then DELETE as two steps would allow both.)
    None means unknown, expired or already used."""
    value = redis_client.getdel(_key(token))
    return int(value) if value is not None else None
