"""FS7-06 — Aggregate health of critical platform components (NFR-010)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import settings


def _ok(status: str) -> bool:
    return status in ("healthy", "ok", "ready", "up")


def check_database(db: Session) -> Dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "component": "postgres"}
    except Exception as exc:
        return {"status": "unhealthy", "component": "postgres", "error": str(exc)}


def check_redis() -> Dict[str, Any]:
    try:
        from src.cache_service import cache_service

        cache_service.redis_client.ping()
        return {
            "status": "healthy",
            "component": "redis",
            "host": settings.redis_host,
            "port": settings.redis_port,
        }
    except Exception as exc:
        return {"status": "unhealthy", "component": "redis", "error": str(exc)}


def check_tsdb() -> Dict[str, Any]:
    from src.tsdb_service import tsdb

    result = tsdb.health()
    result["component"] = "victoria_metrics"
    return result


def check_logs() -> Dict[str, Any]:
    from src.log_store import log_store

    result = log_store.health()
    result["component"] = "loki"
    return result


def check_api_self() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "component": "api",
        "version": settings.app_version,
        "name": settings.app_name,
    }


def check_dlq() -> Dict[str, Any]:
    """PLT-002 — DLQ depth is informational; a non-zero queue is degraded, not down."""
    try:
        from src.protocol_ingest import DeadLetterQueue

        queue = DeadLetterQueue()
        count = queue.size()
        return {
            "status": "healthy" if count == 0 else "degraded",
            "component": "metrics_dlq",
            "count": count,
            "path": str(queue.path),
        }
    except Exception as exc:
        return {"status": "unhealthy", "component": "metrics_dlq", "error": str(exc)}


def aggregate_platform_health(db: Session) -> Dict[str, Any]:
    """Return combined status for Postgres, Redis, VictoriaMetrics, Loki, API."""
    components = [
        check_api_self(),
        check_database(db),
        check_redis(),
        check_tsdb(),
        check_logs(),
        check_dlq(),
    ]
    unhealthy = [c for c in components if not _ok(str(c.get("status", "")))]
    overall = (
        "healthy"
        if not unhealthy
        else ("degraded" if len(unhealthy) < len(components) else "unhealthy")
    )
    return {
        "status": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": {c["component"]: c for c in components},
        "unhealthy_count": len(unhealthy),
    }


def probe_http(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Optional external probe helper (dashboard / mail)."""
    try:
        resp = httpx.get(url, timeout=timeout)
        return {
            "status": "healthy" if resp.status_code < 500 else "unhealthy",
            "http_status": resp.status_code,
            "url": url,
        }
    except Exception as exc:
        return {"status": "unhealthy", "url": url, "error": str(exc)}
