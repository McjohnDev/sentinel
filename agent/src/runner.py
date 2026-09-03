"""Boucle de battement et reprise après indisponibilité (point 5).

La boucle n'est pas un `sleep(intervalle)` : elle avance sur une échéance
calculée à partir d'une horloge **monotone**. Dormir la durée de l'intervalle
laisse dériver la cadence du temps de traitement, et surtout un changement
d'heure système — passage à l'heure d'hiver, correction NTP — peut faire
dormir la boucle une heure de plus, pendant laquelle l'hôte est déclaré hors
ligne sans qu'aucune panne ne se soit produite.

Reprise : après un échec, l'intervalle croît (5 s, 10 s, 20 s… plafonné),
pour ne pas marteler une plateforme déjà en difficulté — un parc entier qui
réessaie à la seconde après une coupure suffit à empêcher son redémarrage. Au
premier succès, la cadence nominale reprend immédiatement.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

import collectors as collectors_module
import inventory as inventory_module
import heartbeat as heartbeat_module
import plan as plan_module
import session as session_module
from config import AgentConfig
from enrollment import AGENT_VERSION, Credentials, write_credentials
from facts import HostFacts
from facts import refreshed as refresh_facts
from metrics import MetricsUnavailable, SystemSample
from metrics import collect as collect_metrics

from transport import build_session

logger = logging.getLogger("cbc-agent.runner")

#: Attente initiale après un échec, en secondes.
BACKOFF_START = 5.0

#: Plafond de l'attente. Au-delà, l'hôte resterait silencieux si longtemps
#: que sa reprise passerait inaperçue.
BACKOFF_MAX = 300.0

#: Battements entre deux inventaires. Le relevé interroge la base de registre
#: ou le gestionnaire de paquets : le faire à chaque battement coûterait bien
#: plus que ce qu'il apprend, un parc logiciel ne bougeant qu'à l'occasion
#: d'une installation.
INVENTORY_EVERY_BEATS = 240


@dataclass
class RunnerOutcome:
    """Ce que la boucle a fait — utile aux tests et à un arrêt propre."""

    beats_sent: int = 0
    failures: int = 0
    resumed: int = 0
    inventories_sent: int = 0
    plan_version: Optional[int] = None
    last_error: Optional[str] = None
    credentials: Optional[Credentials] = None


def _next_backoff(current: float) -> float:
    return min(BACKOFF_MAX, current * 2)


def run(
    config: AgentConfig,
    credentials: Credentials,
    host: HostFacts,
    *,
    interval_seconds: float = 30.0,
    max_beats: Optional[int] = None,
    session: Optional[requests.Session] = None,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    sampler: Callable[[], SystemSample] = collect_metrics,
    host_provider: Optional[Callable[[HostFacts], HostFacts]] = None,
    observer: Callable[[Optional[dict]], dict] = collectors_module.observe,
    inventory_every: int = INVENTORY_EVERY_BEATS,
    config_version: Optional[int] = None,
) -> RunnerOutcome:
    """Bat jusqu'à `max_beats` battements (ou indéfiniment si None).

    `sleeper`, `clock`, `sampler` et `host_provider` sont injectables : la
    reprise après indisponibilité doit pouvoir être éprouvée sans attendre
    réellement, et sans dépendre de la machine qui exécute les tests.
    """
    provider = host_provider or (lambda previous: refresh_facts(previous, AGENT_VERSION, config))
    http = session or build_session(config)
    outcome = RunnerOutcome(credentials=credentials)
    backoff = BACKOFF_START
    beats = 0

    while max_beats is None or beats < max_beats:
        beats += 1
        taken_at = clock()

        # Les faits volatils sont repris à chaque battement : sans cela un
        # poste en DHCP garderait à jamais l'adresse qu'il avait au démarrage
        # de l'agent.
        try:
            host = provider(host)
        except Exception:  # noqa: BLE001 - un relevé raté ne doit pas rompre la liaison
            logger.debug("Relevé d'hôte impossible ; on conserve le précédent.", exc_info=True)

        try:
            sample = sampler()
        except MetricsUnavailable as exc:
            # Sans mesure il n'y a pas de battement possible : réessayer ne
            # changera rien tant que l'hôte est dans cet état.
            outcome.last_error = str(exc)
            session_module.record_failure(
                server_url=config.server_url,
                agent_id=credentials.agent_id,
                error=str(exc),
            )
            logger.error("%s", exc)
            return outcome

        # Version *appliquée*, relue du disque : annoncer celle qu'on vient de
        # recevoir ferait croire à la plateforme qu'un plan est en vigueur
        # alors qu'un arrêt au mauvais moment l'aurait perdu.
        announced = config_version if config_version is not None else plan_module.current_version()

        # Ce que le plan désigne est relevé à chaque battement. Un relevé qui
        # échoue ne doit pas rompre la liaison : mieux vaut un battement sans
        # observation qu'un hôte qui cesse de donner signe de vie.
        try:
            stored_plan = plan_module.read_plan()
            observations = observer(stored_plan.payload if stored_plan else None)
        except Exception:  # noqa: BLE001
            logger.warning("Relevé du plan impossible ; battement sans observation.", exc_info=True)
            observations = None

        payload = heartbeat_module.build_payload(
            sample, host, taken_at=taken_at, config_version=announced,
            observations=observations,
        )

        try:
            result = heartbeat_module.send(config, credentials, payload, session=http)
        except heartbeat_module.IdentityLost as exc:
            # On s'arrête au lieu de se réenrôler tout seul : un réenrôlement
            # automatique consomme un jeton et, si la plateforme a révoqué cet
            # hôte, le ferait rentrer par la fenêtre.
            outcome.failures += 1
            outcome.last_error = str(exc)
            session_module.record_failure(
                server_url=config.server_url,
                agent_id=credentials.agent_id,
                error=str(exc),
            )
            logger.error("%s", exc)
            return outcome
        except heartbeat_module.HeartbeatRefused as exc:
            outcome.failures += 1
            outcome.last_error = str(exc)
            state = session_module.record_failure(
                server_url=config.server_url,
                agent_id=credentials.agent_id,
                error=str(exc),
            )
            logger.warning(
                "Battement %s échoué (%s tentative(s) de suite) : %s",
                beats,
                state.consecutive_failures,
                exc,
            )
            if max_beats is None or beats < max_beats:
                sleeper(backoff)
            backoff = _next_backoff(backoff)
            continue

        adopted = heartbeat_module.interpret(result, credentials)
        if adopted != credentials:
            credentials = adopted
            write_credentials(credentials)
            outcome.credentials = credentials

        # Le plan voyage dans la réponse au battement : c'est le seul canal
        # descendant. Le laisser passer entretiendrait une republication
        # perpétuelle, la plateforme le considérant jamais appliqué.
        if result.config is not None:
            applied = plan_module.apply_offered(config, credentials, result.config, session=http)
            if applied is not None:
                outcome.plan_version = applied

        if result.echo.resumed_after_outage:
            outcome.resumed += 1

        outcome.beats_sent += 1

        # Inventaire : premier battement réussi, puis à cadence lente. Le
        # faire au premier permet à l'exploitant de choisir un service dans
        # la liste réelle de l'hôte sans attendre des heures.
        if inventory_every and (outcome.beats_sent - 1) % inventory_every == 0:
            _push_inventory(config, credentials, http, outcome)
        session_module.record_success(
            server_url=config.server_url,
            agent_id=credentials.agent_id,
            at=taken_at,
        )

        # Cadence nominale rétablie dès le premier succès : rester en attente
        # longue après une reprise laisserait l'hôte au bord du seuil de
        # bascule hors ligne.
        backoff = BACKOFF_START

        # La cadence peut avoir été changée depuis la plateforme : elle voyage
        # dans le plan, et l'agent la relit à chaque cycle plutôt qu'au seul
        # démarrage. Sans cela, un réglage ne prendrait effet qu'au prochain
        # redémarrage de l'agent — c'est-à-dire jamais, sur un service.
        interval_seconds = _planned_interval(interval_seconds)

        if max_beats is None or beats < max_beats:
            sleeper(interval_seconds)

    return outcome


#: Bornes appliquées à la cadence reçue. La plateforme la borne déjà ; on ne
#: lui fait pas aveuglément confiance, un plan corrompu ou d'une version
#: antérieure ne devant pas rendre l'agent muet ou frénétique.
MIN_INTERVAL = 5.0
MAX_INTERVAL = 3600.0


def _planned_interval(current: float) -> float:
    """Cadence demandée par le plan, ou celle en cours si rien n'est demandé."""
    try:
        stored = plan_module.read_plan()
        if stored is None:
            return current
        section = (stored.payload or {}).get("agent")
        if not isinstance(section, dict):
            return current
        wanted = section.get("heartbeat_interval_seconds")
        if wanted is None:
            return current
        value = float(wanted)
    except (TypeError, ValueError, AttributeError):
        return current

    bounded = max(MIN_INTERVAL, min(value, MAX_INTERVAL))
    if bounded != current:
        logger.info("Cadence de battement portée à %.0f s par la plateforme.", bounded)
    return bounded


def _push_inventory(config, credentials, http, outcome: RunnerOutcome) -> None:
    """Relève et transmet l'inventaire, sans jamais rompre le battement.

    Un inventaire manqué n'est pas un incident : il repartira au prochain
    tour. Faire échouer le cycle pour autant retirerait l'hôte du parc pour
    une donnée d'appoint.
    """
    try:
        report = inventory_module.collect()
    except Exception:  # noqa: BLE001
        logger.warning("Relevé d'inventaire impossible.", exc_info=True)
        return

    try:
        inventory_module.push(config, credentials, report, session=http)
    except inventory_module.InventoryPushFailed as exc:
        logger.warning("%s", exc)
        return

    outcome.inventories_sent += 1
    if report.unavailable:
        logger.info("Inventaire partiel — sections indisponibles : %s", ", ".join(report.unavailable))
