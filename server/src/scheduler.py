"""Ordonnanceur de tâches périodiques de la plateforme.

Avant ce module, chaque comportement récurrent (détection hors ligne, escalade,
purge d'inventaire, santé plateforme, sondes réseau, rapports planifiés) était
déclenché à l'intérieur du handler de heartbeat. Conséquence : lors d'une panne
de parc — précisément le scénario que le produit doit détecter — plus aucun
agent n'émettait de heartbeat, donc plus aucune évaluation ne tournait et
aucune alerte AGENT_OFFLINE n'était levée.

Les jobs tournent ici dans un thread dédié, avec une session SQLAlchemy propre
par exécution. Le thread est démarré au startup FastAPI et arrêté au shutdown.

Refs: ALR-002, ALR-006, NFR-010, DSH-007, AGT-029.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal

logger = logging.getLogger(__name__)

# Un job trop lent ne doit pas décaler indéfiniment les suivants : on log au-delà.
SLOW_JOB_WARN_SECONDS = 10.0


@dataclass
class Job:
    """Une tâche périodique."""

    name: str
    interval_seconds: float
    func: Callable[[Session], Any]
    #: exécuter dès le démarrage plutôt qu'après un premier intervalle
    run_on_start: bool = True
    next_run: float = 0.0
    last_run_at: Optional[str] = None
    last_duration_ms: Optional[float] = None
    last_error: Optional[str] = None
    run_count: int = 0
    error_count: int = 0
    last_result: Any = field(default=None, repr=False)

    def state(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self.last_run_at,
            "last_duration_ms": self.last_duration_ms,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }


class PlatformScheduler:
    """Boucle de jobs périodiques dans un thread démon.

    Les services appelés sont du SQLAlchemy synchrone : un thread dédié évite
    de bloquer la boucle d'événements d'uvicorn.
    """

    def __init__(self, tick_seconds: float = 1.0) -> None:
        self._jobs: List[Job] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._tick = tick_seconds
        self._lock = threading.Lock()
        self.started_at: Optional[str] = None

    # ------------------------------------------------------------------ jobs

    def register(
        self,
        name: str,
        interval_seconds: float,
        func: Callable[[Session], Any],
        run_on_start: bool = True,
    ) -> None:
        if interval_seconds <= 0:
            logger.warning("Job %s ignoré : intervalle invalide (%s)", name, interval_seconds)
            return
        with self._lock:
            if any(j.name == name for j in self._jobs):
                logger.warning("Job %s déjà enregistré, ignoré", name)
                return
            self._jobs.append(
                Job(
                    name=name,
                    interval_seconds=float(interval_seconds),
                    func=func,
                    run_on_start=run_on_start,
                    next_run=0.0 if run_on_start else time.monotonic() + interval_seconds,
                )
            )
            logger.info("Job planifié : %s toutes les %ss", name, interval_seconds)

    def jobs_state(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.state() for j in self._jobs]

    def job_result(self, name: str) -> Any:
        with self._lock:
            for j in self._jobs:
                if j.name == name:
                    return j.last_result
        return None

    # --------------------------------------------------------------- runtime

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="cbc-scheduler", daemon=True
        )
        self._thread.start()
        self.started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Ordonnanceur démarré (%d jobs)", len(self._jobs))

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("Ordonnanceur arrêté")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            with self._lock:
                due = [j for j in self._jobs if j.next_run <= now]
            for job in due:
                if self._stop.is_set():
                    break
                self._execute(job)
                # Replanifier depuis la fin d'exécution : un job lent ne
                # s'auto-empile pas.
                job.next_run = time.monotonic() + job.interval_seconds
            self._stop.wait(self._tick)

    def _execute(self, job: Job) -> None:
        started = time.monotonic()
        db = SessionLocal()
        try:
            job.last_result = job.func(db)
            job.last_error = None
        except Exception as exc:  # noqa: BLE001 — un job ne doit jamais tuer la boucle
            job.last_error = f"{type(exc).__name__}: {exc}"
            job.error_count += 1
            logger.exception("Job %s en échec", job.name)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                logger.debug("Rollback impossible pour %s", job.name, exc_info=True)
        finally:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                logger.debug("Fermeture de session impossible pour %s", job.name, exc_info=True)
            duration = (time.monotonic() - started) * 1000.0
            job.last_duration_ms = round(duration, 2)
            job.last_run_at = datetime.now(timezone.utc).isoformat()
            job.run_count += 1
            if duration > SLOW_JOB_WARN_SECONDS * 1000.0:
                logger.warning(
                    "Job %s lent : %.0f ms (intervalle %ss)",
                    job.name,
                    duration,
                    job.interval_seconds,
                )


scheduler = PlatformScheduler()


# --------------------------------------------------------------------- jobs


def job_offline_and_escalation(db: Session) -> Dict[str, int]:
    """ALR-002 + ALR-006 — détection hors ligne et escalade.

    Doit tourner indépendamment des heartbeats : c'est justement leur absence
    qui doit déclencher l'alerte.
    """
    from src.alert_service import AlertService

    AlertService.check_offline_agents(db)
    escalated = AlertService.escalate_unacked(db)
    return {"escalated": escalated}


def job_purge_stale_agents(db: Session) -> Dict[str, int]:
    """Purge d'inventaire des agents désinstallés/abandonnés."""
    from src.agent_purge import purge_stale_agents

    actions = purge_stale_agents(db)
    if actions:
        db.commit()
        try:
            from src.cache_service import cache_service

            cache_service.delete_pattern("agents:*")
        except Exception:  # noqa: BLE001 — le cache est optionnel
            logger.debug("Invalidation cache agents impossible", exc_info=True)
    return {
        "retired": sum(1 for a in actions if a.get("action") == "retired"),
        "deleted": sum(1 for a in actions if a.get("action") == "deleted"),
        "purged": len(actions),
    }


