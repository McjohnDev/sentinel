"""Export frozen JSON Schemas and example fixtures from Pydantic models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from shared.protocols import (  # noqa: E402
    EventV1,
    MetricV1,
    PluginManifestV1,
    TaskResultV1,
    TaskV1,
)


def export() -> None:
    schemas_dir = ROOT / "schemas"
    fixtures_dir = ROOT / "fixtures"
    schemas_dir.mkdir(exist_ok=True)
    fixtures_dir.mkdir(exist_ok=True)

    models = {
        "metric.v1": MetricV1,
        "event.v1": EventV1,
        "task.v1": TaskV1,
        "task.result.v1": TaskResultV1,
        "plugin.manifest.v1": PluginManifestV1,
    }

    for name, model in models.items():
        schema = model.model_json_schema()
        path = schemas_dir / f"{name}.json"
        path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        print(f"wrote {path}")

    # Valid fixtures
    fixtures = {
        "metric.valid.json": {
            "schema": "metric.v1",
            "agent_id": "550e8400-e29b-41d4-a716-446655440000",
            "host": "web-01.prod",
            "ts": "2026-07-30T08:15:00+00:00",
            "family": "cpu",
            "name": "cpu.total.utilization",
            "value": 87.5,
            "unit": "percent",
            "labels": {"core": "all", "env": "prod"},
            "message_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        },
        "metric.invalid.json": {
            "schema": "metric.v2",
            "agent_id": "not-a-uuid",
            "host": "",
            "ts": "yesterday",
            "family": "cpu",
            "name": "cpu.total.utilization",
            "value": "high",
            "unit": "percent",
        },
        "event.valid.json": {
            "schema": "event.v1",
            "source": "agent",
            "host": "db-02.prod",
            "ts": "2026-07-30T08:15:00+00:00",
            "type": "service_down",
            "severity": "critical",
            "message": "Service nginx is not running",
            "attributes": {"service": "nginx"},
        },
        "event.invalid.json": {
            "schema": "event.v1",
            "source": "unknown",
            "host": "db-02.prod",
            "ts": "2026-07-30T08:15:00+00:00",
            "type": "service_down",
            "severity": "urgent",
            "message": "x",
        },
        "task.valid.json": {
            "schema": "task.v1",
            "task_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "issued_by": "user",
            "signature": "sig-placeholder",
            "plugin": "service.manage",
            "input": {"service": "nginx", "operation": "restart"},
            "dry_run": True,
            "expires_at": "2026-07-30T09:00:00+00:00",
        },
        "plugin.manifest.valid.json": {
            "schema": "plugin.manifest.v1",
            "name": "cpu.collector",
            "version": "1.0.0",
            "description": "Collect CPU utilisation metrics",
            "kind": "collector",
            "input_schema": {"type": "object", "properties": {}, "required": []},
            "output_schema": {
                "type": "object",
                "properties": {
                    "metrics": {"type": "array"},
                },
                "required": ["metrics"],
            },
            "required_privileges": ["read"],
            "default_interval_seconds": 60,
            "capability_level": "L0",
        },
    }

    for name, payload in fixtures.items():
        path = fixtures_dir / name
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    export()
