"""Ce que l'agent observe d'après le plan reçu (point 7).

L'agent ne décide de rien. Il regarde ce que le plan lui désigne — partitions
retenues, services attendus, fichiers surveillés — et rapporte ce qu'il
constate. L'évaluation par rapport à l'état attendu se fait côté plateforme,
où vivent les seuils, l'historique et la notion d'alerte.

Une règle traverse tout le module : **« je n'ai pas pu savoir » n'est pas
« non »**. Un fichier sur un partage injoignable, un service que le gestionnaire
refuse d'interroger faute de droits — ces cas remontent `None` ou `unknown`,
jamais `False` ou `stopped`. Confondre les deux lèverait une fausse alerte
« fichier manquant », et surtout **éteindrait** à tort une alerte « fichier
interdit » ou « service arrêté ». Le silence de l'agent doit rester lisible
comme un silence.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover - dépendance déclarée
    psutil = None

logger = logging.getLogger("cbc-agent.collectors")

#: Délai maximum accordé à une commande système d'interrogation.
COMMAND_TIMEOUT = 10

#: États normalisés attendus par la plateforme.
RUNNING = "running"
STOPPED = "stopped"
UNKNOWN = "unknown"


# ----------------------------------------------------------------- disques


def disks(mounts: Iterable[str]) -> List[Dict[str, Any]]:
    """Occupation des partitions désignées par le plan.

    Seules les partitions retenues sont mesurées : interroger tous les volumes
    montés ferait dépendre le battement d'un partage réseau figé, alors que la
    supervision doit signaler ce genre de blocage, pas le subir.
    """
    if psutil is None:
        return []

    reported: List[Dict[str, Any]] = []
    for mount in mounts or []:
        if not mount:
            continue
        try:
            usage = psutil.disk_usage(mount)
        except (OSError, PermissionError) as exc:
            # Point de montage disparu ou inaccessible : on le dit, plutôt que
            # de l'omettre — une partition qui cesse d'être mesurée doit se
            # voir, sinon son alerte s'éteint sans que personne ne l'ait décidé.
            logger.warning("Partition %s illisible : %s", mount, exc)
            reported.append({"mount": mount, "percent": None, "error": "unreadable"})
            continue
        reported.append(
            {
                "mount": mount,
                "percent": round(usage.percent, 1),
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
            }
        )
    return reported


# ---------------------------------------------------------------- services


def _run(command: List[str]) -> Optional[str]:
    """Exécute une commande d'interrogation, sans jamais laisser filer l'agent."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Commande %s indisponible : %s", command[0], exc)
        return None
    return (result.stdout or "") + (result.stderr or "")


def _windows_service_status(name: str) -> str:
    if psutil is None or not hasattr(psutil, "win_service_get"):
        return UNKNOWN
    try:
        service = psutil.win_service_get(name)
        status = (service.status() or "").lower()
    except Exception:
        # Service absent, ou droits insuffisants pour l'interroger. Les deux
        # se disent « je ne sais pas » : déclarer « arrêté » un service qu'on
        # n'a pas pu lire déclencherait une alerte sur une ignorance.
        return UNKNOWN
    if status in ("running", "start_pending", "continue_pending"):
        return RUNNING
    if status in ("stopped", "stop_pending", "paused", "pause_pending"):
        return STOPPED
    return UNKNOWN


def _systemd_service_status(name: str) -> str:
    output = _run(["systemctl", "is-active", name])
    if output is None:
        return UNKNOWN
    state = output.strip().splitlines()[0].strip() if output.strip() else ""
    if state == "active":
        return RUNNING
    if state in ("inactive", "failed", "deactivating"):
        return STOPPED
    # « unknown », « not-found » : le service n'existe pas sous ce nom. C'est
    # une information pour l'exploitant, pas un arrêt.
    return UNKNOWN


