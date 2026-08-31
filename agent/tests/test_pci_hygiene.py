"""Lot 2 — pci.hygiene action plugin."""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from shared.protocols import TaskV1  # noqa: E402
from action_plugins import ALLOWLIST, execute_task  # noqa: E402
from pci_hygiene import run_pci_hygiene  # noqa: E402


def _task(plugin="pci.hygiene", dry_run=True):
    return TaskV1(
        schema="task.v1",
        task_id=uuid4(),
        issued_by="user",
        signature="sig",
        plugin=plugin,
        input={},
        dry_run=dry_run,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )


def test_pci_in_allowlist():
    assert "pci.hygiene" in ALLOWLIST


def test_l0_rejects_pci():
    result = execute_task(_task(), capability_level="L0")
    assert result.status == "rejected"


def test_l1_pci_hygiene_runs():
    result = execute_task(_task(dry_run=False), capability_level="L1")
    assert result.status == "succeeded"
    out = result.output or {}
    assert out.get("schema") == "pci.hygiene.v1"
    assert "score" in out
    assert "checks" in out
    assert "disclaimer" in out
    assert out["total"] >= 5


def test_risky_listener_fails_check():
    class Conn:
        status = "LISTEN"

        class Laddr:
            port = 23

        laddr = Laddr()

    with patch("pci_hygiene._net_connections", return_value=[Conn()]), patch(
        "pci_hygiene._process_names", return_value=set()
    ), patch("pci_hygiene._firewall_hint", return_value=(True, "ok")), patch(
        "pci_hygiene._logging_ok", return_value=(True, "ok")
    ), patch("pci_hygiene._time_sync_ok", return_value=(True, "ok")), patch(
        "pci_hygiene._disk_primary_ok", return_value=(True, "ok")
    ), patch("pci_hygiene._security_agent_present", return_value=(True, "ok")):
        out = run_pci_hygiene({}, dry_run=False)
    assert "net.risky_ports" in out["failed_ids"]
