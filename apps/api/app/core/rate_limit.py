"""A small in-memory sliding-window rate limiter.

Good enough for a single API process. With several workers or instances, each keeps its own
counters, so put a shared limiter (Redis, or your reverse proxy) in front for production.
See docs/SECURITY_AND_PRIVACY.md.
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitError

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _hits.clear()


def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization")
    if auth:
        return f"tok:{hash(auth)}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def rate_limit(name: str, limit_attr: str, window_attr: str):
    """Build a FastAPI dependency limiting `name` using Settings.<limit_attr>/<window_attr>."""

    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = getattr(settings, limit_attr)
        window = getattr(settings, window_attr)
        key = f"{name}:{_client_key(request)}"
        now = time.monotonic()
        bucket = _hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitError("Too many requests, slow down", details={"retry_after_seconds": window})
        bucket.append(now)

    return dependency


sync_limiter = rate_limit("sync", "sync_rate_limit", "sync_rate_window_seconds")
auth_limiter = rate_limit("auth", "auth_rate_limit", "auth_rate_window_seconds")
