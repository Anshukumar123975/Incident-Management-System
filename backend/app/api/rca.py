import json
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal
from app.db.redis import get_redis
from app.models.rca import RCARecord, RCASubmit, RCAResponse
from app.models.work_item import WorkItem, WorkItemResponse
from app.models.events import WorkItemEvent
from app.core.state_machine import WorkItemStateMachine
from app.core.processor import get_work_item_lock
from app.middleware.auth import require_api_key
from app.middleware.rate_limiter import management_rate_limit

router = APIRouter()


@router.post(
    "/rca",
    response_model=RCAResponse,
    dependencies=[Depends(require_api_key), Depends(management_rate_limit)],
    summary="Submit RCA and close incident",
)
async def submit_rca(body: RCASubmit):
    """
    Submits an RCA and automatically closes the Work Item.

    This is a transactional operation:
    1. Validate RCA completeness (Pydantic + state machine)
    2. Insert RCA record in Postgres
    3. Transition Work Item to RESOLVED then CLOSED (two steps)
    4. Calculate and store MTTR
    5. Invalidate Redis cache

    All steps happen in a single DB transaction.
    If any step fails, nothing is committed.
    """
    lock = await get_work_item_lock(str(body.work_item_id))

    async with lock:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Fetch Work Item
                wi = await session.get(WorkItem, body.work_item_id)
                if not wi:
                    raise HTTPException(status_code=404, detail="Work Item not found")

                # 2. Check RCA doesn't already exist
                existing = await session.execute(
                    select(RCARecord).where(RCARecord.work_item_id == body.work_item_id)
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(status_code=409, detail="RCA already submitted for this Work Item")

                # 3. Work Item must be RESOLVED before closing
                #    If INVESTIGATING, auto-advance to RESOLVED first
                if wi.status == "INVESTIGATING":
                    sm = WorkItemStateMachine(wi.status)
                    try:
                        sm.transition("RESOLVED")
                        wi.status = "RESOLVED"
                        session.add(WorkItemEvent(
                            work_item_id=wi.id,
                            event_type="STATUS_CHANGED",
                            old_value="INVESTIGATING",
                            new_value="RESOLVED",
                            note="Auto-advanced to RESOLVED on RCA submission",
                        ))
                    except Exception as e:
                        raise HTTPException(status_code=400, detail=str(e))

                # 4. Create RCA record
                rca = RCARecord(
                    work_item_id=body.work_item_id,
                    root_cause_category=body.root_cause_category,
                    fix_applied=body.fix_applied,
                    prevention_steps=body.prevention_steps,
                    incident_start=body.incident_start,
                    incident_end=body.incident_end,
                )
                session.add(rca)
                await session.flush()  # Get rca.id without committing

                # 5. Transition to CLOSED (state machine validates RCA completeness)
                sm = WorkItemStateMachine(wi.status)
                try:
                    sm.transition("CLOSED", rca)
                    wi.status = "CLOSED"
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))

                # 6. Calculate MTTR
                end_time = datetime.now(timezone.utc)
                mttr_seconds = (end_time - wi.start_time).total_seconds()
                wi.end_time = end_time
                wi.mttr_seconds = mttr_seconds

                # 7. Record timeline events
                session.add(WorkItemEvent(
                    work_item_id=wi.id,
                    event_type="RCA_SUBMITTED",
                    new_value=body.root_cause_category,
                    note=f"MTTR: {mttr_seconds:.0f}s ({mttr_seconds/60:.1f} min)",
                ))
                session.add(WorkItemEvent(
                    work_item_id=wi.id,
                    event_type="STATUS_CHANGED",
                    old_value="RESOLVED",
                    new_value="CLOSED",
                    note="Closed via RCA submission",
                ))

    # 8. Invalidate Redis cache + notify WebSocket clients
    redis = get_redis()
    await redis.delete("incidents:all")
    await redis.publish("incidents", json.dumps({
        "id":           str(wi.id),
        "status":       "CLOSED",
        "mttr_seconds": mttr_seconds,
        "event":        "INCIDENT_CLOSED",
    }))

    return RCAResponse(
        id=rca.id,
        work_item_id=rca.work_item_id,
        root_cause_category=rca.root_cause_category,
        fix_applied=rca.fix_applied,
        prevention_steps=rca.prevention_steps,
        incident_start=rca.incident_start,
        incident_end=rca.incident_end,
        submitted_at=rca.submitted_at,
        mttr_seconds=mttr_seconds,
    )