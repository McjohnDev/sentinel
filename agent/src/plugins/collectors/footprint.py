"""Agent footprint collector — AGT-007 / FS5-05."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psutil

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege


_SELF_PROC: Optional[psutil.Process] = None


def _self_process() -> psutil.Process:
    """Handle mémorisé — cpu_percent(interval=None) mesure l'écart depuis
    l'appel précédent sur le même objet Process."""
    global _SELF_PROC
    if _SELF_PROC is None or _SELF_PROC.pid != os.getpid():
        _SELF_PROC = psutil.Process(os.getpid())
        _SELF_PROC.cpu_percent(interval=None)  # amorce la référence
    return _SELF_PROC


def measure_self() -> Dict[str, float]:
    """AGT-007 — voir agent.py:_measure_agent_footprint pour le détail.

    La forme bloquante mesurait l'agent pendant son propre sleep : le travail
    réel tombait hors fenêtre et un tick d'ordonnanceur isolé se lisait ~30%.
    """
    proc = _self_process()
    try:
        with proc.oneshot():
            cpu = float(proc.cpu_percent(interval=None))
            ram_mb = float(proc.memory_info().rss) / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"cpu_percent": 0.0, "ram_mb": 0.0}

    # Ramené à la machine entière, comme `agent.py:_measure_agent_footprint`.
    # Ces deux mesures alimentent le même budget : les laisser diverger
    # ferait dire au heartbeat et à la métrique deux choses différentes du
    # même agent.
    cores = psutil.cpu_count(logical=True) or 1
    return {"cpu_percent": round(cpu / cores, 2), "ram_mb": round(ram_mb, 2)}


class FootprintCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="agent.footprint",
        version="1.0.0",
        description="Self-reported agent CPU/RAM (AGT-007)",
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
        stats = measure_self()
        return [
            MetricV1(
                schema="metric.v1",
                agent_id=agent_id,
                host=host,
                ts=ts,
                family="agent",
                name="agent.cpu.percent",
                value=stats["cpu_percent"],
                unit="percent",
                labels={},
                message_id=uuid.uuid4(),
            ),
            MetricV1(
                schema="metric.v1",
                agent_id=agent_id,
                host=host,
                ts=ts,
                family="agent",
                name="agent.memory.mb",
                value=stats["ram_mb"],
                unit="megabytes",
                labels={},
                message_id=uuid.uuid4(),
            ),
        ]
