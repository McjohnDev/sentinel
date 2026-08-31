"""Memory collector — AGT-021 / FS2-01."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege


def _point(agent_id: uuid.UUID, host: str, ts: datetime, name: str, value: float, unit: str, **labels: str) -> MetricV1:
    return MetricV1(
        schema="metric.v1",
        agent_id=agent_id,
        host=host,
        ts=ts,
        family="memory",
        name=name,
        value=float(value),
        unit=unit,
        labels=labels,
        message_id=uuid.uuid4(),
    )


class MemoryCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="memory.collector",
        version="1.0.0",
        description="Collect used/free/cached memory and swap usage",
        kind="collector",
        input_schema=PluginIOSchema(type="object", properties={}),
        output_schema=PluginIOSchema(
            type="object",
            properties={"metrics": {"type": "array"}},
            required=["metrics"],
        ),
        required_privileges=[PluginPrivilege.READ],
        default_interval_seconds=60,
        capability_level="L0",
    )

    def collect(self, context: Dict[str, Any]) -> List[MetricV1]:
        agent_id = str(context["agent_id"])
        host = str(context["hostname"])
        ts = datetime.now(timezone.utc)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        metrics = [
            _point(agent_id, host, ts, "memory.used.percent", mem.percent, "percent"),
            _point(agent_id, host, ts, "memory.used.bytes", mem.used, "bytes"),
            _point(agent_id, host, ts, "memory.available.bytes", mem.available, "bytes"),
            _point(agent_id, host, ts, "memory.total.bytes", mem.total, "bytes"),
            _point(agent_id, host, ts, "memory.swap.used.percent", swap.percent, "percent"),
            _point(agent_id, host, ts, "memory.swap.used.bytes", swap.used, "bytes"),
        ]
        cached = getattr(mem, "cached", None)
        if cached is not None:
            metrics.append(_point(agent_id, host, ts, "memory.cached.bytes", cached, "bytes"))
        return metrics
