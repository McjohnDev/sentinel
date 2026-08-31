#!/usr/bin/env python3
"""FS7-02 — Measure latency budgets (NFR-001/002/005).

Usage:
  python tools/latency/measure_budgets.py --base http://localhost:8443 --dashboard http://localhost:3000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http(
    method: str,
    url: str,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> Tuple[int, float, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = {"Accept": "*/*"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs, method=method)
    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            dt = time.perf_counter() - t0
            try:
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                parsed = {"bytes": len(raw)}
            return resp.status, dt, parsed
    except HTTPError as exc:
        dt = time.perf_counter() - t0
        return exc.code, dt, {"detail": exc.read().decode("utf-8", errors="replace")}
    except URLError as exc:
        return 0, time.perf_counter() - t0, {"detail": str(exc.reason)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8443")
    p.add_argument("--dashboard", default="http://localhost:3000")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default="Admin123!")
    args = p.parse_args()
    base = args.base.rstrip("/")

    status, login_s, login = http(
        "POST", f"{base}/api/auth/login", {"username": args.username, "password": args.password}
    )
    if status != 200:
        print(json.dumps({"error": "login failed", "status": status, "body": login}, indent=2))
        return 2
    token = login.get("access_token") or login.get("token")

    # NFR-005 — page / shell load
    st_page, page_s, _ = http("GET", args.dashboard)
    # report to API
    http(
        "POST",
        f"{base}/api/platform/latency/page",
        {"seconds": page_s, "path": "/"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # NFR-001 proxy — health RTT + platform latency snapshot
    st_h, health_s, _ = http("GET", f"{base}/health")
    st_p, _, platform = http(
        "GET", f"{base}/api/platform/status", headers={"Authorization": f"Bearer {token}"}
    )

    # Detect→notify budget is sampled server-side on alert notify; surface current stats
    latency = (platform or {}).get("latency") if st_p == 200 else {}

    report = {
        "story": "FS7-02",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "login_s": round(login_s, 4),
        "page_load": {
            "http_status": st_page,
            "seconds": round(page_s, 4),
            "budget_s": 3.0,
            "within_budget": st_page == 200 and page_s <= 3.0,
        },
        "api_health": {
            "http_status": st_h,
            "seconds": round(health_s, 4),
        },
        "server_latency_snapshot": latency,
        "budgets": {
            "collect_to_ui_s": 60,
            "detect_to_notify_s": 30,
            "page_load_s": 3,
        },
        "run_id": str(uuid.uuid4()),
    }
    print(json.dumps(report, indent=2))
    page_ok = report["page_load"]["within_budget"]
    return 0 if page_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
