"""Canonical metric point — schema metric.v1 (SPEC Part G.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MetricV1(BaseModel):
    """Single time-series sample from an agent or connector."""

    schema_name: str = Field("metric.v1", alias="schema", frozen=True)
    # Identifiant tel que la plateforme l'attribue. Il était typé `UUID`, ce
    # qui a cessé d'être vrai quand les agents sont passés à un code
    # hexadécimal court : tout point de métrique était alors rejeté à la
    # construction, et les collecteurs échouaient en silence un par un.
    # Le type ne doit pas figer une convention d'attribution qui appartient
    # au serveur — la contrainte utile est « non vide et borné ».
    agent_id: str = Field(..., min_length=1, max_length=64)
    host: str = Field(..., min_length=1, max_length=255)
    ts: datetime
    family: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="cpu | memory | disk | network | process | agent | …",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Canonical metric name, e.g. cpu.total.utilization",
    )
    value: float
    unit: str = Field(..., min_length=1, max_length=32)
    labels: Dict[str, str] = Field(default_factory=dict)
    message_id: Optional[UUID] = Field(
        default=None,
        description="Deduplication id for at-least-once delivery (PLT-001)",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "schema": "metric.v1",
                    "agent_id": "A3F09C",
                    "host": "web-01.prod",
                    "ts": "2026-07-30T08:15:00Z",
                    "family": "cpu",
                    "name": "cpu.total.utilization",
                    "value": 87.5,
                    "unit": "percent",
                    "labels": {"core": "all", "env": "prod", "group": "web"},
                }
            ]
        },
    }

    @field_validator("schema_name")
    @classmethod
    def schema_must_be_v1(cls, v: str) -> str:
        if v != "metric.v1":
            raise ValueError("schema must be metric.v1")
        return v

    @field_validator("ts")
    @classmethod
    def ts_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    def to_wire_dict(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")
