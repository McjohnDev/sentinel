"""Canonical wire protocols for CBC Supervision Platform (SPEC Part G).

Schema versions are frozen for Lot 1. Changing a model requires a new schema
version (e.g. metric.v2) — do not silently break metric.v1 consumers.
"""

from .event import EventV1, EventSeverity, EventSource
from .identity import AgentIdentity
from .metric import MetricV1
from .plugin_manifest import PluginIOSchema, PluginManifestV1, PluginPrivilege
from .task import TaskResultV1, TaskV1

__all__ = [
    "AgentIdentity",
    "EventSeverity",
    "EventSource",
    "EventV1",
    "MetricV1",
    "PluginIOSchema",
    "PluginManifestV1",
    "PluginPrivilege",
    "TaskResultV1",
    "TaskV1",
]
