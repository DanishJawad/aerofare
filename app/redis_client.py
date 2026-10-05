import redis

from .database import settings

# One shared client for the whole app, built once at import time — same pattern
# as the SQLAlchemy `engine` in database.py. redis-py pools connections
# internally, and the connection itself is lazy: this line does not talk to
# Redis yet, the first command (SETEX / EXISTS) does.
redis_client: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)
