"""Plan de supervision reçu de la plateforme (point 6).

La plateforme décide *quoi* surveiller sur chaque hôte — seuils processeur et
mémoire, partitions retenues, services attendus, fichiers dont la présence ou
l'absence doit alerter. Elle ne peut pas ouvrir de connexion vers un hôte
derrière un NAT : le plan voyage donc dans la **réponse au battement**, comme
l'écho.

Deux obligations en découlent, et rien ne fonctionne si l'une manque :

* **Conserver le plan sur l'hôte.** Il doit survivre à un redémarrage de
  l'agent et à une coupure de la plateforme — c'est précisément quand la
  liaison est rompue qu'il faut continuer à surveiller ce qui a été demandé.
* **Accuser réception.** Tant que l'accusé ne remonte pas, la plateforme
  considère la version comme non appliquée et la repousse **à chaque
  battement**, indéfiniment. Un agent qui lit le plan sans l'acquitter
  fonctionne en apparence tout en entretenant une republication perpétuelle.

Ce module s'arrête là où commence le point 7 : il reçoit, range et acquitte.
Ce que l'agent *mesure* à partir du plan viendra avec la collecte.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from agent_paths import state_dir
from config import AgentConfig
from enrollment import Credentials

from transport import build_session

logger = logging.getLogger("cbc-agent.plan")


def plan_file() -> Path:
    return state_dir() / "monitoring-plan.json"


@dataclass(frozen=True)
class StoredPlan:
    version: int
    payload: Dict[str, Any]


def read_plan(path: Optional[Path] = None) -> Optional[StoredPlan]:
    """Relit le plan appliqué, s'il en existe un de lisible."""
    target = path or plan_file()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    version = raw.get("version")
    payload = raw.get("payload")
    if not isinstance(version, int) or not isinstance(payload, dict):
        return None
    return StoredPlan(version=version, payload=payload)


def current_version(path: Optional[Path] = None) -> Optional[int]:
    """Version appliquée, à renvoyer dans chaque battement.

    C'est la version **appliquée**, jamais celle qui vient d'être reçue :
    annoncer une version qu'on n'a pas encore rangée ferait croire à la
    plateforme que le plan est en vigueur alors qu'un arrêt au mauvais moment
    l'aurait perdu.
    """
    stored = read_plan(path)
    return stored.version if stored else None


def write_plan(version: int, payload: Dict[str, Any], path: Optional[Path] = None) -> StoredPlan:
    """Range le plan de façon atomique.

    Écriture dans un fichier temporaire, synchronisation, puis remplacement :
    une coupure d'alimentation en pleine écriture doit laisser l'ancien plan
    intact plutôt qu'un fichier tronqué. Un plan illisible vaut un hôte qui ne
    surveille plus ce qu'on lui a demandé.
    """
    target = path or plan_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"version": version, "payload": payload}, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return StoredPlan(version=version, payload=payload)


class AckFailed(RuntimeError):
    """L'accusé de réception n'a pas pu être transmis."""


def acknowledge(
    config: AgentConfig,
    credentials: Credentials,
    version: int,
    *,
    session: Optional[requests.Session] = None,
) -> None:
    """Signale à la plateforme que cette version est appliquée."""
    http = session or build_session(config)
    try:
        response = http.post(
            config.api_url("agents/config/ack"),
            json={"version": version},
            headers={"Authorization": credentials.auth_key},
            timeout=config.timeout_seconds,
            verify=config.tls_verify,
        )
    except requests.exceptions.RequestException as exc:
        raise AckFailed("Accusé de réception non transmis : %s" % exc)

    if response.status_code >= 400:
        raise AckFailed("Accusé de réception refusé (%s)." % response.status_code)


def apply_offered(
    config: AgentConfig,
    credentials: Credentials,
    offered: Optional[Dict[str, Any]],
    *,
    session: Optional[requests.Session] = None,
    path: Optional[Path] = None,
) -> Optional[int]:
    """Range puis acquitte un plan proposé. Rend la version appliquée.

    Ordre imposé : **écrire d'abord, acquitter ensuite**. Acquitter une
    version qu'on n'a pas rangée la ferait disparaître — la plateforme
    cesserait de la pousser alors que l'hôte ne l'a jamais reçue, et
    l'écart ne se découvrirait qu'au prochain incident.
    """
    if not isinstance(offered, dict):
        return None
    version = offered.get("version")
    payload = offered.get("payload")
    if not isinstance(version, int) or not isinstance(payload, dict):
        logger.warning("Plan reçu dans une forme inattendue — ignoré.")
        return None

    applied = current_version(path)
    if applied is not None and version <= applied:
        # Déjà en vigueur. La plateforme peut republier si un accusé s'est
        # perdu : on ré-acquitte sans réécrire.
        _try_ack(config, credentials, version, session)
        return applied

    write_plan(version, payload, path)
    logger.info("Plan de supervision v%s appliqué.", version)
    _try_ack(config, credentials, version, session)
    return version


def _try_ack(config, credentials, version, session) -> None:
    """Acquitte sans faire échouer le battement.

    Un accusé perdu n'est pas grave en soi : la plateforme repoussera la même
    version au battement suivant. Faire échouer le cycle pour autant
    priverait l'hôte de sa présence — un défaut bien plus lourd.
    """
    try:
        acknowledge(config, credentials, version, session=session)
    except AckFailed as exc:
        logger.warning("%s Le plan sera republié au prochain battement.", exc)
