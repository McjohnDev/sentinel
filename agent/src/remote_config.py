"""Remote config apply (AGT-008) — merge platform payload into local agent config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class RemoteConfigState:
    def __init__(self, overlay_path: str | Path) -> None:
        self.overlay_path = Path(overlay_path)
        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        self.version = 0
        self._load()

    def _load(self) -> None:
        meta = self.overlay_path.with_suffix(".meta.json")
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                self.version = int(data.get("version") or 0)
            except (json.JSONDecodeError, ValueError, OSError):
                self.version = 0

    def load_overlay(self) -> Dict[str, Any]:
        if not self.overlay_path.exists():
            return {}
        try:
            data = yaml.safe_load(self.overlay_path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        except OSError:
            return {}

    def apply(self, version: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist overlay and return it (caller merges into live config)."""
        payload = payload if isinstance(payload, dict) else {}
        self.overlay_path.write_text(
            yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        meta = self.overlay_path.with_suffix(".meta.json")
        meta.write_text(json.dumps({"version": int(version)}), encoding="utf-8")
        self.version = int(version)
        return payload
