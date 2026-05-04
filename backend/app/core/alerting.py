from abc import ABC, abstractmethod
from datetime import datetime, timezone


class AlertStrategy(ABC):
    @abstractmethod
    async def send(self, work_item_id: str, component_id: str, severity: str, message: str):
        pass


class P0Alert(AlertStrategy):
    async def send(self, work_item_id: str, component_id: str, severity: str, message: str):
        print(f"[ALERT:P0] CRITICAL - {component_id} | WorkItem={work_item_id} | {message} | time={datetime.now(timezone.utc).isoformat()}")


class P1Alert(AlertStrategy):
    async def send(self, work_item_id: str, component_id: str, severity: str, message: str):
        print(f"[ALERT:P1] HIGH - {component_id} | WorkItem={work_item_id} | {message} | time={datetime.now(timezone.utc).isoformat()}")


class P2Alert(AlertStrategy):
    async def send(self, work_item_id: str, component_id: str, severity: str, message: str):
        print(f"[ALERT:P2] MEDIUM - {component_id} | WorkItem={work_item_id} | {message} | time={datetime.now(timezone.utc).isoformat()}")


ALERT_MAP: dict[str, type[AlertStrategy]] = {
    "RDBMS":       P0Alert,
    "API":         P0Alert,
    "MCP_HOST":    P1Alert,
    "ASYNC_QUEUE": P1Alert,
    "CACHE":       P2Alert,
    "NOSQL":       P2Alert,
}


def get_alert_strategy(component_type: str) -> AlertStrategy:
    return ALERT_MAP.get(component_type, P2Alert)()