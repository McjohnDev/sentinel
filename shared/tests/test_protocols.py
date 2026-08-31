"""Contract tests for frozen Lot 1 protocols (FS0-01)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.protocols import (  # noqa: E402
    EventV1,
    MetricV1,
    PluginManifestV1,
    TaskResultV1,
    TaskV1,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_metric_valid_fixture():
    m = MetricV1.model_validate(_load("metric.valid.json"))
    assert m.schema_name == "metric.v1"
    assert m.name == "cpu.total.utilization"
    wire = m.to_wire_dict()
    assert wire["schema"] == "metric.v1"


def test_metric_invalid_fixture_rejected():
    with pytest.raises(ValidationError):
        MetricV1.model_validate(_load("metric.invalid.json"))


def test_event_valid_and_invalid():
    e = EventV1.model_validate(_load("event.valid.json"))
    assert e.severity == "critical"
    with pytest.raises(ValidationError):
        EventV1.model_validate(_load("event.invalid.json"))


def test_task_valid_and_l0_reject_result():
    t = TaskV1.model_validate(_load("task.valid.json"))
    assert t.dry_run is True
    result = TaskResultV1(
        schema="task.result.v1",
        task_id=t.task_id,
        status="rejected",
        duration_ms=1,
        rejection_reason="agent capability L0 — actions not enabled",
    )
    assert result.status == "rejected"


def test_plugin_manifest_and_llm_tool():
    p = PluginManifestV1.model_validate(_load("plugin.manifest.valid.json"))
    tool = p.to_llm_tool_definition()
    assert tool["name"] == "cpu.collector"
    assert "parameters" in tool


def test_extra_fields_forbidden():
    raw = _load("metric.valid.json")
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        MetricV1.model_validate(raw)
