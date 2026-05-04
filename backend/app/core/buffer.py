import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BufferedSignal:
    """A signal sitting in the in-memory queue waiting to be processed."""
    component_id:   str
    component_type: str
    error_code:     str
    message:        str
    severity:       str
    payload:        dict | None
    received_at:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = ""


class SignalBuffer:
    """
    In-memory ring buffer using asyncio.Queue.

    Design:
    - maxsize caps memory usage
    - put_nowait() never blocks the ingestion endpoint
    - If full, signal is DROPPED and counted — system stays alive
    - Backpressure: producers never blocked, workers drain at own pace
    """

    def __init__(self, maxsize: int = 50000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._dropped: int = 0
        self._total_ingested: int = 0
        self._ingested_since_last_log: int = 0

    def put(self, signal: BufferedSignal) -> bool:
        """Non-blocking enqueue. Returns True if queued, False if dropped."""
        try:
            self._queue.put_nowait(signal)
            self._total_ingested += 1
            self._ingested_since_last_log += 1
            return True
        except asyncio.QueueFull:
            self._dropped += 1
            return False

    async def get(self) -> BufferedSignal:
        """Blocking dequeue — called by workers."""
        return await self._queue.get()

    def task_done(self):
        self._queue.task_done()

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def total_ingested(self) -> int:
        return self._total_ingested

    def get_and_reset_throughput(self) -> int:
        count = self._ingested_since_last_log
        self._ingested_since_last_log = 0
        return count


# Module-level singleton
signal_buffer = SignalBuffer()