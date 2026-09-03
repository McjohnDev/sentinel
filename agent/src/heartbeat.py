"""Battement et reprise de contact (point 5).

Le battement est ce qui fait qu'un hôte enrôlé cesse d'être « hors ligne » :
la plateforme dérive l'état de la fraîcheur de `last_communication`, que seul
un appel de l'agent rafraîchit.

**Sens de la liaison.** L'énoncé du point 5 parle d'« un echo ping envoyé par
la plateforme ». La plateforme ne peut pas ouvrir de connexion vers un hôte
derrière un NAT, et le code le dit (`server/src/main.py`, autour de la
construction de la réponse) : la réponse au battement est le seul canal
descendant réel. L'écho existe donc bel et bien, mais **dans la réponse** —
c'est l'agent qui frappe, la plateforme qui répond en se faisant connaître.
Tout le reste de ce module découle de ce constat.

Ce que l'écho apporte, et que l'agent ne peut pas savoir seul :

* `agent_id` — l'identifiant que la plateforme lui reconnaît réellement ;
* `clock_skew_seconds` — l'écart entre les deux horloges ;
* `previous_gap_seconds` / `resumed_after_outage` — la durée du silence qui
  vient de s'achever, donc la reprise elle-même.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from config import AgentConfig
from enrollment import AGENT_VERSION, Credentials
from facts import HostFacts
from metrics import SystemSample
from transport import build_session

logger = logging.getLogger("cbc-agent.heartbeat")

#: Au-delà, l'écart d'horloge est signalé : il fausse silencieusement les
#: fenêtres de persistance d'alerte côté plateforme.
CLOCK_SKEW_WARN_SECONDS = 120

#: Codes qui signifient « la plateforme ne te reconnaît plus ».
#: 403 et 404 en sont délibérément absents : 403 est renvoyé pour un agent
#: révoqué par un administrateur — s'en servir pour se réenrôler ferait
#: rentrer dans le parc une machine qu'on venait d'en sortir ; et 404 est ce
#: que rend une URL de base erronée, ce qui transformerait une faute de frappe
#: en boucle de réenrôlement perpétuelle.
IDENTITY_LOST_STATUSES = (401,)


class HeartbeatRefused(RuntimeError):
    """La plateforme a refusé le battement."""


class IdentityLost(HeartbeatRefused):
    """La plateforme ne reconnaît plus cet agent — réenrôlement nécessaire."""


@dataclass(frozen=True)
class Echo:
    """Ce que la plateforme renvoie d'elle-même dans la réponse."""

    agent_id: Optional[str] = None
    server_time: Optional[str] = None
    clock_skew_seconds: Optional[float] = None
    previous_gap_seconds: Optional[int] = None
    resumed_after_outage: bool = False
    config_version: Optional[int] = None

    @classmethod
    def parse(cls, raw: Any) -> "Echo":
        if not isinstance(raw, dict):
            return cls()
        skew = raw.get("clock_skew_seconds")
        # Accepte entier comme flottant : tester `isinstance(skew, int)`
        # laisserait passer un écart silencieusement si le serveur émettait
        # un flottant.
        if isinstance(skew, bool) or not isinstance(skew, (int, float)):
            skew = None
        gap = raw.get("previous_gap_seconds")
        if isinstance(gap, bool) or not isinstance(gap, (int, float)):
            gap = None
        return cls(
            agent_id=raw.get("agent_id") or None,
            server_time=raw.get("server_time") or None,
            clock_skew_seconds=float(skew) if skew is not None else None,
            previous_gap_seconds=int(gap) if gap is not None else None,
            resumed_after_outage=bool(raw.get("resumed_after_outage")),
            config_version=raw.get("config_version"),
        )


@dataclass(frozen=True)
class HeartbeatResult:
    echo: Echo
    config: Optional[Dict[str, Any]]
    tasks: list

    @property
    def offered_config_version(self) -> Optional[int]:
        """Version poussée par la plateforme, si elle en pousse une."""
        if isinstance(self.config, dict):
            version = self.config.get("version")
            if isinstance(version, int):
                return version
        return None


