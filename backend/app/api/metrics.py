from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from app.core.buffer import signal_buffer
from app.core.circuit_breaker import postgres_cb, mongo_cb, redis_cb

router = APIRouter()


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus-compatible metrics endpoint",
    description="Exposes system metrics in Prometheus text format. No auth required (standard convention).",
)
async def metrics():
    """
    Prometheus-compatible /metrics endpoint.
    In production this is scraped by a Prometheus server every 15s
    and visualized in Grafana dashboards.

    Metrics exposed:
    - ims_signals_ingested_total: total signals received
    - ims_signals_dropped_total: signals dropped due to queue full
    - ims_queue_depth: current in-memory queue size
    - ims_circuit_breaker_state: 0=CLOSED, 1=HALF_OPEN, 2=OPEN per DB
    """
    state_map = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}

    pg_state    = state_map[postgres_cb.state.value]
    mongo_state = state_map[mongo_cb.state.value]
    redis_state = state_map[redis_cb.state.value]

    output = f"""# HELP ims_signals_ingested_total Total signals received by the ingest API
# TYPE ims_signals_ingested_total counter
ims_signals_ingested_total {signal_buffer.total_ingested}

# HELP ims_signals_dropped_total Signals dropped due to queue overflow
# TYPE ims_signals_dropped_total counter
ims_signals_dropped_total {signal_buffer.dropped}

# HELP ims_queue_depth Current number of signals in the processing queue
# TYPE ims_queue_depth gauge
ims_queue_depth {signal_buffer.depth}

# HELP ims_circuit_breaker_state Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
# TYPE ims_circuit_breaker_state gauge
ims_circuit_breaker_state{{db="postgres"}} {pg_state}
ims_circuit_breaker_state{{db="mongo"}} {mongo_state}
ims_circuit_breaker_state{{db="redis"}} {redis_state}
"""
    return output