"""Tests for durable buffer and L0 task rejection."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from durable_buffer import DurableBuffer  # noqa: E402
from task_handler import handle_incoming_tasks, reject_l0_task  # noqa: E402
from shared.protocols import TaskV1  # noqa: E402


def test_durable_buffer_roundtrip_and_prune(tmp_path):
    buf = DurableBuffer(tmp_path / "q.jsonl", max_bytes=10_000, max_age_seconds=24 * 3600)
    buf.enqueue("heartbeat", {"cpu_percent": 10})
    buf.enqueue("metrics", [{"schema": "metric.v1"}])
    assert len(buf) == 2
    records = buf.checkout()
    assert len(records) == 2
    assert records[0]["kind"] == "heartbeat"
    # Un prélèvement ne détruit rien : les enregistrements restent en attente
    # jusqu'à l'acquittement. L'assertion précédente (`len(buf) == 0` juste
    # après le retrait) validait en réalité la perte de données que le
    # mécanisme doit empêcher.
    assert len(buf) == 2
    buf.commit()
    assert len(buf) == 0


def test_durable_buffer_drops_old_records(tmp_path):
    path = tmp_path / "q.jsonl"
    old = {
        "ts": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        "kind": "heartbeat",
        "payload": {},
    }
    fresh = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "metrics",
        "payload": {},
    }
    path.write_text(json.dumps(old) + "\n" + json.dumps(fresh) + "\n", encoding="utf-8")
    buf = DurableBuffer(path, max_bytes=10_000, max_age_seconds=24 * 3600)
    buf.prune()
    left = buf.peek()
    assert len(left) == 1
    assert left[0]["kind"] == "metrics"


def test_l0_rejects_task_envelope():
    task = TaskV1(
        schema="task.v1",
        task_id=uuid4(),
        issued_by="user",
        signature="sig",
        plugin="service.manage",
        input={"service": "nginx", "operation": "restart"},
        dry_run=True,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    result = reject_l0_task(task)
    assert result.status == "rejected"
    assert "L0" in (result.rejection_reason or "")
    results = handle_incoming_tasks([task.to_wire_dict()])
    assert results[0]["status"] == "rejected"
