"""FS9 — L0 reject / L1 dry-run action plugins."""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from shared.protocols import TaskV1  # noqa: E402
from action_plugins import execute_task  # noqa: E402


def _task(plugin="health.check", dry_run=True):
    return TaskV1(
        schema="task.v1",
        task_id=uuid4(),
        issued_by="user",
        signature="sig",
        plugin=plugin,
        input={"service": "nginx", "operation": "status"} if plugin == "service.manage" else {},
        dry_run=dry_run,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )


def test_l0_rejects():
    result = execute_task(_task(), capability_level="L0")
    assert result.status == "rejected"
    assert "L0" in (result.rejection_reason or "")


def test_l1_dry_run_health():
    result = execute_task(_task("health.check", True), capability_level="L1")
    assert result.status == "dry_run"
    assert result.output.get("result") == "ok"


def test_l1_service_manage_dry_run():
    result = execute_task(_task("service.manage", True), capability_level="L1")
    assert result.status == "dry_run"
    assert result.output.get("service") == "nginx"
