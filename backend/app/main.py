from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings
from app.db.postgres import check_postgres
from app.db.mongo import check_mongo, close_mongo
from app.db.redis import check_redis, close_redis
from app.middleware.logging_config import configure_structlog, CorrelationIDMiddleware
from app.core.processor import start_workers, stop_workers

settings = get_settings()

# Worker task handles — kept for graceful shutdown
_worker_tasks = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    configure_structlog()
    print("Starting IMS backend...")
    print(f"Environment: {settings.APP_ENV}")

    pg_ok    = await check_postgres()
    mongo_ok = await check_mongo()
    redis_ok = await check_redis()

    print(f"PostgreSQL: {'OK' if pg_ok else 'FAILED'}")
    print(f"MongoDB:    {'OK' if mongo_ok else 'FAILED'}")
    print(f"Redis:      {'OK' if redis_ok else 'FAILED'}")

    if not all([pg_ok, mongo_ok, redis_ok]):
        print("WARNING: One or more DB connections failed on startup.")

    # Start worker pool + metrics logger
    global _worker_tasks
    _worker_tasks = await start_workers()

    yield  # App runs here

    # ── Shutdown ─────────────────────────────────────────────
    print("Shutting down IMS backend...")
    await stop_workers(_worker_tasks)
    await close_mongo()
    await close_redis()
    print("Shutdown complete.")


# ── App factory ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Incident Management System",
    description="Mission-critical IMS for distributed stack monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost first) ──────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIDMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────
from app.api.ingest    import router as ingest_router
from app.api.incidents import router as incidents_router
from app.api.rca       import router as rca_router
from app.api.ws        import router as ws_router
from app.api.metrics   import router as metrics_router
from app.api.analytics import router as analytics_router

app.include_router(ingest_router,    tags=["Ingestion"])
app.include_router(incidents_router, tags=["Incidents"])
app.include_router(rca_router,       tags=["RCA"])
app.include_router(ws_router,        tags=["WebSocket"])
app.include_router(metrics_router,   tags=["Observability"])
app.include_router(analytics_router, tags=["Analytics"])


@app.get("/health", tags=["Observability"])
async def health_check():
    pg_ok    = await check_postgres()
    mongo_ok = await check_mongo()
    redis_ok = await check_redis()
    all_ok   = all([pg_ok, mongo_ok, redis_ok])
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded",
                 "postgres": pg_ok, "mongo": mongo_ok, "redis": redis_ok},
        status_code=200 if all_ok else 503,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "IMS API running. See /docs for API reference."}