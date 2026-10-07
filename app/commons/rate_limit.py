from ..redis_client import redis_client
from .errors import ApiError


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Allow `limit` calls per `window_seconds` for this key, else raise 429.

    A fixed window: the first call starts a timer, and the count resets when
    it ends. Simple, but a client can use its limit at the end of one window
    and again at the start of the next, so the real worst case is twice the
    limit in a short burst. A sliding window would fix that and cost more.

    Every call is counted, including the ones that are refused."""
    pipe = redis_client.pipeline(transaction=True)  # MULTI/EXEC: all three run together
    pipe.incr(key)
    # NX: set the expiry only if the key has none. Otherwise every call would
    # push the deadline back and a steady trickle of calls would never reset.
    # Doing INCR and EXPIRE as separate commands could leave a counter with no
    # expiry if the process died between them, blocking that key forever.
    pipe.expire(key, window_seconds, nx=True)
    pipe.ttl(key)
    count, _, ttl = pipe.execute()

    if count > limit:
        retry_after = max(ttl, 1)
        raise ApiError(
            429,
            "rate_limited",
            "Too many requests. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
