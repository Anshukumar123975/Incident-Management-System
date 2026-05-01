import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Returns the shared Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def check_redis() -> bool:
    """Health check — verifies actual Redis connectivity."""
    try:
        client = get_redis()
        await client.ping()
        return True
    except Exception:
        return False


async def close_redis():
    """Called on app shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None