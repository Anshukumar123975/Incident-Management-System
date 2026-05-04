import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def configure_structlog():
    """
    Sets up structlog for JSON structured logging.
    Every log line is valid JSON with consistent fields.
    In production these ship to Datadog/Loki for aggregation.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a correlation_id into every request.
    This ID threads a single signal through ingestion -> queue -> worker -> DB.
    Makes distributed debugging possible: grep logs by correlation_id.
    """
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


def get_logger(name: str = "ims"):
    return structlog.get_logger(name)