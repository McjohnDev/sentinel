"""Unit tests for VictoriaMetrics line format (no live TSDB required)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVER = Path(__file__).resolve().parents[1]
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from src.tsdb_service import VictoriaMetricsClient, metric_to_prometheus_line  # noqa: E402


def test_prometheus_line_format():
    ts = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    line = metric_to_prometheus_line(
        "cpu.total.utilization",
        42.5,
        ts,
        {"name": "cpu.total.utilization", "agent_id": "abc", "host": "web-01"},
    )
    assert line.startswith("cbc_metric{")
    assert 'name="cpu.total.utilization"' in line
    assert "42.5" in line
    assert str(int(ts.timestamp() * 1000)) in line


def test_write_prometheus_posts_to_local_vm():
    client = VictoriaMetricsClient(base_url="http://victoria-metrics:8428")
    with patch("src.tsdb_service.httpx.post") as post:
        post.return_value = MagicMock(status_code=204, raise_for_status=lambda: None)
        n = client.write_prometheus(['cbc_metric{name="x"} 1 1'])
        assert n == 1
        post.assert_called_once()
        assert post.call_args.args[0].endswith("/api/v1/import/prometheus")


def test_health_disabled_when_empty_url():
    client = VictoriaMetricsClient(base_url="")
    assert client.health()["status"] == "disabled"
