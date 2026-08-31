"""Helpers to remove agents and their related rows safely."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.models import (
    ActionApproval,
    Agent,
    Alert,
    AlertEvent,
    AvailabilityPolicy,
    CoverageOverlap,
    FileMonitoring,
    Heartbeat,
    MachineType,
    MailTemplate,
    MaintenanceWindow,
    PilotHost,
    RemoteTask,
    ServiceMonitoring,
    MonitoredFile,
    MonitoredService,
)

logger = logging.getLogger(__name__)

#: Horloge monotone du démarrage plateforme. Renseignée par le lifespan
#: FastAPI. Tant qu'elle vaut None, aucune purge n'est autorisée : on ne sait
#: pas depuis combien de temps le serveur écoute, donc on ne peut pas dire si
#: le silence d'un agent vient de l'agent ou de nous.
_PLATFORM_START_MONOTONIC: Optional[float] = None


def note_platform_start(assume_uptime_seconds: float = 0.0) -> None:
    """À appeler au démarrage de l'API (lifespan).

    `assume_uptime_seconds` permet aux tests de simuler une plateforme déjà en
    ligne depuis un certain temps sans attendre réellement.
    """
    global _PLATFORM_START_MONOTONIC
    _PLATFORM_START_MONOTONIC = time.monotonic() - max(0.0, assume_uptime_seconds)


def platform_uptime_seconds() -> Optional[float]:
    """Secondes écoulées depuis le démarrage de l'API, None si inconnu."""
    if _PLATFORM_START_MONOTONIC is None:
        return None
    return max(0.0, time.monotonic() - _PLATFORM_START_MONOTONIC)


def purge_allowed() -> bool:
    """La plateforme est-elle en ligne depuis assez longtemps pour purger ?"""
    uptime = platform_uptime_seconds()
    if uptime is None:
        return False
    grace = int(getattr(settings, "agent_purge_startup_grace_seconds", 900) or 0)
    return uptime >= grace


def wall_silence_seconds(agent: Agent, now: Optional[datetime] = None) -> float:
    """Silence brut, à l'horloge murale, depuis le dernier signe de vie."""
    now = now or datetime.utcnow()
    last_seen = agent.last_communication or agent.enrolled_at or agent.created_at
    if last_seen is None:
        return float("inf")
    return max(0.0, (now - last_seen).total_seconds())


def effective_silence_seconds(agent: Agent, now: Optional[datetime] = None) -> float:
    """Silence imputable à l'agent, en excluant les périodes où l'API était arrêtée.

    Un agent ne peut pas émettre vers un serveur éteint. Compter ces heures-là
    comme du silence revenait à supprimer tout le parc au premier redémarrage
    après une coupure prolongée.
    """
    uptime = platform_uptime_seconds()
    if uptime is None:
        return 0.0
    return min(wall_silence_seconds(agent, now=now), uptime)


def is_lab_or_sim_agent(agent: Agent) -> bool:
    """True for load-test / simulator / obvious lab hosts — not production CBC hosts."""
    hostname = (agent.hostname or "").lower()
    machine_id = (agent.machine_id or "").lower()
    location = (agent.location or "").lower()
    os_version = (agent.os_version or "").lower()
    name = (agent.name or "").lower()

    if os_version in {"sim", "load-1.0"} or location in {"load-lab", "simulator"}:
        return True
    prefixes = (
        "sim-host-",
        "load-sim-",
        "fs7-load-",
        "load-",
        "sim-",
    )
    for p in prefixes:
        if hostname.startswith(p) or machine_id.startswith(p) or name.startswith(p):
            return True
    if "simulator" in location or ".local" in hostname and hostname.startswith("sim"):
        return True
    return False


