"""CPU collector — golden-path plugin (AGT-020 / FS1-07)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege


class CpuCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="cpu.collector",
        version="1.0.0",
        description="Collect total and per-core CPU utilisation",
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
        total = float(psutil.cpu_percent(interval=0.1))
        per_core = psutil.cpu_percent(interval=None, percpu=True)

        metrics: List[MetricV1] = [
            MetricV1(
                schema="metric.v1",
                agent_id=agent_id,
                host=host,
                ts=ts,
                family="cpu",
                name="cpu.total.utilization",
                value=total,
                unit="percent",
                labels={"core": "all"},
                message_id=uuid.uuid4(),
            )
        ]
        for idx, value in enumerate(per_core):
            metrics.append(
                MetricV1(
                    schema="metric.v1",
                    agent_id=agent_id,
                    host=host,
                    ts=ts,
                    family="cpu",
                    name="cpu.core.utilization",
                    value=float(value),
                    unit="percent",
                    labels={"core": str(idx)},
                    message_id=uuid.uuid4(),
                )
            )
        return metrics
