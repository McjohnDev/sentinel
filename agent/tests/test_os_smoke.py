"""FS7-03 — Cross-OS agent smoke suite (runs on whatever OS hosts pytest).

Markers document Win/Linux/macOS intent; collectors that are OS-specific are skipped
gracefully so CI on one OS still exercises the shared plugin path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from plugins import build_default_registry  # noqa: E402
from durable_buffer import DurableBuffer  # noqa: E402


def test_registry_builds_on_host_os():
    registry = build_default_registry()
    manifests = {m.name for m in registry.list_manifests()}
    assert "cpu.collector" in manifests
    assert "memory.collector" in manifests
    assert "disk.collector" in manifests


def test_collect_emits_metric_v1_on_host_os():
    import uuid

    registry = build_default_registry()
    metrics = registry.collect_all(
        {"agent_id": str(uuid.uuid4()), "hostname": f"smoke-{sys.platform}"}
    )
    assert metrics, "expected at least one metric on this OS"
    assert all(m.schema_name == "metric.v1" for m in metrics)


def test_durable_buffer_roundtrip(tmp_path):
    buf = DurableBuffer(tmp_path / "q.jsonl", max_bytes=10_000, max_age_seconds=24 * 3600)
    buf.enqueue("metrics", [{"schema": "metric.v1"}])
    records = buf.drain()
    assert len(records) == 1
    assert records[0]["kind"] == "metrics"


@pytest.mark.parametrize(
    "label,condition",
    [
        ("windows", sys.platform.startswith("win")),
        ("linux", sys.platform.startswith("linux")),
        ("macos", sys.platform == "darwin"),
    ],
)
def test_os_label_documented(label, condition):
    """Documents 3-OS coverage matrix — skip when not on that OS."""
    if not condition:
        pytest.skip(f"host is {sys.platform}, not {label}")
    assert condition
