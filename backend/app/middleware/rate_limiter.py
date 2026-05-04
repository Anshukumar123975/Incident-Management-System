import time
import uuid
from fastapi import Request, HTTPException, status
from app.db.redis import get_redis
from app.config import get_settings

settings = get_settings()


async def ingest_rate_limit(request: Request):
    """
    Sliding window rate limiter for the ingest endpoint.
    Allows RATE_LIMIT_INGEST requests per second per IP.
    Uses Redis sorted sets — each request is a scored member.
    """
    await _check_rate_limit(
        request,
        limit=settings.RATE_LIMIT_INGEST,
        window=settings.RATE_LIMIT_WINDOW_SECONDS,
        prefix="rl:ingest",
    )


async def management_rate_limit(request: Request):
    """
    Sliding window rate limiter for management endpoints.
    More restrictive than ingest — prevents dashboard scraping.
    """
    await _check_rate_limit(
        request,
        limit=settings.RATE_LIMIT_MANAGEMENT,
        window=settings.RATE_LIMIT_WINDOW_SECONDS,
        prefix="rl:mgmt",
    )


async def _check_rate_limit(request: Request, limit: int, window: int, prefix: str):
    """
    Sliding window implementation using Redis sorted sets.
    Key: {prefix}:{client_ip}
    Score: current timestamp
    Member: unique UUID per request

    On each request:
    1. Remove entries older than the window
    2. Add current request
    3. Count entries — if > limit, reject with 429
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{prefix}:{client_ip}"
    now = time.time()
    window_start = now - window

    redis = get_redis()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(uuid.uuid4()): now})
        pipe.zcard(key)
        pipe.expire(key, window * 2)
        results = await pipe.execute()

    request_count = results[2]

    if request_count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {limit} requests per {window}s.",
            headers={"Retry-After": str(window)},
        )