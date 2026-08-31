"""Canonical event — schema event.v1 (SPEC Part G.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventSource(str, Enum):
    AGENT = "agent"
    PLATFORM = "platform"
    EXTERNAL = "external"


class EventSeverity(str, Enum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class EventV1(BaseModel):
    """Discrete event (service down, log match, OS event, …)."""

    schema_name: str = Field("event.v1", alias="schema", frozen=True)
    source: EventSource
    host: str = Field(..., min_length=1, max_length=255)
    ts: datetime
    type: str = Field(..., min_length=1, max_length=64)
    severity: EventSeverity
    message: str = Field(..., min_length=1, max_length=4000)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[UUID] = None
    message_id: Optional[UUID] = None

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "use_enum_values": True,
        "json_schema_extra": {
            "examples": [
                {
                    "schema": "event.v1",
                    "source": "agent",
                    "host": "db-02.prod",
                    "ts": "2026-07-30T08:15:00Z",
                    "type": "service_down",
                    "severity": "critical",
                    "message": "Service nginx is not running",
                    "attributes": {"service": "nginx"},
                }
            ]
        },
    }

    @field_validator("schema_name")
    @classmethod
    def schema_must_be_v1(cls, v: str) -> str:
        if v != "event.v1":
            raise ValueError("schema must be event.v1")
        return v

    @field_validator("ts")
    @classmethod
    def ts_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def to_wire_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")
