import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from app.db.postgres import AsyncSessionLocal
from app.db.mongo import get_signals_collection
from app.db.redis import get_redis
from app.models.work_item import WorkItem, WorkItemResponse, WorkItemStatusUpdate, WorkItemListResponse
from app.models.rca import RCARecord
from app.models.events import WorkItemEvent, WorkItemEventResponse
from app.core.state_machine import WorkItemStateMachine, InvalidTransitionError
from app.core.processor import get_work_item_lock
from app.middleware.auth import require_api_key
from app.middleware.rate_limiter import management_rate_limit

router = APIRouter()


@router.get(
    "/incidents",
    response_model=WorkItemListResponse,
    dependencies=[Depends(management_rate_limit)],
    summary="List all incidents sorted by severity",
)
async def list_incidents():
    """
    Returns all Work Items sorted by severity (P0 first) then creation time.
    Serves from Redis cache (2s TTL) to avoid hammering Postgres on every UI refresh.
    Cache miss falls through to Postgres and refreshes the cache.
    """
    redis = get_redis()
    cache_key = "incidents:all"

    # Try Redis cache first
    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        return WorkItemListResponse(items=data["items"], total=data["total"])

    # Cache miss — query Postgres
    async with AsyncSessionLocal() as session:
        severity_order = {"P0": 0, "P1": 1, "P2": 2}
        result = await session.execute(
            select(WorkItem).order_by(desc(WorkItem.created_at))
        )
        items = result.scalars().all()

        # Sort by severity priority then time
        items_sorted = sorted(
            items,
            key=lambda x: (severity_order.get(x.severity, 99),)
        )

        response_items = [WorkItemResponse.model_validate(i) for i in items_sorted]

        # Refresh Redis cache
        cache_data = {
            "items": [i.model_dump(mode="json") for i in response_items],
            "total": len(response_items),
        }
        await redis.set(cache_key, json.dumps(cache_data), ex=2)

        return WorkItemListResponse(items=response_items, total=len(response_items))


@router.get(
    "/incidents/{work_item_id}",
    dependencies=[Depends(management_rate_limit)],
    summary="Get incident detail with raw signals",
)
async def get_incident(work_item_id: UUID):
    """
    Returns Work Item detail + raw signals from MongoDB.
    The signals come from MongoDB (audit log) not Postgres.
    This is the correct separation — Postgres owns the Work Item,
    MongoDB owns every raw signal payload.
    """
    async with AsyncSessionLocal() as session:
        wi = await session.get(WorkItem, work_item_id)
        if not wi:
            raise HTTPException(status_code=404, detail="Work Item not found")

        # Fetch RCA if exists
        rca_result = await session.execute(
            select(RCARecord).where(RCARecord.work_item_id == work_item_id)
        )
        rca = rca_result.scalar_one_or_none()

    # Fetch raw signals from MongoDB
    col = get_signals_collection()
    cursor = col.find(
        {"work_item_id": str(work_item_id)},
        {"_id": 0}
    ).sort("received_at", -1).limit(100)
    signals = await cursor.to_list(length=100)

    return {
        "work_item": WorkItemResponse.model_validate(wi),
        "rca": rca,
        "signals": signals,
        "signal_count": len(signals),
    }


@router.patch(
    "/incidents/{work_item_id}",
    response_model=WorkItemResponse,
    dependencies=[Depends(require_api_key), Depends(management_rate_limit)],
    summary="Transition incident status",
)
async def update_incident_status(work_item_id: UUID, body: WorkItemStatusUpdate):
    """
    Transitions a Work Item through its lifecycle.
    Uses asyncio.Lock per Work Item to prevent race conditions
    when multiple engineers update the same incident concurrently.
    Rejects invalid transitions via WorkItemStateMachine.
    """
    lock = await get_work_item_lock(str(work_item_id))

    async with lock:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                wi = await session.get(WorkItem, work_item_id)
                if not wi:
                    raise HTTPException(status_code=404, detail="Work Item not found")

                # Fetch RCA if transitioning to CLOSED
                rca = None
                if body.status == "CLOSED":
                    rca_result = await session.execute(
                        select(RCARecord).where(RCARecord.work_item_id == work_item_id)
                    )
                    rca = rca_result.scalar_one_or_none()

                # State machine validates the transition
                sm = WorkItemStateMachine(wi.status)
                try:
                    new_status = sm.transition(body.status, rca)
                except (Exception) as e:
                    raise HTTPException(status_code=400, detail=str(e))

                old_status = wi.status
                wi.status = new_status.value

                # Record timeline event
                event = WorkItemEvent(
                    work_item_id=work_item_id,
                    event_type="STATUS_CHANGED",
                    old_value=old_status,
                    new_value=new_status.value,
                )
                session.add(event)

        # Reload the work item to get updated fields like updated_at
        wi = await session.get(WorkItem, work_item_id)

        # Invalidate Redis cache
        redis = get_redis()
        await redis.delete("incidents:all")
        await redis.publish("incidents", json.dumps({
            "id": str(work_item_id),
            "status": new_status.value,
            "event": "STATUS_CHANGED",
        }))

        return WorkItemResponse.model_validate(wi)


@router.get(
    "/incidents/{work_item_id}/timeline",
    dependencies=[Depends(management_rate_limit)],
    summary="Get incident audit timeline",
)
async def get_incident_timeline(work_item_id: UUID):
    """
    Returns chronological audit trail of all events on a Work Item.
    Useful for post-incident review — shows exactly what happened and when.
    """
    async with AsyncSessionLocal() as session:
        wi = await session.get(WorkItem, work_item_id)
        if not wi:
            raise HTTPException(status_code=404, detail="Work Item not found")

        result = await session.execute(
            select(WorkItemEvent)
            .where(WorkItemEvent.work_item_id == work_item_id)
            .order_by(WorkItemEvent.created_at.asc())
        )
        events = result.scalars().all()

    return {
        "work_item_id": str(work_item_id),
        "events": [WorkItemEventResponse.model_validate(e) for e in events],
        "total": len(events),
    }