"""FS7 — platform health + latency SLO helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.latency_slo import LatencySLO, BUDGET_COLLECT_TO_UI_S, BUDGET_PAGE_LOAD_S  # noqa: E402
from src.platform_health import aggregate_platform_health, _ok  # noqa: E402


def test_latency_slo_stats_and_budgets():
    slo = LatencySLO(maxlen=100)
    for v in (1.0, 2.0, 50.0, 0.5):
        slo.record_collect_to_ingest(v)
    slo.record_page_load(1.2)
    snap = slo.snapshot()
    assert snap["collect_to_ingest"]["count"] == 4
    assert snap["collect_to_ingest"]["budget_s"] == BUDGET_COLLECT_TO_UI_S
    assert snap["page_load"]["within_budget"] is True
    assert snap["page_load"]["budget_s"] == BUDGET_PAGE_LOAD_S


def test_ok_helper():
    assert _ok("healthy")
    assert not _ok("unhealthy")


def test_aggregate_platform_health_mocked():
    db = MagicMock()
    with patch("src.platform_health.check_database", return_value={"status": "healthy", "component": "postgres"}), patch(
        "src.platform_health.check_redis", return_value={"status": "healthy", "component": "redis"}
    ), patch(
        "src.platform_health.check_tsdb", return_value={"status": "healthy", "component": "victoria_metrics"}
    ), patch(
        "src.platform_health.check_logs", return_value={"status": "healthy", "component": "loki"}
    ), patch(
        "src.platform_health.check_dlq", return_value={"status": "healthy", "component": "metrics_dlq", "count": 0}
    ):
        result = aggregate_platform_health(db)
        assert result["status"] == "healthy"
        assert result["unhealthy_count"] == 0
        assert "postgres" in result["components"]
        assert "metrics_dlq" in result["components"]


def test_aggregate_degraded_when_one_down():
    db = MagicMock()
    with patch("src.platform_health.check_database", return_value={"status": "healthy", "component": "postgres"}), patch(
        "src.platform_health.check_redis", return_value={"status": "unhealthy", "component": "redis", "error": "down"}
    ), patch(
        "src.platform_health.check_tsdb", return_value={"status": "healthy", "component": "victoria_metrics"}
    ), patch(
        "src.platform_health.check_logs", return_value={"status": "healthy", "component": "loki"}
    ), patch(
        "src.platform_health.check_dlq", return_value={"status": "healthy", "component": "metrics_dlq", "count": 0}
    ):
        result = aggregate_platform_health(db)
        assert result["status"] == "degraded"
        assert result["unhealthy_count"] == 1
