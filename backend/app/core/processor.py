import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from app.core.buffer import signal_buffer, BufferedSignal
from app.core.debouncer import get_or_create_work_item_id
from app.core.alerting import get_alert_strategy
from app.core.circuit_breaker import postgres_cb, mongo_cb
from app.db.postgres import AsyncSessionLocal
from app.db.mongo import get_signals_collection, get_dead_letter_collection
from app.db.redis import get_redis
from app.models.work_item import WorkItem
from app.config import get_settings
from sqlalchemy import select, update

settings = get_settings()

# Per Work Item lock — prevents race conditions on concurrent status updates
_work_item_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()  # protects the locks dict itself


async def get_work_item_lock(work_item_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if work_item_id not in _work_item_locks:
            _work_item_locks[work_item_id] = asyncio.Lock()
        return _work_item_locks[work_item_id]


async def _write_to_postgres_with_retry(work_item_id: str, component_id: str,
                                         component_type: str, severity: str,
                                         signal: BufferedSignal, should_create: bool):
    """Writes to Postgres with exponential backoff retry (3 attempts)."""
    for attempt in range(3):
        try:
            async with AsyncSessionLocal() as session:
                if should_create:
                    wi = WorkItem(
                        id=UUID(work_item_id),
                        component_id=component_id,
                        component_type=component_type,
                        severity=severity,
                        status="OPEN",
                        signal_count=1,
                        start_time=signal.received_at,
                    )
                    session.add(wi)
                    await session.flush()

                    from app.models.events import WorkItemEvent
                    event = WorkItemEvent(
                        work_item_id=UUID(work_item_id),
                        event_type="SIGNAL_RECEIVED",
                        new_value=signal.error_code,
                        note=signal.message,
                    )
                    session.add(event)
                else:
                    from sqlalchemy import update
                    await session.execute(
                        update(WorkItem)
                        .where(WorkItem.id == UUID(work_item_id))
                        .values(signal_count=WorkItem.signal_count + 1)
                    )
                    from app.models.events import WorkItemEvent
                    event = WorkItemEvent(
                        work_item_id=UUID(work_item_id),
                        event_type="SIGNAL_RECEIVED",
                        new_value=signal.error_code,
                        note=signal.message,
                    )
                    session.add(event)

                await session.commit()
                return  # success

        except Exception as e:
            import traceback
            print(f"[Processor] Postgres write attempt {attempt+1} failed: {e}")
            traceback.print_exc()
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                await _send_to_dead_letter(signal, work_item_id, str(e))

async def _send_to_dead_letter(signal: BufferedSignal, work_item_id: str, error: str):
    """Last resort — store failed signals in MongoDB dead_letter collection."""
    try:
        dlq = get_dead_letter_collection()
        await dlq.insert_one({
            "work_item_id":   work_item_id,
            "component_id":   signal.component_id,
            "component_type": signal.component_type,
            "error_code":     signal.error_code,
            "message":        signal.message,
            "received_at":    signal.received_at.isoformat(),
            "error":          error,
        })
    except Exception:
        print(f"[DLQ] CRITICAL: Could not write to dead letter queue for {signal.component_id}")


async def _write_signal_to_mongo(signal: BufferedSignal, work_item_id: str):
    """Writes raw signal to MongoDB audit log with retry."""
    doc = {
        "work_item_id":   work_item_id,
        "component_id":   signal.component_id,
        "component_type": signal.component_type,
        "error_code":     signal.error_code,
        "message":        signal.message,
        "severity":       signal.severity,
        "payload":        signal.payload,
        "received_at":    signal.received_at.isoformat(),
        "correlation_id": signal.correlation_id,
    }
    for attempt in range(3):
        try:
            col = get_signals_collection()
            await col.insert_one(doc)
            return
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                print(f"[Processor] MongoDB write failed after 3 attempts: {e}")


async def _update_redis_cache(work_item_id: str, component_id: str,
                               severity: str, status: str, signal_count: int):
    """Updates the Redis dashboard cache entry for this Work Item."""
    try:
        redis = get_redis()
        cache_key = f"wi:{work_item_id}"
        data = json.dumps({
            "id":           work_item_id,
            "component_id": component_id,
            "severity":     severity,
            "status":       status,
            "signal_count": signal_count,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        })
        await redis.set(cache_key, data, ex=300)  # 5 min TTL
        # Publish to WebSocket feed channel
        await redis.publish("incidents", data)
    except Exception as e:
        print(f"[Processor] Redis cache update failed: {e}")


async def process_signal(signal: BufferedSignal):
    """
    Core processing logic for a single signal.
    Called by each worker.
    """
    should_create, work_item_id = await get_or_create_work_item_id(signal.component_id)

    # Get or create the per-Work-Item lock to prevent race conditions
    lock = await get_work_item_lock(work_item_id)

    async with lock:
        # 1. Write to Postgres (source of truth)
        await _write_to_postgres_with_retry(
            work_item_id, signal.component_id, signal.component_type,
            signal.severity, signal, should_create
        )

        # 2. Write raw signal to MongoDB (audit log)
        await _write_signal_to_mongo(signal, work_item_id)

        # 3. Update Redis cache + publish to WebSocket
        await _update_redis_cache(
            work_item_id, signal.component_id,
            signal.severity, "OPEN", 1
        )

        # 4. Fire alert only when Work Item is first created
        if should_create:
            strategy = get_alert_strategy(signal.component_type)
            await strategy.send(
                work_item_id, signal.component_id,
                signal.severity, signal.message
            )


async def worker(worker_id: int):
    """
    Async worker that continuously drains the signal buffer.
    Each worker processes one signal at a time.
    8 workers run concurrently (configurable via WORKER_COUNT).
    """
    print(f"[Worker:{worker_id}] Started")
    while True:
        try:
            signal = await signal_buffer.get()
            await process_signal(signal)
            signal_buffer.task_done()
        except asyncio.CancelledError:
            print(f"[Worker:{worker_id}] Shutting down")
            break
        except Exception as e:
            print(f"[Worker:{worker_id}] Error processing signal: {e}")
            signal_buffer.task_done()


async def metrics_logger():
    """
    Prints throughput metrics every 5 seconds to stdout.
    Required by the spec: "print throughput metrics (Signals/sec) every 5 seconds"
    """
    while True:
        try:
            await asyncio.sleep(settings.METRICS_INTERVAL_SECONDS)
            throughput = signal_buffer.get_and_reset_throughput()
            rate = throughput / settings.METRICS_INTERVAL_SECONDS
            print(
                f"[Metrics] "
                f"signals/sec={rate:.1f} | "
                f"queue_depth={signal_buffer.depth} | "
                f"total_ingested={signal_buffer.total_ingested} | "
                f"dropped={signal_buffer.dropped}"
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Metrics] Error: {e}")


async def start_workers() -> list[asyncio.Task]:
    """Starts the worker pool and metrics logger. Called on app startup."""
    tasks = []
    for i in range(settings.WORKER_COUNT):
        task = asyncio.create_task(worker(i), name=f"worker-{i}")
        tasks.append(task)

    metrics_task = asyncio.create_task(metrics_logger(), name="metrics-logger")
    tasks.append(metrics_task)

    print(f"[Processor] Started {settings.WORKER_COUNT} workers + metrics logger")
    return tasks


async def stop_workers(tasks: list[asyncio.Task]):
    """Gracefully drains queue and cancels workers on shutdown."""
    print("[Processor] Draining queue before shutdown...")
    # Give workers 10 seconds to drain remaining signals
    try:
        await asyncio.wait_for(signal_buffer._queue.join(), timeout=10.0)
    except asyncio.TimeoutError:
        print(f"[Processor] Drain timeout — {signal_buffer.depth} signals remaining")

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("[Processor] All workers stopped")