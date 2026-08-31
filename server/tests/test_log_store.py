"""Tests for Loki client helpers (no live Loki required)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVER = Path(__file__).resolve().parents[1]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from src.log_store import LokiClient  # noqa: E402


def test_loki_push_posts_streams():
    client = LokiClient(base_url="http://loki:3100")
    with patch("src.log_store.httpx.post") as post:
        post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
        n = client.push(
            "aid",
            "host1",
            [{"severity": "info", "message": "hello", "ts": "2026-08-13T10:00:00+00:00", "source": "journald", "channel": "sshd.service"}],
        )
        assert n == 1
        assert post.call_args.args[0].endswith("/loki/api/v1/push")
        stream = post.call_args.kwargs["json"]["streams"][0]["stream"]
        assert stream["source"] == "journald"
        assert stream["channel"] == "sshd.service"


def test_loki_disabled():
    client = LokiClient(base_url="")
    assert client.health()["status"] == "disabled"
    assert client.push("a", "h", [{"message": "x"}]) == 0
