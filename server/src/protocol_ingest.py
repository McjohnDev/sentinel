"""metric.v1 validation + dead-letter helpers (PLT-002)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

logger = logging.getLogger(__name__)

# Ensure repo-root shared package is importable when server runs from server/
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.protocols import MetricV1  # noqa: E402


class DeadLetterQueue:
    """Append-only file DLQ for invalid payloads (Lot 1)."""

    def __init__(self, path: str | Path = "logs/dlq_metrics.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def push(self, payload: Any, error: str) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "error": error,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        logger.warning("DLQ write: %s", error)

    def size(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def tail(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.path.exists() or limit <= 0:
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        rows: List[Dict[str, Any]] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"error": "corrupt_dlq_line", "payload": line[:500]})
        return list(reversed(rows))


def validate_metrics_batch(
    items: List[Dict[str, Any]],
    dlq: DeadLetterQueue | None = None,
) -> Tuple[List[MetricV1], int]:
    """Validate a list of dicts as metric.v1. Invalid items go to DLQ."""
    valid: List[MetricV1] = []
    rejected = 0
    queue = dlq or DeadLetterQueue()
    for item in items:
        try:
            valid.append(MetricV1.model_validate(item))
        except ValidationError as exc:
            rejected += 1
            queue.push(item, str(exc.errors()))
    return valid, rejected