def _launchd_service_status(name: str) -> str:
    output = _run(["launchctl", "list"])
    if output is None:
        return UNKNOWN
    for line in output.splitlines():
        if line.strip().endswith(name) or ("\t%s" % name) in line:
            first = line.split("\t")[0].strip()
            return STOPPED if first == "-" else RUNNING
    return UNKNOWN


def service_status(name: str) -> str:
    """État normalisé d'un service, ou `unknown` si indéterminable."""
    if not name:
        return UNKNOWN
    if sys.platform == "win32":
        return _windows_service_status(name)
    if sys.platform == "darwin":
        return _launchd_service_status(name)
    return _systemd_service_status(name)


def services(names: Iterable[str]) -> List[Dict[str, Any]]:
    """État des services désignés par le plan."""
    return [{"name": name, "status": service_status(name)} for name in names or [] if name]


# --------------------------------------------------------------- fichiers


def file_state(path: str) -> Dict[str, Any]:
    """Présence et caractéristiques d'un fichier.

    `exists` vaut `None` quand la question n'a pas pu être tranchée — droits
    refusés, partage réseau injoignable. La plateforme distingue ce cas de
    l'absence, et c'est la distinction qui compte : traiter l'indécidable
    comme une absence éteindrait une alerte « fichier interdit » au moment où
    l'on perd justement la capacité de vérifier.
    """
    record: Dict[str, Any] = {"path": path, "exists": None, "size_bytes": None, "last_modified": None}
    try:
        stat = os.stat(path)
    except FileNotFoundError:
        record["exists"] = False
        return record
    except NotADirectoryError:
        # Un composant du chemin n'est pas un répertoire : le fichier ne peut
        # pas exister sous cette forme.
        record["exists"] = False
        return record
    except (PermissionError, OSError) as exc:
        logger.warning("Fichier %s : état indéterminable (%s)", path, exc)
        return record

    record["exists"] = True
    record["size_bytes"] = stat.st_size
    record["last_modified"] = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return record


def files(specs: Iterable[Any]) -> List[Dict[str, Any]]:
    """État des fichiers désignés par le plan.

    Le plan les décrit soit par une chaîne, soit par un objet portant `path` :
    les deux formes sont acceptées, l'agent n'ayant pas à imposer la sienne à
    la plateforme.
    """
    observed: List[Dict[str, Any]] = []
    for spec in specs or []:
        path = spec.get("path") if isinstance(spec, dict) else spec
        if not path:
            continue
        observed.append(file_state(str(path)))
    return observed


# ------------------------------------------------------- lecture du plan


def _section(plan: Optional[Dict[str, Any]], *keys: str) -> Any:
    node: Any = plan or {}
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _as_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _enabled_items(section: Any, key: str) -> List[Any]:
    """Éléments d'une section, si elle est exploitable et active."""
    if not isinstance(section, dict):
        return []
    if section.get("enabled", True) is False:
        return []
    return _as_list(section.get(key))


def observe(plan_payload: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Relève tout ce que le plan désigne, en une passe.

    Sans plan, les listes sont vides — et la plateforme sait interpréter
    l'absence : elle n'évalue services et fichiers que lorsque l'agent en
    rapporte, ce qui évite qu'un agent muet éteigne les alertes existantes.
    """
    # Chaque section est validée avant lecture. Un plan d'une version
    # antérieure ou déformé ne doit pas faire échouer le battement : l'hôte
    # cesserait de donner signe de vie à cause d'un défaut de configuration,
    # ce qui est bien pire que de ne rien observer.
    mounts = _as_list(_section(plan_payload, "metrics", "disk", "alert_mounts"))

    service_section = _section(plan_payload, "services_monitoring")
    service_names = _enabled_items(service_section, "services")

    file_section = _section(plan_payload, "files_monitoring")
    file_specs = _enabled_items(file_section, "files")

    return {
        "disks": disks(mounts),
        "services": services(service_names),
        "files": files(file_specs),
    }
