"""Network collector — AGT-023 / FS2-03."""

from __future__ import annotations

import uuid
from collections import Counter
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
        family="network",
        name=name,
        value=float(value),
        unit=unit,
        labels=labels,
        message_id=uuid.uuid4(),
    )


class NetworkCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="network.collector",
        version="1.0.0",
        description="Per-interface throughput, errors, drops, and TCP connection states",
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

        counters = psutil.net_io_counters(pernic=True)
        for iface, io in counters.items():
            labels = {"iface": iface}
            metrics.extend(
                [
                    _point(agent_id, host, ts, "network.bytes.sent", io.bytes_sent, "bytes", **labels),
                    _point(agent_id, host, ts, "network.bytes.recv", io.bytes_recv, "bytes", **labels),
                    _point(agent_id, host, ts, "network.errors.in", io.errin, "count", **labels),
                    _point(agent_id, host, ts, "network.errors.out", io.errout, "count", **labels),
                    _point(agent_id, host, ts, "network.drops.in", io.dropin, "count", **labels),
                    _point(agent_id, host, ts, "network.drops.out", io.dropout, "count", **labels),
                ]
            )

        try:
            conns = psutil.net_connections(kind="tcp")
            states = Counter((c.status or "UNKNOWN") for c in conns)
            for state, count in states.items():
                metrics.append(
                    _point(agent_id, host, ts, "network.tcp.connections", count, "count", state=state)
                )
        except (psutil.AccessDenied, PermissionError):
            pass

        return metrics
