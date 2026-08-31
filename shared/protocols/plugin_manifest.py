"""Plugin manifest — AGT-002 / AGT-080 (JSON Schema I/O via Pydantic)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PluginPrivilege(str, Enum):
    NONE = "none"
    READ = "read"
    SERVICE_CONTROL = "service_control"
    FILE_WRITE = "file_write"
    COMMAND_EXEC = "command_exec"
    ELEVATED = "elevated"


class PluginIOSchema(BaseModel):
    """JSON Schema fragment describing plugin input or output."""

    type: str = Field(default="object")
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)
    additionalProperties: bool = True


class PluginManifestV1(BaseModel):
    """Machine-readable plugin declaration (collectors Lot 1, actions Lot 2)."""

    schema_name: str = Field("plugin.manifest.v1", alias="schema", frozen=True)
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")
    version: str = Field(..., min_length=1, max_length=32)
    description: str = Field(..., min_length=1, max_length=500)
    kind: str = Field(..., description="collector | action | both")
    input_schema: PluginIOSchema = Field(default_factory=PluginIOSchema)
    output_schema: PluginIOSchema = Field(default_factory=PluginIOSchema)
    required_privileges: List[PluginPrivilege] = Field(default_factory=list)
    default_interval_seconds: Optional[int] = Field(
        default=60,
        ge=10,
        le=900,
        description="Collectors only; 10 s–15 min (SPEC)",
    )
    capability_level: str = Field(
        default="L0",
        description="L0 collect-only; L1 actions (Lot 2)",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "use_enum_values": True,
    }

    @field_validator("schema_name")
    @classmethod
    def schema_must_be_v1(cls, v: str) -> str:
        if v != "plugin.manifest.v1":
            raise ValueError("schema must be plugin.manifest.v1")
        return v

    @field_validator("kind")
    @classmethod
    def kind_allowed(cls, v: str) -> str:
        allowed = {"collector", "action", "both"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {allowed}")
        return v

    def to_llm_tool_definition(self) -> Dict[str, Any]:
        """AGT-080: usable as LLM function-calling tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema.model_dump(),
        }
