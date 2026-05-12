from fastapi import APIRouter, Depends
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal
from app.middleware.rate_limiter import management_rate_limit

router = APIRouter()

@router.get(
    "/analytics/mttr",
    dependencies=[Depends(management_rate_limit)],
    summary="MTTR analytics by component type",
)
async def get_mttr_analytics(window_days: int = 7):
    """
    Returns average MTTR grouped by component type over a rolling window.
    Uses TimescaleDB time_bucket for efficient time-series aggregation.
    Shows: which component types take longest to recover from incidents.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT
                    component_type,
                    COUNT(*) as incident_count,
                    AVG(mttr_seconds) as avg_mttr_seconds,
                    MIN(mttr_seconds) as min_mttr_seconds,
                    MAX(mttr_seconds) as max_mttr_seconds
                FROM work_items
                WHERE
                    status = 'CLOSED'
                    AND mttr_seconds IS NOT NULL
                    AND created_at >= NOW() - INTERVAL :window
                GROUP BY component_type
                ORDER BY avg_mttr_seconds DESC
            """),
            {"window": f"{window_days} days"}
        )
        rows = result.mappings().all()

    return {
        "window_days": window_days,
        "data": [
            {
                "component_type":    r["component_type"],
                "incident_count":    r["incident_count"],
                "avg_mttr_seconds":  round(float(r["avg_mttr_seconds"]), 1) if r["avg_mttr_seconds"] else None,
                "avg_mttr_minutes":  round(float(r["avg_mttr_seconds"]) / 60, 1) if r["avg_mttr_seconds"] else None,
                "min_mttr_seconds":  round(float(r["min_mttr_seconds"]), 1) if r["min_mttr_seconds"] else None,
                "max_mttr_seconds":  round(float(r["max_mttr_seconds"]), 1) if r["max_mttr_seconds"] else None,
            }
            for r in rows
        ],
    }