"""Plan de supervision d'un hôte (point 6).

**Ce qui existait** : le paramétrage était éclaté et, pour l'essentiel, fictif.
Les seuils CPU/RAM/disque vivaient sur `Agent` et fonctionnaient ; en
revanche `ServiceMonitoringConfig` et `FileMonitoringConfig` n'étaient
*jamais écrits* — les endpoints `PUT /api/settings/*-monitoring` renvoyaient
la requête en écho, l'interface affichait « mise à jour avec succès » et
perdait tout au rafraîchissement, pendant que le moteur d'alerte comparait à
une liste codée en dur et vide.

**Choix de conception.** Les seuils restent là où ils fonctionnent déjà —
colonnes de `Agent`, lues par `AlertService._thresholds_for` et
`_disk_mount_rule_map_for_agent`, couvertes par des tests. Les recopier dans
une table « plan » aurait créé deux sources de vérité, c'est-à-dire
exactement la fragmentation qu'on cherche à supprimer. Ce module n'ajoute
donc que ce qui manquait (services et fichiers) et **présente l'ensemble
comme un plan unique** à l'API et à l'agent, quelle que soit la répartition
du stockage.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.models import (
    Agent,
    AlertSeverity,
    FileCondition,
    MonitoredFile,
    MonitoredService,
    ServiceState,
)

logger = logging.getLogger(__name__)

#: Seuils appliqués quand l'hôte n'en définit aucun. Ils ne sont pas écrits
#: en base : un hôte sans surcharge doit suivre les seuils globaux, et une
#: copie figée le déconnecterait de toute évolution de la politique centrale.
DEFAULT_CPU = (80.0, 90.0)
DEFAULT_RAM = (80.0, 90.0)
DEFAULT_DISK = (85.0, 95.0)

#: Cadence de battement retenue quand rien n'est réglé.
DEFAULT_HEARTBEAT_SECONDS = 30

#: Bornes acceptées. Le plancher évite qu'un réglage à une seconde noie la
#: plateforme sous les battements d'un parc entier ; le plafond est imposé par
#: le seuil de bascule hors ligne du serveur, qu'une cadence plus lente
#: franchirait à chaque cycle.
HEARTBEAT_MIN_SECONDS = 5


def max_heartbeat_seconds() -> int:
    """Cadence la plus lente encore compatible avec la détection hors ligne.

    Le serveur déclare un hôte hors ligne au-delà de `heartbeat_timeout_seconds`.
    Battre exactement à ce rythme le placerait à la limite en permanence : on
    garde une marge d'un tiers, de quoi absorber un battement perdu sans
    déclencher une fausse absence.
    """
    from src.config import settings

    timeout = int(getattr(settings, "heartbeat_timeout_seconds", 90) or 90)
    return max(HEARTBEAT_MIN_SECONDS, int(timeout * 2 / 3))


def effective_heartbeat_seconds(db: Session, agent: Agent) -> int:
    """Cadence retenue pour cet hôte : la sienne, sinon celle du parc.

    La valeur est bornée à l'écriture *et* ici : un réglage introduit
    directement en base, ou hérité d'une version antérieure, ne doit pas
    pouvoir rendre un hôte perpétuellement hors ligne.
    """
    from src.models import GlobalSettings

    own = getattr(agent, "heartbeat_interval_seconds", None)
    if own:
        chosen = int(own)
    else:
        row = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        chosen = int(getattr(row, "heartbeat_interval_seconds", None) or DEFAULT_HEARTBEAT_SECONDS)

    return max(HEARTBEAT_MIN_SECONDS, min(chosen, max_heartbeat_seconds()))


def _parse_mount_rules(raw: Optional[str]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Règles de partition illisibles, ignorées")
        return []
    if not isinstance(parsed, list):
        return []
    rules = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("mount"):
            continue
        rules.append(
            {
                "mount": str(item["mount"]),
                "warning": float(item.get("warning", DEFAULT_DISK[0])),
                "critical": float(item.get("critical", DEFAULT_DISK[1])),
            }
        )
    return rules


def get_plan(db: Session, agent: Agent) -> Dict[str, Any]:
    """Plan complet d'un hôte, tel que l'API et l'interface le manipulent."""
    services = (
        db.query(MonitoredService)
        .filter(MonitoredService.agent_id == agent.id)
        .order_by(MonitoredService.service_name)
        .all()
    )
    files = (
        db.query(MonitoredFile)
        .filter(MonitoredFile.agent_id == agent.id)
        .order_by(MonitoredFile.path)
        .all()
    )

    return {
        "agent_id": agent.id,
        "version": int(agent.monitoring_version or 0),
        "version_acked": int(agent.monitoring_version_acked or 0),
        # CPU et RAM sont toujours supervisés : ce sont les deux métriques par
        # défaut demandées. Seuls les seuils se règlent.
        "cpu": {
            "warning": agent.cpu_warning_threshold,
            "critical": agent.cpu_critical_threshold,
            "inherited": agent.cpu_warning_threshold is None,
        },
        "ram": {
            "warning": agent.ram_warning_threshold,
            "critical": agent.ram_critical_threshold,
            "inherited": agent.ram_warning_threshold is None,
        },
        "disk": {
            "warning": agent.disk_warning_threshold,
            "critical": agent.disk_critical_threshold,
            "inherited": agent.disk_warning_threshold is None,
            # Partitions explicitement choisies. Vide = on s'en tient à la
            # partition principale remontée par l'agent.
            "partitions": _parse_mount_rules(agent.disk_mount_rules),
        },
        "services": [
            {
                "name": s.service_name,
                "expected_state": s.expected_state.value,
                "severity": s.severity.value,
                "enabled": bool(s.enabled),
            }
            for s in services
        ],
        "files": [
            {
                "path": f.path,
                "condition": f.condition.value,
                "severity": f.severity.value,
                "max_size_mb": f.max_size_mb,
                "enabled": bool(f.enabled),
            }
            for f in files
        ],
    }


