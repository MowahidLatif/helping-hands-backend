import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
_client = None


def r():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client