def delete_agent_with_deps(db: Session, agent: Agent) -> None:
    """Delete an agent and dependent rows that lack ORM cascade."""
    agent_id = agent.id

    # Approvals may reference remote tasks — clear approvals first.
    task_ids = [t.id for t in db.query(RemoteTask).filter(RemoteTask.agent_id == agent_id).all()]
    if task_ids:
        db.query(ActionApproval).filter(ActionApproval.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(RemoteTask).filter(RemoteTask.agent_id == agent_id).delete(synchronize_session=False)

    db.query(Heartbeat).filter(Heartbeat.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AlertEvent).filter(AlertEvent.agent_id == agent_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.agent_id == agent_id).delete(synchronize_session=False)
    db.query(ServiceMonitoring).filter(ServiceMonitoring.agent_id == agent_id).delete(synchronize_session=False)
    db.query(FileMonitoring).filter(FileMonitoring.agent_id == agent_id).delete(synchronize_session=False)
    db.query(MonitoredService).filter(MonitoredService.agent_id == agent_id).delete(synchronize_session=False)
    db.query(MonitoredFile).filter(MonitoredFile.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AvailabilityPolicy).filter(AvailabilityPolicy.agent_id == agent_id).delete(synchronize_session=False)
    db.query(MaintenanceWindow).filter(MaintenanceWindow.agent_id == agent_id).delete(synchronize_session=False)
    db.query(CoverageOverlap).filter(CoverageOverlap.agent_id == agent_id).delete(synchronize_session=False)
    db.query(PilotHost).filter(PilotHost.agent_id == agent_id).delete(synchronize_session=False)
    db.query(MailTemplate).filter(MailTemplate.agent_id == agent_id).delete(synchronize_session=False)

    db.delete(agent)


def _purge_after_seconds(agent: Agent) -> int:
    mt = agent.machine_type
    value = mt.value if hasattr(mt, "value") else str(mt or "")
    if value == MachineType.SERVER.value or value == "server":
        return int(getattr(settings, "agent_server_stale_purge_after_seconds", 86400) or 86400)
    return int(getattr(settings, "agent_stale_purge_after_seconds", 604800) or 604800)


#: Statut d'un agent mis de côté par la purge : la ligne et la clé d'auth sont
#: conservées, il se ré-active tout seul au premier heartbeat authentifié.
RETIRED = "retired"

#: Hôte dont l'agent a été désinstallé et qui l'a annoncé. Différence de fond
#: avec RETIRED : ici le retrait est *voulu et déclaré*, il ne relève donc ni
#: de l'alerte ni de la relance — seulement de la conservation de la trace.
UNINSTALLED = "uninstalled"

#: Statuts hors supervision active : ni vivants, ni candidats à la relance.
INACTIVE_STATUSES = ("revoked", "deleted", UNINSTALLED)

#: Fenêtre pendant laquelle un agent tout juste enrôlé est protégé, le temps
#: que son premier heartbeat arrive.
ENROLLMENT_GRACE = timedelta(minutes=2)


def is_agent_live(agent: Agent, now: Optional[datetime] = None, timeout_seconds: Optional[int] = None) -> bool:
    """True when the agent is actively heartbeating (or freshly enrolled)."""
    now = now or datetime.utcnow()
    timeout = timedelta(seconds=timeout_seconds if timeout_seconds is not None else settings.heartbeat_timeout_seconds)
    if agent.status in INACTIVE_STATUSES:
        return False
    # Un enrôlement tout frais protège l'agent même s'il a déjà un
    # last_communication : au ré-enrôlement d'un hôte connu, la plateforme met
    # à jour last_communication, l'ancienne condition « is None » ne s'appliquait
    # donc jamais et la purge pouvait effacer un agent enrôlé la seconde d'avant.
    enrolled_at = agent.enrolled_at
    if enrolled_at is not None and (now - enrolled_at) <= ENROLLMENT_GRACE:
        return True
    last_seen = agent.last_communication
    return bool(
        agent.status == "active"
        and last_seen is not None
        and (now - last_seen) <= timeout
    )


def last_seen_age_seconds(agent: Agent, now: Optional[datetime] = None) -> Optional[int]:
    now = now or datetime.utcnow()
    last_seen = agent.last_communication
    if last_seen is None:
        return None
    return max(0, int((now - last_seen).total_seconds()))


def derived_agent_status(
    agent: Agent,
    now: Optional[datetime] = None,
    timeout_seconds: Optional[int] = None,
) -> str:
    """Single live/offline/revoked value for list and detail APIs."""
    if agent.status == "revoked":
        return "revoked"
    if agent.status == UNINSTALLED:
        return UNINSTALLED
    if is_agent_live(agent, now=now, timeout_seconds=timeout_seconds):
        return "active"
    # « retired » reste un hors-ligne du point de vue de l'IHM : la nuance
    # (candidat à suppression) est portée par le champ `retired` de la charge.
    return "offline"


def _retired_delete_after_seconds() -> int:
    return int(getattr(settings, "agent_retired_delete_after_seconds", 2592000) or 2592000)


def purge_stale_agents(db: Session, *, now: Optional[datetime] = None) -> List[dict]:
    """Inventaire : mettre de côté les hôtes silencieux, supprimer les abandons.

    Deux étages, pour ne jamais détruire l'identité d'un agent encore vivant :

    1. silence > seuil machine  -> `status = retired`. La ligne et la clé
       d'auth survivent : si l'agent réapparaît, son heartbeat authentifié le
       remet en `active` sans nouveau jeton d'enrôlement.
    2. silence > délai de rétention des retirés -> suppression définitive.

    Le silence est mesuré en temps de fonctionnement plateforme
    (`effective_silence_seconds`) : une coupure du serveur ne compte pas
    contre les agents. Rien n'est purgé tant que l'API n'est pas en ligne
    depuis `agent_purge_startup_grace_seconds`.
    """
    now = now or datetime.utcnow()
    actions: List[dict] = []

    if not purge_allowed():
        uptime = platform_uptime_seconds()
        logger.info(
            "Purge inventaire ignorée : plateforme en ligne depuis %ss (sas %ss)",
            "?" if uptime is None else int(uptime),
            getattr(settings, "agent_purge_startup_grace_seconds", 900),
        )
        return actions

    candidate_ids = [
        agent.id
        for agent in db.query(Agent).all()
        if agent.status != "revoked" and not is_agent_live(agent, now=now)
    ]

    for agent_id in candidate_ids:
        # Relire la ligne sous verrou : entre la sélection ci-dessus et la
        # décision, l'agent a pu se ré-enrôler ou envoyer un heartbeat. Sans
        # cette relecture, la purge supprimait des agents redevenus vivants
        # une fraction de seconde plus tôt (course enrôlement / purge).
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .with_for_update(nowait=False)
            .first()
        )
        if agent is None:
            continue
        # Horloge relue au moment de la décision, sans écraser le `now` du
        # cycle : un appelant qui fixe l'heure (tests) garde la main.
        checked_at = datetime.utcnow()
        if is_agent_live(agent, now=checked_at) or agent.status == "revoked":
            continue

        silence = effective_silence_seconds(agent, now=checked_at)
        stale_after = _purge_after_seconds(agent)

        if agent.status == UNINSTALLED:
            # Désinstallation déclarée : le compte à rebours part de la
            # désinstallation, pas du dernier battement. On ne « retire » pas
            # un hôte déjà retiré, on ne fait qu'attendre l'échéance.
            reference = agent.uninstalled_at or agent.last_communication
            age = (checked_at - reference).total_seconds() if reference else float("inf")
            if age >= _retired_delete_after_seconds():
                actions.append(
                    {
                        "id": agent.id,
                        "hostname": agent.hostname,
                        "action": "deleted",
                        "reason": "uninstalled_expired",
                        "silent_for_seconds": int(silence),
                    }
                )
                delete_agent_with_deps(db, agent)
            continue

        if agent.status == RETIRED:
            # Suppression définitive : deux horloges doivent concorder. La
            # rétention se mesure au temps réel (sinon une plateforme
            # redémarrée chaque mois n'atteindrait jamais 30 jours de
            # fonctionnement continu et ne nettoierait plus rien), mais on
            # exige aussi un vrai silence observé, pour ne pas supprimer au
            # sortir d'une longue panne un hôte qui n'a pas encore eu le
            # temps de se manifester.
            wall = wall_silence_seconds(agent, now=checked_at)
            if wall >= _retired_delete_after_seconds() and silence >= stale_after:
                actions.append(
                    {
                        "id": agent.id,
                        "hostname": agent.hostname,
                        "action": "deleted",
                        "reason": "retired_expired",
                        "silent_for_seconds": int(wall),
                    }
                )
                delete_agent_with_deps(db, agent)
            continue

        if silence >= stale_after:
            agent.status = RETIRED
            agent.updated_at = checked_at
            actions.append(
                {
                    "id": agent.id,
                    "hostname": agent.hostname,
                    "action": "retired",
                    "reason": "stale",
                    "silent_for_seconds": int(silence),
                }
            )

    if actions:
        logger.warning(
            "Purge inventaire : %s retiré(s), %s supprimé(s)",
            sum(1 for a in actions if a["action"] == "retired"),
            sum(1 for a in actions if a["action"] == "deleted"),
        )
    return actions
