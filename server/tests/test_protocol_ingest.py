"""Tests for metric.v1 validation + DLQ (FS1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVER_SRC = Path(__file__).resolve().parents[1]
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))

from src.protocol_ingest import DeadLetterQueue, validate_metrics_batch  # noqa: E402


def test_validate_batch_splits_valid_and_invalid(tmp_path):
    dlq = DeadLetterQueue(tmp_path / "dlq.jsonl")
    valid_fix = json.loads(
        (ROOT / "shared" / "fixtures" / "metric.valid.json").read_text(encoding="utf-8")
    )
    invalid_fix = json.loads(
        (ROOT / "shared" / "fixtures" / "metric.invalid.json").read_text(encoding="utf-8")
    )
    valid, rejected = validate_metrics_batch([valid_fix, invalid_fix], dlq)
    assert len(valid) == 1
    assert rejected == 1
    assert dlq.path.exists()
    lines = dlq.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert dlq.size() == 1
    tail = dlq.tail(10)
    assert len(tail) == 1
    assert "error" in tail[0]
