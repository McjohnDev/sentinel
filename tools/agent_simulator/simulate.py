#!/usr/bin/env python3
"""FS0-09 — Agent simulator: emit valid/invalid metric.v1 payloads.

Usage:
  python tools/agent_simulator/simulate.py --hosts 5
  python tools/agent_simulator/simulate.py --invalid
  python tools/agent_simulator/simulate.py --post http://localhost:8443/api/ingest/metrics
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.protocols import MetricV1  # noqa: E402


def make_metric(host: str, agent_id: uuid.UUID, family: str, name: str, value: float, unit: str) -> Dict[str, Any]:
    m = MetricV1(
        schema="metric.v1",
        agent_id=agent_id,
        host=host,
        ts=datetime.now(timezone.utc),
        family=family,
        name=name,
        value=value,
        unit=unit,
        labels={"env": "sim", "group": "simulator"},
        message_id=uuid.uuid4(),
    )
    return m.to_wire_dict()


def simulate_host(index: int) -> List[Dict[str, Any]]:
    host = f"sim-host-{index:03d}.local"
    agent_id = uuid.uuid4()
    return [
        make_metric(host, agent_id, "cpu", "cpu.total.utilization", round(random.uniform(5, 95), 2), "percent"),
        make_metric(host, agent_id, "memory", "memory.used.percent", round(random.uniform(20, 90), 2), "percent"),
        make_metric(host, agent_id, "disk", "disk.used.percent", round(random.uniform(30, 95), 2), "percent"),
    ]


def invalid_payload() -> Dict[str, Any]:
    return {
        "schema": "metric.v2",
        "agent_id": "bad",
        "host": "",
        "ts": "not-a-date",
        "family": "cpu",
        "name": "cpu.total.utilization",
        "value": "hot",
        "unit": "percent",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CBC agent metric simulator")
    parser.add_argument("--hosts", type=int, default=3, help="Number of virtual hosts")
    parser.add_argument("--invalid", action="store_true", help="Emit one invalid payload")
    parser.add_argument("--post", type=str, default="", help="Optional HTTP POST URL")
    parser.add_argument("--out", type=str, default="", help="Write JSONL to file")
    args = parser.parse_args()

    batch: List[Dict[str, Any]] = []
    if args.invalid:
        batch.append(invalid_payload())
    else:
        for i in range(1, args.hosts + 1):
            batch.extend(simulate_host(i))

    # Validate valid ones
    ok = 0
    bad = 0
    for item in batch:
        try:
            MetricV1.model_validate(item)
            ok += 1
        except Exception:
            bad += 1

    print(json.dumps({"count": len(batch), "valid": ok, "invalid": bad, "payloads": batch}, indent=2))

    if args.out:
        path = Path(args.out)
        with path.open("w", encoding="utf-8") as f:
            for item in batch:
                f.write(json.dumps(item) + "\n")
        print(f"wrote {path}", file=sys.stderr)

    if args.post:
        try:
            import urllib.request

            data = json.dumps({"metrics": batch}).encode("utf-8")
            req = urllib.request.Request(
                args.post,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"POST {args.post} -> {resp.status}", file=sys.stderr)
        except Exception as exc:
            print(f"POST failed (endpoint may not exist yet): {exc}", file=sys.stderr)
            return 2

    return 0 if bad == 0 or args.invalid else 1


if __name__ == "__main__":
    raise SystemExit(main())
