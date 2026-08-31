"""Self-hosted Grafana Loki client — no cloud account (ADR-001 / STO-003)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _ns(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return str(int(ts.timestamp() * 1_000_000_000))


class LokiClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 8.0) -> None:
        resolved = settings.loki_url if base_url is None else base_url
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout
        self.enabled = bool(self.base_url)

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "url": self.base_url}
        try:
            resp = httpx.get(f"{self.base_url}/ready", timeout=self.timeout)
            ok = resp.status_code == 200
            return {
                "status": "healthy" if ok else "unhealthy",
                "url": self.base_url,
                "http_status": resp.status_code,
            }
        except Exception as exc:
            return {"status": "unhealthy", "url": self.base_url, "error": str(exc)}

    def push(self, agent_id: str, host: str, events: List[Dict[str, Any]]) -> int:
        if not events or not self.enabled:
            return 0
        streams: Dict[tuple, List[List[str]]] = {}
        for ev in events:
            sev = str(ev.get("severity") or "info")
            source = str(ev.get("source") or "file")
            channel = str(ev.get("channel") or "default")
            ts_raw = ev.get("ts")
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                ts = datetime.now(timezone.utc)
            key = (sev, source, channel)
            streams.setdefault(key, []).append(
                [_ns(ts), str(ev.get("message") or ev.get("raw") or "")]
            )
        payload = {
            "streams": [
                {
                    "stream": {
                        "job": "cbc-agent",
                        "agent_id": agent_id,
                        "host": host,
                        "severity": sev,
                        "source": source,
                        "channel": channel,
                    },
                    "values": values,
                }
                for (sev, source, channel), values in streams.items()
            ]
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/loki/api/v1/push",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return len(events)
        except Exception:
            logger.exception("Loki push failed")
            return 0

    def query(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "result": []}
        try:
            resp = httpx.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": int(start.timestamp() * 1_000_000_000),
                    "end": int(end.timestamp() * 1_000_000_000),
                    "limit": limit,
                    "direction": "backward",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = []
            for stream in data.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                for ts_ns, line in stream.get("values", []):
                    rows.append(
                        {
                            "ts": datetime.fromtimestamp(int(ts_ns) / 1_000_000_000, tz=timezone.utc).isoformat(),
                            "message": line,
                            "host": labels.get("host"),
                            "agent_id": labels.get("agent_id"),
                            "severity": labels.get("severity"),
                            "source": labels.get("source"),
                            "channel": labels.get("channel"),
                        }
                    )
            rows.sort(key=lambda r: r["ts"], reverse=True)
            return {"status": "success", "query": query, "result": rows[:limit]}
        except Exception as exc:
            logger.exception("Loki query failed")
            return {"status": "error", "query": query, "error": str(exc), "result": []}


log_store = LokiClient()
