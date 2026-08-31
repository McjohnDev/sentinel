"""Publish agent online/offline to cache + dashboard WebSocket."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from src.agent_purge import derived_agent_status, last_seen_age_seconds
from src.cache_service import cache_service
from src.websocket_manager import manager

logger = logging.getLogger(__name__)


def publish_agent_presence(agent, *, online: Optional[bool] = None) -> None:
    """Invalidate the agents list cache and push `agent.presence` to the UI."""
    try:
        cache_service.delete_pattern("agents:*")
    except Exception:
        logger.debug("agents cache invalidate failed", exc_info=True)

    status = derived_agent_status(agent)
    if online is None:
        online = status == "active"
    last = agent.last_communication
    payload = {
        "type": "agent.presence",
        "agent_id": agent.id,
        "hostname": agent.hostname,
        "online": bool(online),
        "status": status,
        "last_communication": last.isoformat() if last else None,
        "last_seen_age_seconds": last_seen_age_seconds(agent),
        "ts": datetime.utcnow().isoformat(),
    }
    manager.broadcast_sync(payload)
