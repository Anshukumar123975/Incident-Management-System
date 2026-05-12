from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_KEY: str = "dev-api-key-change-in-production"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://ims_user:ims_password@postgres:5432/ims_db"

    # MongoDB
    MONGO_URL: str = "mongodb://ims_user:ims_password@mongo:27017/ims_db"
    MONGO_DB: str = "ims_db"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Queue
    QUEUE_MAX_SIZE: int = 50000
    WORKER_COUNT: int = 8

    # Rate Limiting
    RATE_LIMIT_INGEST: int = 1000
    RATE_LIMIT_MANAGEMENT: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 1

    # Debounce
    DEBOUNCE_WINDOW_SECONDS: int = 10
    DEBOUNCE_THRESHOLD: int = 100

    # Circuit Breaker
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIMEOUT_SECONDS: int = 30

    # Observability
    METRICS_INTERVAL_SECONDS: int = 5
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:80,http://localhost"

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",")]
        extras = [
            "http://localhost",
            "http://localhost:80",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:80",
        ]
        return list(set(origins + extras))

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()