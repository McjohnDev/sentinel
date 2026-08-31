"""Signed HMAC webhook (INT-003) — no cloud account required."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def post_signed(
    url: str,
    secret: str,
    payload: Dict[str, Any],
    timeout: float = 8.0,
    retries: int = 3,
) -> bool:
    body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
    ts = str(int(time.time()))
    sig = sign_body(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-CBC-Signature": f"sha256={sig}",
        "X-CBC-Timestamp": ts,
    }
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = httpx.post(url, content=body, headers=headers, timeout=timeout)
            if 200 <= resp.status_code < 300:
                return True
            logger.warning("webhook HTTP %s attempt %s", resp.status_code, attempt + 1)
        except Exception as exc:
            last_exc = exc
            logger.warning("webhook error attempt %s: %s", attempt + 1, exc)
        time.sleep(min(2 ** attempt, 4))
    if last_exc:
        logger.error("webhook failed after retries: %s", last_exc)
    return False
