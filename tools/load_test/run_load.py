#!/usr/bin/env python3
"""FS7-01 — Sustained agent load harness (128 → 500).

Prerequisites on the API:
  ALLOW_LOAD_SIM=true
  RATE_LIMIT_DISABLED=true   # recommended for 128+ concurrent agents

Usage (from repo root):
  python tools/load_test/run_load.py --agents 128 --duration 60 --base http://localhost:8443
  python tools/load_test/run_load.py --agents 500 --duration 120 --out docs/architecture/FS7-LOAD-RESULTS.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(
    method: str,
    url: str,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"detail": raw}
        return exc.code, parsed
    except (URLError, TimeoutError, OSError) as exc:
        return 0, {"detail": str(exc)}


def login(base: str, username: str, password: str) -> str:
    status, data = http_json(
        "POST",
        f"{base}/api/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"login failed: {status} {data}")
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"login missing token: {data}")
    return token


def create_sim_agents(base: str, token: str, count: int, prefix: str) -> List[Dict[str, str]]:
    """Create agents in batches to avoid long transactions / huge responses."""
    remaining = count
    batch_idx = 0
    agents: List[Dict[str, str]] = []
    while remaining > 0:
        batch = min(25, remaining)
        status, data = http_json(
            "POST",
            f"{base}/api/platform/sim-agents",
            {"count": batch, "prefix": f"{prefix}-b{batch_idx}"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120.0,
        )
        if status != 200:
            raise RuntimeError(f"sim-agents failed: {status} {data}")
        agents.extend(data.get("agents") or [])
        remaining -= batch
        batch_idx += 1
        time.sleep(0.3)
    return agents


def heartbeat_once(base: str, auth_key: str) -> Tuple[bool, float, str]:
    t0 = time.perf_counter()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": round(random.uniform(5, 90), 2),
        "cpu_cores": 4,
        "ram_percent": round(random.uniform(20, 85), 2),
        "ram_total_gb": 16.0,
        "ram_used_gb": 8.0,
        "ram_free_gb": 8.0,
        "disk_percent": round(random.uniform(30, 80), 2),
        "disk_total_gb": 200.0,
        "disk_used_gb": 80.0,
        "disk_free_gb": 120.0,
        "uptime_seconds": 3600,
    }
    status, data = http_json(
        "POST",
        f"{base}/api/agents/heartbeat",
        payload,
        headers={"Authorization": auth_key},
        timeout=45.0,
    )
    dt = time.perf_counter() - t0
    ok = status == 200
    return ok, dt, "" if ok else str(data)


def metrics_once(base: str, agent_id: str, auth_key: str, hostname: str) -> Tuple[bool, float, str]:
    t0 = time.perf_counter()
    aid = uuid.UUID(agent_id) if len(agent_id) == 36 else uuid.uuid4()
    metric = {
        "schema": "metric.v1",
        "agent_id": str(aid),
        "host": hostname,
        "ts": datetime.now(timezone.utc).isoformat(),
        "family": "cpu",
        "name": "cpu.total.utilization",
        "value": round(random.uniform(5, 95), 2),
        "unit": "percent",
        "labels": {"env": "load"},
        "message_id": str(uuid.uuid4()),
    }
    status, data = http_json(
        "POST",
        f"{base}/api/ingest/metrics",
        {"metrics": [metric]},
        headers={"Authorization": auth_key},
        timeout=45.0,
    )
    dt = time.perf_counter() - t0
    ok = status == 200
    return ok, dt, "" if ok else str(data)


def worker_loop(
    base: str,
    agent: Dict[str, str],
    duration_s: int,
    interval_s: float,
    stop_at: float,
    counters: Dict[str, Any],
    lock: threading.Lock,
) -> None:
    time.sleep(random.uniform(0, min(3.0, interval_s)))
    while time.time() < stop_at:
        ok_hb, dt_hb, err_hb = heartbeat_once(base, agent["auth_key"])
        ok_m, dt_m, err_m = metrics_once(base, agent["id"], agent["auth_key"], agent["hostname"])
        with lock:
            counters["hb_ok"] += int(ok_hb)
            counters["hb_fail"] += int(not ok_hb)
            counters["met_ok"] += int(ok_m)
            counters["met_fail"] += int(not ok_m)
            counters["hb_lat"].append(dt_hb)
            counters["met_lat"].append(dt_m)
            if not ok_hb and len(counters["errors"]) < 20:
                counters["errors"].append(f"hb:{err_hb}")
            if not ok_m and len(counters["errors"]) < 20:
                counters["errors"].append(f"met:{err_m}")
        time.sleep(interval_s)


def pct(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="CBC FS7 load test")
    parser.add_argument("--base", default="http://localhost:8443")
    parser.add_argument("--agents", type=int, default=128)
    parser.add_argument("--duration", type=int, default=60, help="seconds of sustained traffic")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between cycles per agent")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin123!")
    parser.add_argument("--prefix", default="fs7-load")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    print(f"login {base} …", file=sys.stderr)
    token = login(base, args.username, args.password)
    print(f"creating {args.agents} sim agents …", file=sys.stderr)
    agents = create_sim_agents(base, token, args.agents, args.prefix)
    if len(agents) < args.agents:
        print(f"warning: only {len(agents)} agents created", file=sys.stderr)

    counters: Dict[str, Any] = {
        "hb_ok": 0,
        "hb_fail": 0,
        "met_ok": 0,
        "met_fail": 0,
        "hb_lat": [],
        "met_lat": [],
        "errors": [],
    }
    lock = threading.Lock()
    stop_at = time.time() + args.duration
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=min(len(agents), 48)) as pool:
        futs = [
            pool.submit(worker_loop, base, a, args.duration, args.interval, stop_at, counters, lock)
            for a in agents
        ]
        for f in as_completed(futs):
            f.result()

    elapsed = time.perf_counter() - t0
    status_code, platform = http_json(
        "GET",
        f"{base}/api/platform/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    report = {
        "story": "FS7-01",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "agents_requested": args.agents,
        "agents_created": len(agents),
        "duration_s": args.duration,
        "interval_s": args.interval,
        "wall_s": round(elapsed, 2),
        "heartbeats": {"ok": counters["hb_ok"], "fail": counters["hb_fail"], "p95_s": pct(counters["hb_lat"], 95)},
        "metrics": {"ok": counters["met_ok"], "fail": counters["met_fail"], "p95_s": pct(counters["met_lat"], 95)},
        "data_loss_suspect": counters["hb_fail"] > 0 or counters["met_fail"] > 0,
        "errors_sample": counters["errors"],
        "platform_status_http": status_code,
        "platform": platform if status_code == 200 else None,
        "pass_criteria": {
            "nfr004_agents": args.agents >= 128,
            "no_data_loss": counters["hb_fail"] == 0 and counters["met_fail"] == 0,
        },
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {args.out}", file=sys.stderr)

    ok = report["pass_criteria"]["no_data_loss"]
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
