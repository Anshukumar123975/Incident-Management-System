from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

# Module-level client — shared across the app lifetime
_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URL)
    return _client


def get_mongo_db():
    """Returns the IMS database handle."""
    return get_mongo_client()[settings.MONGO_DB]


def get_signals_collection():
    return get_mongo_db()["signals"]


def get_dead_letter_collection():
    return get_mongo_db()["dead_letter"]


async def check_mongo() -> bool:
    """Health check — verifies actual MongoDB connectivity."""
    try:
        await get_mongo_client().admin.command("ping")
        return True
    except Exception:
        return False


async def close_mongo():
    """Called on app shutdown to close the connection pool."""
    global _client
    if _client is not None:
        _client.close()
        _client = None