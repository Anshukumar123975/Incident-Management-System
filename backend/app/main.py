from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.db.postgres import check_postgres
from app.db.mongo import check_mongo, close_mongo
from app.db.redis import check_redis, close_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: verify all DB connections are live.
    Shutdown: cleanly close connection pools.
    """
    print("Starting IMS backend...")
    print(f"Environment: {settings.APP_ENV}")

    # Verify DB connectivity on startup
    pg_ok = await check_postgres()
    mongo_ok = await check_mongo()
    redis_ok = await check_redis()

    print(f"PostgreSQL: {'OK' if pg_ok else 'FAILED'}")
    print(f"MongoDB:    {'OK' if mongo_ok else 'FAILED'}")
    print(f"Redis:      {'OK' if redis_ok else 'FAILED'}")

    if not all([pg_ok, mongo_ok, redis_ok]):
        print("WARNING: One or more DB connections failed on startup.")

    yield  # App runs here

    # Shutdown: close connections
    print("Shutting down IMS backend...")
    await close_mongo()
    await close_redis()
    print("Connections closed.")


# ── App factory ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Incident Management System",
    description="Mission-critical IMS for distributed stack monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────

# GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS — strict origin whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Observability"])
async def health_check():
    """
    Checks actual connectivity to all three databases.
    Returns 200 if healthy, 503 if any DB is down.
    Used by Docker health checks and monitoring systems.
    """
    pg_ok = await check_postgres()
    mongo_ok = await check_mongo()
    redis_ok = await check_redis()

    all_healthy = all([pg_ok, mongo_ok, redis_ok])

    payload = {
        "status": "ok" if all_healthy else "degraded",
        "postgres": pg_ok,
        "mongo": mongo_ok,
        "redis": redis_ok,
    }

    return JSONResponse(
        content=payload,
        status_code=200 if all_healthy else 503,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "IMS API running. See /docs for API reference."}