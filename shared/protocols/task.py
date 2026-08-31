"""Task envelope — schema task.v1 (defined Lot 1, active Lot 2). L0 agents reject."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TaskIssuer(str, Enum):
    USER = "user"
    API = "api"
    N8N = "n8n"
    RULE = "rule"


class TaskStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    DRY_RUN = "dry_run"


class TaskV1(BaseModel):
    """Platform-initiated action request (AGT-010 / Part G.3)."""

    schema_name: str = Field("task.v1", alias="schema", frozen=True)
    task_id: UUID
    issued_by: TaskIssuer
    signature: str = Field(..., min_length=1, description="Platform signature")
    plugin: str = Field(..., min_length=1, max_length=128)
    input: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    approval_ref: Optional[str] = None
    expires_at: datetime
    agent_id: Optional[UUID] = None

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "use_enum_values": True,
    }

    @field_validator("schema_name")
    @classmethod
    def schema_must_be_v1(cls, v: str) -> str:
        if v != "task.v1":
            raise ValueError("schema must be task.v1")
        return v

    @field_validator("expires_at")
    @classmethod
    def expires_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def to_wire_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")


class TaskResultV1(BaseModel):
    """Structured task result — never free text only (AGT-081)."""

    schema_name: str = Field("task.result.v1", alias="schema", frozen=True)
    task_id: UUID
    status: TaskStatus
    duration_ms: int = Field(..., ge=0)
    exit_code: Optional[int] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    stdout_truncated: Optional[str] = Field(default=None, max_length=8000)
    stderr_truncated: Optional[str] = Field(default=None, max_length=8000)
    audit_ref: Optional[str] = None
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Set when L0 agent rejects an action task",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "use_enum_values": True,
    }

    def to_wire_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")
