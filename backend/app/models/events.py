from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from app.db.postgres import Base


# ── SQLAlchemy ORM Model ──────────────────────────────────────────────────
class WorkItemEvent(Base):
    """
    Immutable audit trail for every notable event on a Work Item.
    Powers the /incidents/{id}/timeline endpoint.
    Event types: STATUS_CHANGED | RCA_SUBMITTED | ESCALATED | ANOMALY_DETECTED
    """
    __tablename__ = "work_item_events"

    id:           Mapped[UUID]           = mapped_column(primary_key=True, default=uuid4)
    work_item_id: Mapped[UUID]           = mapped_column(ForeignKey("work_items.id"), nullable=False)
    event_type:   Mapped[str]            = mapped_column(String, nullable=False)
    old_value:    Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    new_value:    Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    note:         Mapped[Optional[str]]  = mapped_column(String, nullable=True)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Pydantic Schema ───────────────────────────────────────────────────────
class WorkItemEventResponse(BaseModel):
    id:           UUID
    work_item_id: UUID
    event_type:   str
    old_value:    Optional[str] = None
    new_value:    Optional[str] = None
    note:         Optional[str] = None
    created_at:   datetime

    model_config = {"from_attributes": True}