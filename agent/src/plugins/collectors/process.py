"""Process collector — AGT-024 / FS2-03."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege

TOP_N = 5


def _point(agent_id: uuid.UUID, host: str, ts: datetime, name: str, value: float, unit: str, **labels: str) -> MetricV1:
    return MetricV1(
        schema="metric.v1",
        agent_id=agent_id,
        host=host,
        ts=ts,
        family="process",
        name=name,
        value=float(value),
        unit=unit,
        labels=labels,
        message_id=uuid.uuid4(),
    )


class ProcessCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="process.collector",
        version="1.0.0",
        description="Top-N processes by CPU/RAM and watched-process presence",
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
        watched: List[str] = list(context.get("watched_processes") or [])
        metrics: List[MetricV1] = []

        procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        by_cpu = sorted(procs, key=lambda p: p.get("cpu_percent") or 0, reverse=True)[:TOP_N]
        by_ram = sorted(procs, key=lambda p: p.get("memory_percent") or 0, reverse=True)[:TOP_N]

        for rank, info in enumerate(by_cpu, start=1):
            name = str(info.get("name") or "unknown")[:64]
            metrics.append(
                _point(
                    agent_id, host, ts, "process.top.cpu.percent",
                    float(info.get("cpu_percent") or 0), "percent",
                    rank=str(rank), pid=str(info.get("pid") or 0), proc=name,
                )
            )
        for rank, info in enumerate(by_ram, start=1):
            name = str(info.get("name") or "unknown")[:64]
            metrics.append(
                _point(
                    agent_id, host, ts, "process.top.memory.percent",
                    float(info.get("memory_percent") or 0), "percent",
                    rank=str(rank), pid=str(info.get("pid") or 0), proc=name,
                )
            )

        running_names = {(p.get("name") or "").lower() for p in procs}
        for wanted in watched:
            present = 1.0 if wanted.lower() in running_names else 0.0
            metrics.append(
                _point(agent_id, host, ts, "process.watched.present", present, "bool", proc=wanted)
            )

        metrics.append(_point(agent_id, host, ts, "process.count", len(procs), "count"))
        return metrics
