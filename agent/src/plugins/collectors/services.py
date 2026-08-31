"""Services collector — AGT-026 / FS5 (CBC service list via remote config)."""

from __future__ import annotations

import platform
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege


def _service_status(name: str) -> str:
    system = platform.system().lower()
    try:
        if system == "windows":
            proc = subprocess.run(
                ["sc", "query", name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            out = (proc.stdout or "").upper()
            if "RUNNING" in out:
                return "running"
            if "STOPPED" in out:
                return "stopped"
            return "unknown"
        # Linux systemd
        proc = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        state = (proc.stdout or "").strip().lower()
        if state == "active":
            return "running"
        if state in ("inactive", "failed"):
            return "stopped"
        return state or "unknown"
    except Exception:
        return "unknown"


class ServicesCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="services.collector",
        version="1.0.0",
        description="Watched systemd / Windows services from CBC list",
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
        services = list(context.get("watched_services") or [])
        if not services:
            return []
        agent_id = str(context["agent_id"])
        host = str(context["hostname"])
        ts = datetime.now(timezone.utc)
        metrics: List[MetricV1] = []
        for name in services:
            status = _service_status(str(name))
            metrics.append(
                MetricV1(
                    schema="metric.v1",
                    agent_id=agent_id,
                    host=host,
                    ts=ts,
                    family="service",
                    name="service.up",
                    value=1.0 if status == "running" else 0.0,
                    unit="bool",
                    labels={"service": str(name)[:128], "status": status},
                    message_id=uuid.uuid4(),
                )
            )
        return metrics