def build_payload(
    sample: SystemSample,
    host: HostFacts,
    *,
    taken_at: datetime,
    config_version: Optional[int] = None,
    observations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construit le corps du battement.

    `taken_at` est l'instant de la **mesure**, pas celui de l'envoi : la
    plateforme le stocke tel quel comme date de l'échantillon.

    Les faits d'hôte repartent à chaque battement, et non seulement à
    l'enrôlement : sans cela, une montée de version d'OS ou d'agent resterait
    invisible dans l'inventaire jusqu'à un réenrôlement — qui n'arrive jamais
    en fonctionnement normal.
    """
    if taken_at.tzinfo is None:
        raise ValueError("taken_at doit porter un fuseau (UTC attendu)")

    payload: Dict[str, Any] = dict(sample.as_payload())
    payload["timestamp"] = taken_at.astimezone(timezone.utc).isoformat()

    payload["hostname"] = host.hostname
    payload["os"] = host.os
    payload["os_version"] = host.os_version
    payload["agent_version"] = AGENT_VERSION
    if host.ip_address:
        payload["ip_address"] = host.ip_address
    if host.runtime:
        payload["runtime"] = host.runtime
    # Renvoyé à chaque battement comme les autres faits : un hôte que l'on
    # rebranche sur un autre port change de VLAN sans se réenrôler.
    if host.vlan_observed:
        payload["vlan_observed"] = host.vlan_observed
    if config_version is not None:
        payload["config_version"] = config_version

    # Observations du plan (point 7). Chaque liste n'est jointe que si elle
    # porte quelque chose : la plateforme n'évalue services et fichiers que
    # lorsque l'agent en rapporte, si bien qu'une liste vide éteindrait les
    # alertes en cours au lieu de ne rien dire.
    for key in ("disks", "services", "files"):
        values = (observations or {}).get(key)
        if values:
            payload[key] = values
    return payload


def _detail(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return "réponse %s" % response.status_code
    if isinstance(detail, list) and detail:
        first = detail[0]
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return "champ refusé « %s » : %s" % (field, first.get("msg", "invalide"))
    return str(detail) if detail else "réponse %s" % response.status_code


def send(
    config: AgentConfig,
    credentials: Credentials,
    payload: Dict[str, Any],
    *,
    session: Optional[requests.Session] = None,
) -> HeartbeatResult:
    """Envoie un battement et interprète la réponse."""
    http = session or build_session(config)

    try:
        response = http.post(
            config.api_url("agents/heartbeat"),
            json=payload,
            headers={"Authorization": credentials.auth_key},
            timeout=config.timeout_seconds,
            verify=config.tls_verify,
        )
    except requests.exceptions.RequestException as exc:
        raise HeartbeatRefused("Plateforme injoignable : %s" % exc)

    if response.status_code in IDENTITY_LOST_STATUSES:
        raise IdentityLost(
            "La plateforme ne reconnaît plus cet agent (%s) — réenrôlement "
            "nécessaire." % _detail(response)
        )
    if response.status_code >= 400:
        raise HeartbeatRefused("Battement refusé — %s" % _detail(response))

    try:
        body = response.json()
    except ValueError:
        raise HeartbeatRefused("Réponse de battement illisible.")
    if not isinstance(body, dict):
        raise HeartbeatRefused("Réponse de battement inattendue.")

    config_block = body.get("config")
    tasks = body.get("tasks")
    return HeartbeatResult(
        echo=Echo.parse(body.get("echo")),
        config=config_block if isinstance(config_block, dict) else None,
        tasks=tasks if isinstance(tasks, list) else [],
    )


def interpret(result: HeartbeatResult, credentials: Credentials) -> Credentials:
    """Tire les conséquences de l'écho, et rend l'identité à retenir.

    Trois choses que seule la plateforme sait, et qu'il serait fautif
    d'ignorer :

    * une divergence d'identifiant — l'agent adopte celui de la plateforme,
      sinon tout ce qu'il enverra ensuite désignera une ligne qui n'existe
      plus ;
    * un écart d'horloge important — il décale les fenêtres d'alerte sans
      qu'aucune erreur ne se produise ;
    * une reprise après silence — un rattrapage muet ressemble à un
      fonctionnement normal dans les journaux.
    """
    echo = result.echo

    if echo.resumed_after_outage:
        logger.warning(
            "Reprise de contact après %s s de silence.",
            echo.previous_gap_seconds if echo.previous_gap_seconds is not None else "?",
        )

    if echo.clock_skew_seconds is not None and abs(echo.clock_skew_seconds) >= CLOCK_SKEW_WARN_SECONDS:
        logger.warning(
            "Horloge décalée de %.0f s par rapport à la plateforme — les "
            "fenêtres d'alerte en dépendent.",
            echo.clock_skew_seconds,
        )

    if echo.agent_id and echo.agent_id != credentials.agent_id:
        logger.warning(
            "Identifiant divergent : la plateforme connaît cet hôte sous %s, "
            "l'agent se croyait %s. Adoption de %s.",
            echo.agent_id,
            credentials.agent_id,
            echo.agent_id,
        )
        return Credentials(agent_id=echo.agent_id, auth_key=credentials.auth_key)

    return credentials
