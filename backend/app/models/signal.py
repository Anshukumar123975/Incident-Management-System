from datetime import datetime, timezone
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


COMPONENT_SEVERITY_MAP = {
    "RDBMS":       "P0",
    "API":         "P0",
    "MCP_HOST":    "P1",
    "ASYNC_QUEUE": "P1",
    "CACHE":       "P2",
    "NOSQL":       "P2",
}

VALID_COMPONENT_TYPES = list(COMPONENT_SEVERITY_MAP.keys())


class SignalIngest(BaseModel):
    """
    Inbound signal payload from any producer.
    Validated strictly — bad signals are rejected at the gate.
    """
    component_id:   str  = Field(..., min_length=1, max_length=100)
    component_type: str  = Field(...)
    error_code:     str  = Field(..., min_length=1, max_length=100)
    message:        str  = Field(..., min_length=1, max_length=1000)
    payload:        Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_component_type(self):
        if self.component_type not in VALID_COMPONENT_TYPES:
            raise ValueError(f"component_type must be one of {VALID_COMPONENT_TYPES}")
        return self

    @property
    def severity(self) -> str:
        return COMPONENT_SEVERITY_MAP[self.component_type]


class SignalDocument(BaseModel):
    """Stored in MongoDB — immutable audit log entry."""
    work_item_id:   str
    component_id:   str
    component_type: str
    error_code:     str
    message:        str
    severity:       str
    payload:        Optional[dict[str, Any]] = None
    received_at:    datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalIngestResponse(BaseModel):
    status:       str = "accepted"
    message:      str = "Signal queued for processing"
    component_id: str