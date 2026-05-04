import uuid
from fastapi import APIRouter, Depends, Request
from app.models.signal import SignalIngest, SignalIngestResponse
from app.core.buffer import signal_buffer, BufferedSignal
from app.middleware.auth import require_api_key
from app.middleware.rate_limiter import ingest_rate_limit

router = APIRouter()


@router.post(
    "/signals",
    response_model=SignalIngestResponse,
    status_code=202,
    summary="Ingest a signal",
    description="Accepts a signal and queues it for async processing. Never blocks on DB writes.",
    dependencies=[Depends(require_api_key), Depends(ingest_rate_limit)],
)
async def ingest_signal(signal: SignalIngest, request: Request):
    """
    The ingest endpoint contract:
    - Validates input (Pydantic strict mode)
    - Drops signal onto in-memory queue (non-blocking)
    - Returns 202 Accepted immediately
    - NEVER waits for DB writes

    This is the backpressure boundary:
    If the queue is full, the signal is dropped and counted.
    The system stays alive even if all DBs are slow/down.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    buffered = BufferedSignal(
        component_id=signal.component_id,
        component_type=signal.component_type,
        error_code=signal.error_code,
        message=signal.message,
        severity=signal.severity,
        payload=signal.payload,
        correlation_id=correlation_id,
    )

    queued = signal_buffer.put(buffered)

    if not queued:
        # Queue full — log drop but still return 202
        # We don't return 503 here because that would cause producers
        # to retry and make the overload worse (cascading failure)
        print(f"[Ingest] DROPPED signal for {signal.component_id} — queue full "
              f"(depth={signal_buffer.depth}, total_dropped={signal_buffer.dropped})")

    return SignalIngestResponse(
        status="accepted",
        message="Signal queued for processing" if queued else "Signal dropped — queue full",
        component_id=signal.component_id,
    )