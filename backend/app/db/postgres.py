from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

# Connection pool: min 5, max 20 connections
# pool_pre_ping checks connection health before use
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=15,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_postgres() -> bool:
    """Health check — verifies actual DB connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False