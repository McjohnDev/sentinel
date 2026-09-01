"""Enrôlement de l'agent auprès de la plateforme (point 1).

Séquence : l'agent constate son hôte, présente un jeton à usage unique, et
reçoit en retour l'identifiant court attribué par la plateforme (6 caractères
hexadécimaux) et une clé d'authentification. Les deux sont conservés sur
l'hôte ; tout ce qui suit — heartbeat, configuration, métriques — s'appuie
dessus.

L'enrôlement est délibérément **non répétable par accident** : relancer la
commande sur un hôte déjà enrôlé ne consomme pas un second jeton et ne crée
pas un doublon dans l'inventaire. Il faut le demander explicitement.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from agent_paths import credentials_file
from config import AgentConfig
from facts import HostFacts

AGENT_VERSION = "2.0.0-dev"


class EnrollmentError(RuntimeError):
    """Échec d'enrôlement — le message est destiné à l'exploitant."""


@dataclass(frozen=True)
class Credentials:
    agent_id: str
    auth_key: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def read_credentials(path: Optional[Path] = None) -> Optional[Credentials]:
    """Relit les jetons obtenus lors d'un enrôlement précédent."""
    target = path or credentials_file()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    agent_id = str(raw.get("agent_id") or "").strip()
    auth_key = str(raw.get("auth_key") or "").strip()
    if not agent_id or not auth_key:
        return None
    return Credentials(agent_id=agent_id, auth_key=auth_key)


def write_credentials(creds: Credentials, path: Optional[Path] = None) -> Path:
    """Écrit les jetons, en restreignant l'accès quand le système le permet."""
    target = path or credentials_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(creds.to_json() + "\n", encoding="utf-8")
    try:
        target.chmod(0o600)
    except (OSError, NotImplementedError):
        # Windows n'applique pas ces bits ; la protection y vient des ACL du
        # répertoire ProgramData. Ne pas transformer cela en échec.
        pass
    return target


def is_enrolled(path: Optional[Path] = None) -> bool:
    return read_credentials(path) is not None


def clear_credentials(path: Optional[Path] = None) -> None:
    """Oublie les jetons, sans toucher à l'identité de la machine.

    `machine_id` est délibérément conservé : la plateforme reconnaît un hôte
    par cette identité, et une réinstallation ultérieure doit retomber sur la
    **même** ligne d'inventaire — avec son historique et sa marque de
    désinstallation levée. L'effacer produirait un second hôte pour la même
    machine, ce que le point 4 cherche précisément à éviter.
    """
    target = path or credentials_file()
    try:
        target.unlink()
    except FileNotFoundError:
        pass


class DeregistrationError(RuntimeError):
    """Le désenrôlement n'a pas pu être signalé à la plateforme."""


def deregister(
    config: AgentConfig,
    credentials: Credentials,
    *,
    reason: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> str:
    """Signale la désinstallation à la plateforme (point 4).

    L'hôte n'est pas effacé côté plateforme : il est *marqué* désinstallé et
    garde son historique. Ce signalement est ce qui distingue un retrait
    volontaire d'une panne — sans lui, la machine resterait « hors ligne »
    dans le parc et déclencherait des alertes pour une absence voulue.
    """
    http = session or requests.Session()
    body = {"reason": reason} if reason else {}

    try:
        response = http.post(
            config.deregister_url,
            json=body,
            headers={"Authorization": credentials.auth_key},
            timeout=config.timeout_seconds,
            verify=config.tls_verify,
        )
    except requests.exceptions.RequestException as exc:
        raise DeregistrationError(
            "Plateforme injoignable sur %s : %s" % (config.deregister_url, exc)
        )

    if response.status_code >= 400:
        raise DeregistrationError("Désenrôlement refusé — %s" % _explain(response))

    return credentials.agent_id


def build_payload(config: AgentConfig, machine_id: str, host: HostFacts) -> Dict[str, Any]:
    """Construit le corps attendu par `POST /api/agents/enroll`."""
    payload: Dict[str, Any] = {
        "token": config.enrollment_token,
        "machine_id": machine_id,
        "hostname": host.hostname,
        "os": host.os,
        "agent_version": AGENT_VERSION,
        "machine_type": config.machine_type,
    }
    # Champs optionnels : la plateforme accepte leur absence, mais pas une
    # valeur nulle sur les chaînes contraintes.
    if host.ip_address:
        payload["ip_address"] = host.ip_address
    if host.os_version:
        payload["os_version"] = host.os_version
    if host.cpu_cores is not None:
        payload["cpu_cores"] = host.cpu_cores
    if host.ram_total_gb is not None:
        payload["ram_total_gb"] = host.ram_total_gb
    if host.disk_total_gb is not None:
        payload["disk_total_gb"] = host.disk_total_gb
    if host.runtime:
        payload["runtime"] = host.runtime
    if host.vlan_observed:
        payload["vlan_observed"] = host.vlan_observed
    return payload


def _explain(response: requests.Response) -> str:
    """Traduit un refus de la plateforme en phrase actionnable."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list) and detail:
        # Erreur de validation Pydantic : nommer le champ fautif, sinon
        # l'exploitant ne peut rien faire du message.
        first = detail[0]
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return "champ refusé « %s » : %s" % (field, first.get("msg", "invalide"))
    if detail:
        return str(detail)
    return "réponse %s de la plateforme" % response.status_code


def enroll(
    config: AgentConfig,
    machine_id: str,
    host: HostFacts,
    *,
    session: Optional[requests.Session] = None,
    credentials_path: Optional[Path] = None,
) -> Credentials:
    """Enrôle l'hôte et conserve les jetons obtenus."""
    if not config.enrollment_token:
        raise EnrollmentError(
            "Aucun jeton d'enrôlement. Le fournir par --token, la variable "
            "CBC_ENROLLMENT_TOKEN, ou server.enrollment_token."
        )

    http = session or requests.Session()
    payload = build_payload(config, machine_id, host)

    try:
        response = http.post(
            config.enroll_url,
            json=payload,
            timeout=config.timeout_seconds,
            verify=config.tls_verify,
        )
    except requests.exceptions.SSLError as exc:
        raise EnrollmentError(
            "Certificat de la plateforme refusé (%s). Vérifier l'autorité de "
            "certification installée sur cet hôte." % exc
        )
    except requests.exceptions.RequestException as exc:
        raise EnrollmentError("Plateforme injoignable sur %s : %s" % (config.enroll_url, exc))

    if response.status_code >= 400:
        raise EnrollmentError("Enrôlement refusé — %s" % _explain(response))

    try:
        body = response.json()
        creds = Credentials(agent_id=body["agent_id"], auth_key=body["auth_key"])
    except (ValueError, KeyError) as exc:
        raise EnrollmentError("Réponse d'enrôlement inexploitable : %s" % exc)

    write_credentials(creds, credentials_path)
    return creds
