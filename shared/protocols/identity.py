"""Agent self-declared identity (AGT-015) — embedded in enrolment and payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AgentIdentity(BaseModel):
    """Identity fields the agent SHALL declare at enrolment and on every payload."""

    hostname: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., description="Windows | Linux | Darwin/macOS")
    os_version: str = Field(..., min_length=1, max_length=100)
    ip_addresses: List[str] = Field(default_factory=list, min_length=0)
    agent_name: str = Field(default="cbc-agent", min_length=1, max_length=100)
    agent_version: str = Field(..., min_length=1, max_length=50)
    local_ts: datetime = Field(
        ...,
        description="Local timestamp with timezone (AGT-015)",
    )

    @field_validator("local_ts")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("local_ts must be timezone-aware")
        return v

    @classmethod
    def utc_now_example(cls, **kwargs) -> "AgentIdentity":
        defaults = dict(
            hostname="web-01.prod",
            os="Linux",
            os_version="5.15.0",
            ip_addresses=["10.0.0.12"],
            agent_name="cbc-agent",
            agent_version="1.1.0",
            local_ts=datetime.now(timezone.utc),
        )
        defaults.update(kwargs)
        return cls(**defaults)
