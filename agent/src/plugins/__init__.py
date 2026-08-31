"""Plugin framework (AGT-002) — Lot 1 collectors."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Type

from shared.protocols import MetricV1, PluginManifestV1

logger = logging.getLogger(__name__)


class CollectorPlugin(ABC):
    """Base class for L0 collector plugins."""

    manifest: PluginManifestV1

    @abstractmethod
    def collect(self, context: Dict[str, Any]) -> List[MetricV1]:
        """Return zero or more metric.v1 points."""


class PluginRegistry:
    """Discovers and runs collector plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, CollectorPlugin] = {}

    def register(self, plugin: CollectorPlugin) -> None:
        name = plugin.manifest.name
        if name in self._plugins:
            raise ValueError(f"duplicate plugin: {name}")
        self._plugins[name] = plugin
        logger.info("registered plugin %s v%s", name, plugin.manifest.version)

    def get(self, name: str) -> Optional[CollectorPlugin]:
        return self._plugins.get(name)

    def list_manifests(self) -> List[PluginManifestV1]:
        return [p.manifest for p in self._plugins.values()]

    def collect_all(self, context: Dict[str, Any]) -> List[MetricV1]:
        metrics: List[MetricV1] = []
        for name, plugin in self._plugins.items():
            try:
                metrics.extend(plugin.collect(context))
            except Exception:
                logger.exception("plugin %s failed", name)
        return metrics

    def load_builtin_package(self, package_name: str = "plugins.collectors") -> None:
        """Import all modules under a collectors package to trigger registration hooks."""
        try:
            pkg = importlib.import_module(package_name)
        except ModuleNotFoundError:
            logger.warning("plugin package %s not found", package_name)
            return
        if not hasattr(pkg, "__path__"):
            return
        for mod in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
            importlib.import_module(mod.name)


def build_default_registry() -> PluginRegistry:
    """Factory used by the agent entrypoint."""
    from plugins.collectors.cpu import CpuCollectorPlugin
    from plugins.collectors.disk import DiskCollectorPlugin
    from plugins.collectors.files import FilesCollectorPlugin
    from plugins.collectors.footprint import FootprintCollectorPlugin
    from plugins.collectors.memory import MemoryCollectorPlugin
    from plugins.collectors.network import NetworkCollectorPlugin
    from plugins.collectors.process import ProcessCollectorPlugin
    from plugins.collectors.services import ServicesCollectorPlugin

    registry = PluginRegistry()
    registry.register(CpuCollectorPlugin())
    registry.register(MemoryCollectorPlugin())
    registry.register(DiskCollectorPlugin())
    registry.register(NetworkCollectorPlugin())
    registry.register(ProcessCollectorPlugin())
    registry.register(ServicesCollectorPlugin())
    registry.register(FilesCollectorPlugin())
    registry.register(FootprintCollectorPlugin())
    return registry
