"""
Simple in-memory rate limiter middleware.

Configure via RATE_LIMIT_ENABLED (default: 1) and RATE_LIMIT_PER_MINUTE (default: 200).
Auth endpoints use RATE_LIMIT_AUTH_PER_MINUTE (default: 10).
"""

from __future__ import annotations
import os
import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_counts: dict[str, list[float]] = defaultdict(list)
_window = 60  # seconds


def _clean_old(ts_list: list[float], window: int) -> None:
    now = time.time()
    cutoff = now - window
    while ts_list and ts_list[0] < cutoff:
        ts_list.pop(0)


def is_rate_limited(key: str, limit: int) -> bool:
    """Return True if the key has exceeded the limit within the window."""
    if limit <= 0:
        return False
    with _lock:
        _clean_old(_counts[key], _window)
        if len(_counts[key]) >= limit:
            return True
        _counts[key].append(time.time())
        return False


def rate_limit_key() -> str:
    """Get rate limit key from request (IP)."""
    from flask import request

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit_exceeded_response(limit: int):
    """Return 429 response."""
    from flask import jsonify

    return jsonify({"error": "rate limit exceeded", "retry_after": 60}), 429


def rate_limit_decorator(limit_per_minute: int, key_prefix: str = ""):
    """Decorator to rate limit a route."""

    def decorator(fn):
        from functools import wraps

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if os.getenv("RATE_LIMIT_ENABLED", "1") != "1":
                return fn(*args, **kwargs)
            prefix = key_prefix or str(limit_per_minute)
            key = f"{prefix}:{rate_limit_key()}"
            if is_rate_limited(key, limit_per_minute):
                return rate_limit_exceeded_response(limit_per_minute)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
