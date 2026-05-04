from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, Integer, Boolean, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, Field
from app.db.postgres import Base


# ── SQLAlchemy ORM Model ──────────────────────────────────────────────────
class WorkItem(Base):
    __tablename__ = "work_items"

    id:             Mapped[UUID]    = mapped_column(primary_key=True, default=uuid4)
    component_id:   Mapped[str]     = mapped_column(String, nullable=False)
    component_type: Mapped[str]     = mapped_column(String, nullable=False)
    severity:       Mapped[str]     = mapped_column(String, nullable=False)
    status:         Mapped[str]     = mapped_column(String, nullable=False, default="OPEN")
    signal_count:   Mapped[int]     = mapped_column(Integer, nullable=False, default=1)
    is_anomaly:     Mapped[bool]    = mapped_column(Boolean, nullable=False, default=False)
    start_time:     Mapped[datetime]= mapped_column(DateTime(timezone=True), nullable=False)
    end_time:       Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    mttr_seconds:   Mapped[Optional[float]]    = mapped_column(Float, nullable=True)
    created_at:     Mapped[datetime]= mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:     Mapped[datetime]= mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Pydantic Schemas ──────────────────────────────────────────────────────

class WorkItemResponse(BaseModel):
    id:             UUID
    component_id:   str
    component_type: str
    severity:       str
    status:         str
    signal_count:   int
    is_anomaly:     bool
    start_time:     datetime
    end_time:       Optional[datetime] = None
    mttr_seconds:   Optional[float]    = None
    created_at:     datetime
    updated_at:     datetime

    model_config = {"from_attributes": True}


class WorkItemStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|INVESTIGATING|RESOLVED|CLOSED)$")


class WorkItemListResponse(BaseModel):
    items:  list[WorkItemResponse]
    total:  int