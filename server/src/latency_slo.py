"""FS7-02 — In-memory latency SLO samples (NFR-001/002/005)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional


# Budgets (seconds) — Lot 1
BUDGET_COLLECT_TO_UI_S = 60.0
BUDGET_DETECT_TO_NOTIFY_S = 30.0
BUDGET_PAGE_LOAD_S = 3.0


class LatencySLO:
    """Ring buffer of latency observations for dashboards / load reports."""

    def __init__(self, maxlen: int = 2000) -> None:
        self._lock = threading.Lock()
        self._collect_to_ingest: Deque[float] = deque(maxlen=maxlen)
        self._detect_to_notify: Deque[float] = deque(maxlen=maxlen)
        self._page_load: Deque[float] = deque(maxlen=maxlen)
        self._api_rtt: Deque[float] = deque(maxlen=maxlen)

    def record_collect_to_ingest(self, seconds: float) -> None:
        if seconds < 0:
            return
        with self._lock:
            self._collect_to_ingest.append(seconds)

    def record_detect_to_notify(self, seconds: float) -> None:
        if seconds < 0:
            return
        with self._lock:
            self._detect_to_notify.append(seconds)

    def record_page_load(self, seconds: float) -> None:
        if seconds < 0:
            return
        with self._lock:
            self._page_load.append(seconds)

    def record_api_rtt(self, seconds: float) -> None:
        if seconds < 0:
            return
        with self._lock:
            self._api_rtt.append(seconds)

    @staticmethod
    def _stats(samples: List[float], budget: float) -> Dict[str, Any]:
        if not samples:
            return {
                "count": 0,
                "p50_s": None,
                "p95_s": None,
                "max_s": None,
                "budget_s": budget,
                "within_budget": None,
            }
        ordered = sorted(samples)
        n = len(ordered)

        def pct(p: float) -> float:
            idx = min(n - 1, max(0, int(round((p / 100.0) * (n - 1)))))
            return round(ordered[idx], 4)

        p95 = pct(95)
        return {
            "count": n,
            "p50_s": pct(50),
            "p95_s": p95,
            "max_s": round(ordered[-1], 4),
            "budget_s": budget,
            "within_budget": p95 <= budget,
        }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            collect = list(self._collect_to_ingest)
            notify = list(self._detect_to_notify)
            page = list(self._page_load)
            rtt = list(self._api_rtt)
        return {
            "collect_to_ingest": self._stats(collect, BUDGET_COLLECT_TO_UI_S),
            "detect_to_notify": self._stats(notify, BUDGET_DETECT_TO_NOTIFY_S),
            "page_load": self._stats(page, BUDGET_PAGE_LOAD_S),
            "api_rtt": self._stats(rtt, BUDGET_PAGE_LOAD_S),
            "budgets": {
                "collect_to_ui_s": BUDGET_COLLECT_TO_UI_S,
                "detect_to_notify_s": BUDGET_DETECT_TO_NOTIFY_S,
                "page_load_s": BUDGET_PAGE_LOAD_S,
            },
            "observed_at": time.time(),
        }


latency_slo = LatencySLO()