def job_platform_health(db: Session) -> Dict[str, Any]:
    """NFR-010 — sonder les composants critiques sans attendre qu'un humain
    ouvre l'onglet Paramètres.

    Le résultat est mémorisé sur le job : `/health/platform` peut le servir
    sans re-sonder, et une transition vers `unhealthy` est journalisée.
    """
    from src.platform_health import aggregate_platform_health

    previous = scheduler.job_result("platform_health") or {}
    current = aggregate_platform_health(db)

    prev_components = (previous or {}).get("components", {})
    for name, comp in current.get("components", {}).items():
        was = str(prev_components.get(name, {}).get("status", "")).lower()
        now_status = str(comp.get("status", "")).lower()
        if was and was != now_status:
            level = logger.warning if now_status not in ("healthy", "ok") else logger.info
            level("Composant plateforme %s : %s -> %s", name, was, now_status)
    return current


def job_apply_retention(db: Session) -> Dict[str, int]:
    """STO-002 — applique la politique de rétention configurée.

    La table `retention_config` était administrable depuis l'interface mais
    aucun traitement ne la lisait : les alertes résolues et les heartbeats
    s'accumulaient indéfiniment. Sur un parc de plusieurs centaines d'hôtes
    émettant toutes les 30 secondes, la table des heartbeats est de loin la
    plus volumineuse de la base.

    Deux précautions :

    * seules les alertes **résolues ou archivées** sont supprimées — une
      alerte encore ouverte ou acquittée reste visible quel que soit son âge ;
    * la piste d'audit n'est jamais purgée ici. Sa conservation relève d'une
      obligation réglementaire (COBAC) et doit faire l'objet d'une décision
      explicite de CBC, pas d'un effet de bord d'un réglage d'exploitation.
    """
    from src.models import Alert, AlertEvent, AlertStatus, Heartbeat, RetentionConfig

    config = db.query(RetentionConfig).filter(RetentionConfig.id == "default").first()
    # Test explicite sur None : `0 or 30` vaut 30, si bien qu'une rétention
    # réglée à 0 (« conserver sans limite ») aurait au contraire purgé à
    # 30 jours.
    alerts_days = int(
        config.alerts_days if config is not None and config.alerts_days is not None else 30
    )
    heartbeats_days = int(
        config.heartbeats_days if config is not None and config.heartbeats_days is not None else 7
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    removed = {"alerts": 0, "alert_events": 0, "heartbeats": 0}

    if heartbeats_days > 0:
        cutoff = now - timedelta(days=heartbeats_days)
        removed["heartbeats"] = (
            db.query(Heartbeat)
            .filter(Heartbeat.created_at < cutoff)
            .delete(synchronize_session=False)
        )

    if alerts_days > 0:
        cutoff = now - timedelta(days=alerts_days)
        stale = (
            db.query(Alert.id)
            .filter(
                Alert.started_at < cutoff,
                Alert.status.in_([AlertStatus.RESOLVED, AlertStatus.ARCHIVED]),
            )
            .all()
        )
        stale_ids = [row[0] for row in stale]
        if stale_ids:
            # Supprimer d'abord les évènements : ils référencent l'alerte.
            # Par lots, pour ne pas dépasser la limite de paramètres SQLite.
            for start in range(0, len(stale_ids), 500):
                batch = stale_ids[start : start + 500]
                removed["alert_events"] += (
                    db.query(AlertEvent)
                    .filter(AlertEvent.alert_id.in_(batch))
                    .delete(synchronize_session=False)
                )
                removed["alerts"] += (
                    db.query(Alert)
                    .filter(Alert.id.in_(batch))
                    .delete(synchronize_session=False)
                )

    if any(removed.values()):
        db.commit()
        logger.info(
            "Rétention appliquée : %d heartbeats, %d alertes, %d évènements",
            removed["heartbeats"],
            removed["alerts"],
            removed["alert_events"],
        )
    return removed


#: Niveaux d'agrégat : (niveau, fenêtre PromQL, métrique source, durée en s).
#: Le niveau journalier se calcule à partir du niveau horaire, pas des points
#: bruts : agréger 86 400 s de données brutes à chaque passage serait inutile
#: et coûteux.
ROLLUP_TIERS = (
    ("1h", "1h", "cbc_metric", 3600),
    ("1d", "1d", "cbc_metric_1h", 86400),
)

#: Profondeur de rattrapage au premier passage. Au-delà, les intervalles
#: anciens sont considérés comme définitivement manqués plutôt que de lancer
#: un rattrapage de plusieurs mois au démarrage.
ROLLUP_BACKFILL_HOURS = 48


def job_tsdb_rollup(db: Session) -> Dict[str, Any]:
    """STO-002 — produit les séries agrégées 1h puis 1d.

    VictoriaMetrics en édition open source ne sait pas sous-échantillonner :
    c'est une fonction de l'édition entreprise. Les agrégats sont donc calculés
    ici et réécrits comme des séries distinctes (`cbc_metric_1h`,
    `cbc_metric_1d`), étiquetées par fonction d'agrégation.

    Intérêt réel : une requête sur treize mois lit quelques centaines de points
    agrégés au lieu de plusieurs dizaines de milliers de points bruts.

    Le traitement est idempotent — la dernière borne traitée est mémorisée — et
    n'agrège jamais l'intervalle en cours, qui donnerait une valeur partielle
    jamais corrigée.
    """
    from src.models import TsdbRollupState
    from src.tsdb_service import RollupWriter, tsdb

    if not tsdb.enabled:
        return {"skipped": "tsdb désactivé"}

    now = datetime.now(timezone.utc)
    writer = RollupWriter(tsdb)
    summary: Dict[str, Any] = {}

    for tier, window, source_metric, bucket_seconds in ROLLUP_TIERS:
        state = db.query(TsdbRollupState).filter(TsdbRollupState.tier == tier).first()
        if state is None:
            state = TsdbRollupState(tier=tier)
            db.add(state)

        if state.last_bucket_at is not None:
            since = state.last_bucket_at.replace(tzinfo=timezone.utc)
        else:
            since = now - timedelta(hours=ROLLUP_BACKFILL_HOURS)

        result = writer.run_tier(
            tier=tier,
            window=window,
            source_metric=source_metric,
            bucket_seconds=bucket_seconds,
            since=since,
            now=now,
        )

        if result["buckets"]:
            state.last_bucket_at = result["last_bucket"].replace(tzinfo=None)
            state.buckets_written = (state.buckets_written or 0) + result["buckets"]
            state.samples_written = (state.samples_written or 0) + result["samples"]
        state.last_run_at = now.replace(tzinfo=None)
        summary[tier] = {"buckets": result["buckets"], "samples": result["samples"]}

    db.commit()
    total = sum(v["buckets"] for v in summary.values())
    if total:
        logger.info("Agrégats TSDB : %s", summary)
    return summary


def register_default_jobs() -> None:
    """Enregistre les jobs de la plateforme. Idempotent."""
    scheduler.register(
        "offline_and_escalation",
        settings.offline_check_interval_seconds,
        job_offline_and_escalation,
    )
    # Pas de run_on_start : les sondes sortantes (Redis, VictoriaMetrics, Loki)
    # ne doivent pas s'exécuter pendant le démarrage de l'application.
    scheduler.register(
        "platform_health",
        settings.notification_channel_health_check_interval_seconds,
        job_platform_health,
        run_on_start=False,
    )
    # L'inventaire bouge lentement : une passe par heure suffit et évite un
    # scan complet de la table à chaque minute.
    scheduler.register("purge_stale_agents", 3600, job_purge_stale_agents)
    # La rétention est une opération de fond : une passe par heure suffit, et
    # `run_on_start=False` évite une suppression massive pendant le démarrage.
    scheduler.register("apply_retention", 3600, job_apply_retention, run_on_start=False)
    # Les agrégats se calculent sur des intervalles terminés : une passe par
    # demi-heure suffit à rattraper l'heure écoulée sans jamais agréger
    # l'intervalle courant.
    scheduler.register("tsdb_rollup", 1800, job_tsdb_rollup, run_on_start=False)
