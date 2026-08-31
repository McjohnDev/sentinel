"""Tests for remote config overlay and new collectors."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from remote_config import RemoteConfigState, deep_merge  # noqa: E402
from plugins import build_default_registry  # noqa: E402


def test_remote_config_apply(tmp_path):
    state = RemoteConfigState(tmp_path / "remote-config.yaml")
    assert state.version == 0
    overlay = state.apply(2, {"metrics": {"processes": {"watched": ["sqlservr"]}}})
    assert overlay["metrics"]["processes"]["watched"] == ["sqlservr"]
    state2 = RemoteConfigState(tmp_path / "remote-config.yaml")
    assert state2.version == 2
    assert state2.load_overlay()["metrics"]["processes"]["watched"] == ["sqlservr"]


def test_default_registry_includes_fs5_plugins():
    reg = build_default_registry()
    names = {m.name for m in reg.list_manifests()}
    assert "services.collector" in names
    assert "files.collector" in names
    assert "agent.footprint" in names
    assert "cpu.collector" in names


def test_deep_merge_remote():
    base = {"server": {"url": "https://a"}, "logs": {"enabled": False}}
    overlay = {"logs": {"enabled": True, "files": ["/var/log/a.log"]}}
    merged = deep_merge(base, overlay)
    assert merged["server"]["url"] == "https://a"
    assert merged["logs"]["enabled"] is True
    assert merged["logs"]["files"] == ["/var/log/a.log"]
