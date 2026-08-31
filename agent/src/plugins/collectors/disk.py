"""Disk collector — AGT-022 / FS2-02 (one series per mount)."""

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
        family="disk",
        name=name,
        value=float(value),
        unit=unit,
        labels=labels,
        message_id=uuid.uuid4(),
    )


class DiskCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="disk.collector",
        version="1.0.0",
        description="Collect disk usage per filesystem / mount point",
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
        metrics: List[MetricV1] = []

        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint or part.fstype in ("", "cdrom", "iso9660"):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            labels = {"mount": part.mountpoint, "fstype": part.fstype or "unknown"}
            metrics.extend(
                [
                    _point(agent_id, host, ts, "disk.used.percent", usage.percent, "percent", **labels),
                    _point(agent_id, host, ts, "disk.used.bytes", usage.used, "bytes", **labels),
                    _point(agent_id, host, ts, "disk.total.bytes", usage.total, "bytes", **labels),
                    _point(agent_id, host, ts, "disk.free.bytes", usage.free, "bytes", **labels),
                ]
            )
        return metrics
