import asyncio
from datetime import datetime, timezone
from enum import Enum


class CircuitState(Enum):
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(Exception):
    pass


class CircuitBreaker:
    """
    Protects a DB client from cascading failures.
    CLOSED -> OPEN after failure_threshold consecutive failures.
    OPEN -> HALF_OPEN after recovery_timeout seconds.
    HALF_OPEN -> CLOSED on success, -> OPEN on failure.
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro):
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        self._state = CircuitState.HALF_OPEN
                        print(f"[CircuitBreaker:{self.name}] OPEN -> HALF_OPEN")
                    else:
                        raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
        try:
            result = await coro
            await self._on_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                print(f"[CircuitBreaker:{self.name}] HALF_OPEN -> CLOSED")

    async def _on_failure(self, error):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                print(f"[CircuitBreaker:{self.name}] HALF_OPEN -> OPEN")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                print(f"[CircuitBreaker:{self.name}] CLOSED -> OPEN ({self._failure_count} failures)")

    def get_status(self) -> dict:
        return {"name": self.name, "state": self._state.value, "failure_count": self._failure_count}


from app.config import get_settings
_s = get_settings()
postgres_cb = CircuitBreaker("postgres", _s.CB_FAILURE_THRESHOLD, _s.CB_RECOVERY_TIMEOUT_SECONDS)
mongo_cb    = CircuitBreaker("mongo",    _s.CB_FAILURE_THRESHOLD, _s.CB_RECOVERY_TIMEOUT_SECONDS)
redis_cb    = CircuitBreaker("redis",    _s.CB_FAILURE_THRESHOLD, _s.CB_RECOVERY_TIMEOUT_SECONDS)