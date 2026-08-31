"""Self-hosted VictoriaMetrics client — no cloud account (ADR-001 / STO-001)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

METRIC_NAME = "cbc_metric"


def _escape_label(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _to_unix_ms(ts: datetime) -> int:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp() * 1000)


def metric_to_prometheus_line(
    name: str,
    value: float,
    ts: datetime,
    labels: Dict[str, str],
) -> str:
    parts = [f'{k}="{_escape_label(v)}"' for k, v in sorted(labels.items()) if v is not None and v != ""]
    label_str = ",".join(parts)
    return f"{METRIC_NAME}{{{label_str}}} {value} {_to_unix_ms(ts)}"


class VictoriaMetricsClient:
    """Write/query VictoriaMetrics over HTTP. Local Docker only — no signup."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 8.0) -> None:
        resolved = settings.victoria_metrics_url if base_url is None else base_url
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout
        self.enabled = bool(self.base_url)

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "url": self.base_url}
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
            ok = resp.status_code == 200
            return {
                "status": "healthy" if ok else "unhealthy",
                "url": self.base_url,
                "http_status": resp.status_code,
            }
        except Exception as exc:
            return {"status": "unhealthy", "url": self.base_url, "error": str(exc)}

    def write_prometheus(self, lines: Iterable[str]) -> int:
        payload = "\n".join(line for line in lines if line).strip()
        if not payload or not self.enabled:
            return 0
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/import/prometheus",
                content=payload + "\n",
                headers={"Content-Type": "text/plain"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return payload.count("\n") + 1
        except Exception:
            logger.exception("VictoriaMetrics write failed")
            return 0

    def write_metric_v1(self, metrics: List[Any]) -> int:
        """Persist canonical metric.v1 points."""
        lines: List[str] = []
        for m in metrics:
            labels = {
                "name": m.name,
                "family": m.family,
                "agent_id": str(m.agent_id),
                "host": m.host,
                "unit": m.unit,
            }
            labels.update({k: str(v) for k, v in (m.labels or {}).items()})
            lines.append(metric_to_prometheus_line(m.name, float(m.value), m.ts, labels))
        return self.write_prometheus(lines)

    def write_heartbeat_samples(
        self,
        agent_id: str,
        host: str,
        ts: datetime,
        cpu_percent: float,
        ram_percent: float,
        disk_percent: float,
    ) -> int:
        """Mirror legacy heartbeat gauges into the TSDB so history works without plugins."""
        samples = [
            ("cpu.total.utilization", "cpu", cpu_percent, {"core": "all"}),
            ("memory.used.percent", "memory", ram_percent, {}),
            ("disk.used.percent", "disk", disk_percent, {"mount": "/"}),
        ]
        lines = []
        for name, family, value, extra in samples:
            labels = {
                "name": name,
                "family": family,
                "agent_id": agent_id,
                "host": host,
                "unit": "percent",
                "source": "heartbeat",
                **extra,
            }
            lines.append(metric_to_prometheus_line(name, float(value), ts, labels))
        return self.write_prometheus(lines)

    def query_range(
        self,
        agent_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        step: str = "60s",
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "result": []}
        query = f'{METRIC_NAME}{{agent_id="{_escape_label(agent_id)}",name="{_escape_label(metric_name)}"}}'
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            series = []
            for item in data.get("data", {}).get("result", []):
                series.append(
                    {
                        "metric": item.get("metric", {}),
                        "points": [
                            {"ts": datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(), "value": float(val)}
                            for ts, val in item.get("values", [])
                        ],
                    }
                )
            return {"status": "success", "query": query, "result": series}
        except Exception as exc:
            logger.exception("VictoriaMetrics query failed")
            return {"status": "error", "query": query, "error": str(exc), "result": []}


tsdb = VictoriaMetricsClient()


# ---------------------------------------------------------------- agrégats
#
# VictoriaMetrics en édition open source ne propose pas de sous-échantillonnage
# natif : c'est une fonction de l'édition entreprise. Les agrégats sont donc
# calculés par la plateforme et réécrits comme des séries distinctes, portant
# une étiquette `rollup` (1h, 1d) et une étiquette `agg` (avg, min, max).
#
# Une série agrégée n'écrase jamais la série brute : les deux coexistent, et
# une requête longue portée interroge la série agrégée, beaucoup plus légère.

ROLLUP_LABEL = "rollup"
AGG_FUNCTIONS = ("avg", "min", "max")


def rollup_metric_name(tier: str) -> str:
    """Nom de métrique d'un niveau d'agrégat (ex. cbc_metric_1h)."""
    return f"{METRIC_NAME}_{tier}"


class RollupWriter:
    """Calcule et réécrit les agrégats d'un niveau donné.

    Le calcul est délégué à VictoriaMetrics (`avg_over_time` et consorts) :
    une requête instantanée à la borne d'un intervalle renvoie la valeur
    agrégée de *toutes* les séries sur cet intervalle, ce qui évite de
    rapatrier les points bruts.
    """

    def __init__(self, client: "VictoriaMetricsClient") -> None:
        self.client = client

    def _instant(self, query: str, at: datetime) -> List[Dict[str, Any]]:
        if not self.client.enabled:
            return []
        try:
            resp = httpx.get(
                f"{self.client.base_url}/api/v1/query",
                params={"query": query, "time": at.timestamp()},
                timeout=self.client.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("result", [])
        except Exception:
            logger.exception("Requête d'agrégat en échec: %s", query)
            return []

    def build_bucket(
        self,
        tier: str,
        window: str,
        source_metric: str,
        bucket_end: datetime,
    ) -> List[str]:
        """Lignes Prometheus pour un intervalle, tous agrégats confondus."""
        lines: List[str] = []
        target = rollup_metric_name(tier)
        for agg in AGG_FUNCTIONS:
            query = f"{agg}_over_time({source_metric}[{window}])"
            for item in self._instant(query, bucket_end):
                metric = dict(item.get("metric") or {})
                value = item.get("value")
                if not value or len(value) < 2:
                    continue
                try:
                    numeric = float(value[1])
                except (TypeError, ValueError):
                    continue
                # `__name__` porte le nom de la série source : il est remplacé
                # par le nom du niveau d'agrégat.
                metric.pop("__name__", None)
                metric[ROLLUP_LABEL] = tier
                metric["agg"] = agg
                label_str = ",".join(
                    f'{k}="{_escape_label(str(v))}"' for k, v in sorted(metric.items())
                )
                lines.append(f"{target}{{{label_str}}} {numeric} {_to_unix_ms(bucket_end)}")
        return lines

    def run_tier(
        self,
        tier: str,
        window: str,
        source_metric: str,
        bucket_seconds: int,
        since: datetime,
        now: datetime,
        max_buckets: int = 48,
    ) -> Dict[str, Any]:
        """Agrège tous les intervalles **terminés** entre `since` et `now`.

        L'intervalle courant est volontairement exclu : l'agréger produirait
        une valeur partielle qui ne serait jamais corrigée.
        """
        written = 0
        buckets = 0
        last_end = since

        # Aligner sur la borne d'intervalle pour que les points d'agrégat
        # tombent toujours au même endroit, quel que soit l'instant d'exécution.
        epoch = int(since.timestamp())
        aligned = epoch - (epoch % bucket_seconds) + bucket_seconds
        cutoff = int(now.timestamp()) - (int(now.timestamp()) % bucket_seconds)

        while aligned <= cutoff and buckets < max_buckets:
            bucket_end = datetime.fromtimestamp(aligned, tz=timezone.utc)
            lines = self.build_bucket(tier, window, source_metric, bucket_end)
            if lines:
                written += self.client.write_prometheus(lines)
            last_end = bucket_end
            buckets += 1
            aligned += bucket_seconds

        return {"tier": tier, "buckets": buckets, "samples": written, "last_bucket": last_end}
