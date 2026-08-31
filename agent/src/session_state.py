"""Local presence file — operator truth when the dashboard disagrees (AGT-005 companion)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class SessionState:
    """Persists last HTTP outcome + credentials so a restart can ping without re-enrolling."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(
        self,
        *,
        server_url: str,
        machine_id: str,
        agent_id: Optional[str] = None,
        auth_key: Optional[str] = None,
        last_error: Optional[str] = None,
        consecutive_failures: int = 0,
        buffer_records: int = 0,
        connected: bool = False,
    ) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "server_url": server_url,
            "machine_id": machine_id,
            "agent_id": agent_id,
            "auth_key": auth_key,
            "last_error": last_error,
            "consecutive_failures": consecutive_failures,
            "buffer_records": buffer_records,
            "connected": connected,
            "last_success_at": datetime.now(timezone.utc).isoformat() if connected else None,
        }
        previous = self.load()
        if not connected:
            payload["last_success_at"] = previous.get("last_success_at")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
