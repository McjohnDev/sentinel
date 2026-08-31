"""External connectors — Docker host metrics (PLT-004)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from urllib import error, request


def _docker_base() -> str:
    return os.environ.get("DOCKER_HOST", "http://127.0.0.1:2375").rstrip("/")


def probe_docker(endpoint: Optional[str] = None) -> Dict[str, Any]:
    """
    Query Docker Engine HTTP API (/info, /containers/json).
    Works with TCP DOCKER_HOST; unix sockets need a proxy (lab uses TCP or mock).
    """
    base = (endpoint or _docker_base()).rstrip("/")
    if base.startswith("unix:"):
        return {
            "status": "degraded",
            "error_message": "unix socket not supported in this build — set TCP DOCKER_HOST",
            "last_payload": None,
        }
    try:
        info_req = request.Request(f"{base}/info", method="GET")
        with request.urlopen(info_req, timeout=3) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        containers_req = request.Request(f"{base}/containers/json?all=true", method="GET")
        with request.urlopen(containers_req, timeout=3) as resp:
            containers = json.loads(resp.read().decode("utf-8"))
        running = sum(1 for c in containers if (c.get("State") or "").lower() == "running")
        payload = {
            "containers_total": len(containers),
            "containers_running": running,
            "ncpu": info.get("NCPU"),
            "mem_total": info.get("MemTotal"),
            "name": info.get("Name"),
            "server_version": info.get("ServerVersion"),
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }
        return {"status": "up", "error_message": None, "last_payload": json.dumps(payload)}
    except error.URLError as exc:
        return {"status": "down", "error_message": str(exc.reason)[:200], "last_payload": None}
    except Exception as exc:
        return {"status": "unknown", "error_message": str(exc)[:200], "last_payload": None}
