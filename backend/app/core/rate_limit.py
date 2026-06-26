"""Simple Redis-based sliding window rate limiter.

Fallback: if Redis is unavailable, the limiter is disabled (fail-open).
"""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status
from app.db.redis_client import get_redis


async def check_rate_limit(
    request: Request,
    key_prefix: str = "rl",
    max_requests: int = 60,
    window_seconds: int = 60,
) -> None:
    """Check if the current request exceeds the rate limit.

    Uses a sliding window counter stored in Redis.
    Returns 429 Too Many Requests if the limit is exceeded.

    Args:
        request: FastAPI request (used to derive client IP).
        key_prefix: Redis key prefix (e.g. "rl:auth").
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: Sliding window size in seconds.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    window_start = now - window_seconds
    key = f"{key_prefix}:{client_ip}"

    try:
        redis = get_redis()

        # Remove entries outside the window
        await redis.zremrangebyscore(key, 0, window_start)

        # Count requests in current window
        count = await redis.zcard(key)

        if count >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请稍后再试（{max_requests}次/{window_seconds}秒）",
            )

        # Add current request
        await redis.zadd(key, {str(now): now})
        await redis.expire(key, window_seconds * 2)

    except HTTPException:
        raise
    except Exception:
        # Redis unavailable — fail open (allow request)
        pass


async def rate_limit_auth(request: Request) -> None:
    """Rate limiter for auth endpoints: 10 req/min per IP."""
    await check_rate_limit(request, "rl:auth", max_requests=10, window_seconds=60)


async def rate_limit_api(request: Request) -> None:
    """Rate limiter for general API: 60 req/min per IP."""
    await check_rate_limit(request, "rl:api", max_requests=60, window_seconds=60)
