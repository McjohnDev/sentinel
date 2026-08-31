"""Files collector — watched file existence/size (CBC file list via remote config)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

from plugins import CollectorPlugin
from shared.protocols import MetricV1, PluginIOSchema, PluginManifestV1, PluginPrivilege


def _normalize(entry: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(entry, str):
        return {"path": entry}
    return entry


class FilesCollectorPlugin(CollectorPlugin):
    manifest = PluginManifestV1(
        schema="plugin.manifest.v1",
        name="files.collector",
        version="1.0.0",
        description="Watched file existence and size from CBC list",
        kind="collector",
        input_schema=PluginIOSchema(type="object", properties={}),
        output_schema=PluginIOSchema(
            type="object",
            properties={"metrics": {"type": "array"}},
            required=["metrics"],
        ),
        required_privileges=[PluginPrivilege.READ],
        default_interval_seconds=300,
        capability_level="L0",
    )

    def collect(self, context: Dict[str, Any]) -> List[MetricV1]:
        files = [_normalize(f) for f in (context.get("watched_files") or [])]
        if not files:
            return []
        agent_id = str(context["agent_id"])
        host = str(context["hostname"])
        ts = datetime.now(timezone.utc)
        metrics: List[MetricV1] = []
        for entry in files:
            path = str(entry.get("path") or "")
            if not path:
                continue
            exists = os.path.exists(path)
            size_mb = 0.0
            if exists:
                try:
                    size_mb = Path(path).stat().st_size / (1024 * 1024)
                except OSError:
                    exists = False
            metrics.append(
                MetricV1(
                    schema="metric.v1",
                    agent_id=agent_id,
                    host=host,
                    ts=ts,
                    family="file",
                    name="file.exists",
                    value=1.0 if exists else 0.0,
                    unit="bool",
                    labels={"path": path[:256]},
                    message_id=uuid.uuid4(),
                )
            )
            metrics.append(
                MetricV1(
                    schema="metric.v1",
                    agent_id=agent_id,
                    host=host,
                    ts=ts,
                    family="file",
                    name="file.size.mb",
                    value=round(size_mb, 3),
                    unit="megabytes",
                    labels={"path": path[:256]},
                    message_id=uuid.uuid4(),
                )
            )
            max_mb = entry.get("max_size_mb")
            if max_mb is not None and exists:
                over = 1.0 if size_mb > float(max_mb) else 0.0
                metrics.append(
                    MetricV1(
                        schema="metric.v1",
                        agent_id=agent_id,
                        host=host,
                        ts=ts,
                        family="file",
                        name="file.oversize",
                        value=over,
                        unit="bool",
                        labels={"path": path[:256]},
                        message_id=uuid.uuid4(),
                    )
                )
        return metrics
