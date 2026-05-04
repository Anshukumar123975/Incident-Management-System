from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, Field, model_validator
from app.db.postgres import Base


# ── SQLAlchemy ORM Model ──────────────────────────────────────────────────
class RCARecord(Base):
    __tablename__ = "rca_records"

    id:                   Mapped[UUID]     = mapped_column(primary_key=True, default=uuid4)
    work_item_id:         Mapped[UUID]     = mapped_column(ForeignKey("work_items.id"), nullable=False)
    root_cause_category:  Mapped[str]      = mapped_column(String, nullable=False)
    fix_applied:          Mapped[str]      = mapped_column(String, nullable=False)
    prevention_steps:     Mapped[str]      = mapped_column(String, nullable=False)
    incident_start:       Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident_end:         Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Pydantic Schemas ──────────────────────────────────────────────────────

RCA_CATEGORIES = ["INFRA", "CODE", "CONFIG", "DEPENDENCY", "NETWORK", "UNKNOWN"]


class RCASubmit(BaseModel):
    """
    Request body for POST /rca.
    All fields are mandatory — the state machine blocks CLOSED
    if any field is missing or empty.
    """
    work_item_id:        UUID
    root_cause_category: str      = Field(..., description=f"One of: {RCA_CATEGORIES}")
    fix_applied:         str      = Field(..., min_length=10, description="What fix was applied")
    prevention_steps:    str      = Field(..., min_length=10, description="Steps to prevent recurrence")
    incident_start:      datetime = Field(..., description="When the incident started (UTC)")
    incident_end:        datetime = Field(..., description="When the incident was resolved (UTC)")

    @model_validator(mode="after")
    def validate_rca(self):
        # Category must be valid
        if self.root_cause_category not in RCA_CATEGORIES:
            raise ValueError(f"root_cause_category must be one of {RCA_CATEGORIES}")

        # End must be after start
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be after incident_start")

        # Fields cannot be blank or whitespace only
        if not self.fix_applied.strip():
            raise ValueError("fix_applied cannot be blank")
        if not self.prevention_steps.strip():
            raise ValueError("prevention_steps cannot be blank")

        return self


class RCAResponse(BaseModel):
    id:                  UUID
    work_item_id:        UUID
    root_cause_category: str
    fix_applied:         str
    prevention_steps:    str
    incident_start:      datetime
    incident_end:        datetime
    submitted_at:        datetime
    mttr_seconds:        Optional[float] = None  # calculated and attached on submit

    model_config = {"from_attributes": True}