def _coerce_severity(value: Any, default: AlertSeverity = AlertSeverity.MAJOR) -> AlertSeverity:
    if isinstance(value, AlertSeverity):
        return value
    try:
        return AlertSeverity(str(value).lower())
    except ValueError:
        return default


def replace_plan(
    db: Session,
    agent: Agent,
    payload: Dict[str, Any],
    *,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Remplace le plan d'un hôte par celui fourni, et incrémente sa version.

    Remplacement et non fusion : l'appelant envoie l'état voulu. Une API
    d'ajout/retrait obligerait l'interface à tenir un journal de différences,
    et le moindre décalage laisserait un service supervisé que l'exploitant
    croit avoir retiré.
    """
    if "cpu" in payload:
        cpu = payload["cpu"] or {}
        agent.cpu_warning_threshold = cpu.get("warning")
        agent.cpu_critical_threshold = cpu.get("critical")
    if "ram" in payload:
        ram = payload["ram"] or {}
        agent.ram_warning_threshold = ram.get("warning")
        agent.ram_critical_threshold = ram.get("critical")
    if "disk" in payload:
        disk = payload["disk"] or {}
        agent.disk_warning_threshold = disk.get("warning")
        agent.disk_critical_threshold = disk.get("critical")
        partitions = disk.get("partitions")
        if partitions is not None:
            cleaned = [
                {
                    "mount": str(p["mount"]),
                    "warning": float(p.get("warning", DEFAULT_DISK[0])),
                    "critical": float(p.get("critical", DEFAULT_DISK[1])),
                }
                for p in partitions
                if isinstance(p, dict) and p.get("mount")
            ]
            agent.disk_mount_rules = json.dumps(cleaned) if cleaned else None

    if "services" in payload:
        db.query(MonitoredService).filter(MonitoredService.agent_id == agent.id).delete(
            synchronize_session=False
        )
        seen = set()
        for item in payload["services"] or []:
            name = str((item or {}).get("name") or "").strip()
            # Une liste de services vide est un cas légitime : tous les hôtes
            # n'ont pas de service applicatif à surveiller.
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                expected = ServiceState(str(item.get("expected_state", "running")).lower())
            except ValueError:
                expected = ServiceState.RUNNING
            db.add(
                MonitoredService(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    service_name=name,
                    expected_state=expected,
                    severity=_coerce_severity(item.get("severity")),
                    enabled=bool(item.get("enabled", True)),
                )
            )

    if "files" in payload:
        db.query(MonitoredFile).filter(MonitoredFile.agent_id == agent.id).delete(
            synchronize_session=False
        )
        seen_paths = set()
        for item in payload["files"] or []:
            path = str((item or {}).get("path") or "").strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                condition = FileCondition(str(item.get("condition", "must_exist")).lower())
            except ValueError:
                condition = FileCondition.MUST_EXIST
            max_size = item.get("max_size_mb")
            db.add(
                MonitoredFile(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    path=path,
                    condition=condition,
                    severity=_coerce_severity(item.get("severity")),
                    max_size_mb=int(max_size) if max_size else None,
                    enabled=bool(item.get("enabled", True)),
                )
            )

    # Nouvelle version : c'est elle qui déclenche le push vers l'agent au
    # prochain battement.
    agent.monitoring_version = int(agent.monitoring_version or 0) + 1
    db.commit()

    logger.info(
        "Plan de supervision de %s (%s) publié en version %s par %s",
        agent.id,
        agent.hostname,
        agent.monitoring_version,
        updated_by or "système",
    )
    return get_plan(db, agent)


def agent_config_payload(db: Session, agent: Agent) -> Dict[str, Any]:
    """Traduit le plan en sections de configuration comprises par l'agent.

    L'agent ne décide de rien : il observe et rapporte. Il a seulement besoin
    de savoir *quoi* regarder — l'évaluation par rapport à l'état attendu se
    fait côté plateforme, où vivent les seuils et l'historique.
    """
    services = (
        db.query(MonitoredService)
        .filter(MonitoredService.agent_id == agent.id, MonitoredService.enabled.is_(True))
        .all()
    )
    files = (
        db.query(MonitoredFile)
        .filter(MonitoredFile.agent_id == agent.id, MonitoredFile.enabled.is_(True))
        .all()
    )
    mounts = [r["mount"] for r in _parse_mount_rules(agent.disk_mount_rules)]

    return {
        "services_monitoring": {
            "enabled": bool(services),
            "services": [s.service_name for s in services],
        },
        "files_monitoring": {
            "enabled": bool(files),
            "files": [
                {"path": f.path, "max_size_mb": f.max_size_mb} for f in files
            ],
        },
        "metrics": {"disk": {"alert_mounts": mounts}},
        # Cadence de battement : l'agent la relit du plan à chaque cycle, ce
        # qui permet de la changer depuis la plateforme sans intervenir sur
        # l'hôte.
        "agent": {"heartbeat_interval_seconds": effective_heartbeat_seconds(db, agent)},
    }


def bump_version(db: Session, agent: Agent) -> int:
    """Marque le plan d'un hôte comme à republier.

    Nécessaire dès qu'un réglage porté par le plan change ailleurs que dans
    `replace_plan` — la cadence de battement, par exemple. Sans incrément, la
    plateforme considère l'hôte à jour et ne lui pousse rien : le réglage
    resterait visible à l'écran sans jamais atteindre la machine.
    """
    agent.monitoring_version = int(agent.monitoring_version or 0) + 1
    db.commit()
    return agent.monitoring_version


def pending_for_agent(db: Session, agent: Agent) -> Optional[Dict[str, Any]]:
    """Plan à pousser si l'agent n'a pas encore accusé la version courante."""
    version = int(agent.monitoring_version or 0)
    if version == 0 or int(agent.monitoring_version_acked or 0) >= version:
        return None
    return {"version": version, "payload": agent_config_payload(db, agent)}


def ack(db: Session, agent: Agent, version: int) -> None:
    if int(version) > int(agent.monitoring_version_acked or 0):
        agent.monitoring_version_acked = int(version)
        db.commit()
