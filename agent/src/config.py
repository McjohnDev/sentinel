"""Lecture de la configuration de l'agent.

Le fichier livré avec le binaire ne porte volontairement pas de jeton : il est
embarqué tel quel dans le paquet distribué, un secret y serait diffusé avec
chaque installation. Le jeton arrive donc par argument de ligne de commande ou
par variable d'environnement au moment de l'enrôlement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

#: Jeton d'enrôlement passé par l'environnement (installation silencieuse).
ENROLLMENT_TOKEN_ENV = "CBC_ENROLLMENT_TOKEN"

#: URL de plateforme passée par l'environnement.
SERVER_URL_ENV = "CBC_SERVER_URL"

VALID_MACHINE_TYPES = ("server", "workstation")


class ConfigError(ValueError):
    """Configuration inutilisable — message destiné à l'exploitant."""


@dataclass(frozen=True)
class AgentConfig:
    server_url: str
    enrollment_token: str
    tls_verify: bool
    machine_type: str
    timeout_seconds: float

    def api_url(self, path: str) -> str:
        """URL absolue d'une route de la plateforme."""
        return self.server_url.rstrip("/") + "/api/" + path.lstrip("/")

    @property
    def enroll_url(self) -> str:
        return self.api_url("agents/enroll")

    @property
    def deregister_url(self) -> str:
        return self.api_url("agents/deregister")


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_config(
    path: Optional[Path] = None,
    *,
    token_override: Optional[str] = None,
    url_override: Optional[str] = None,
) -> AgentConfig:
    """Construit la configuration effective.

    Priorité : argument de ligne de commande, puis environnement, puis
    fichier. L'exploitant qui passe `--token` sur une installation doit
    l'emporter sur ce que contient le fichier livré.
    """
    raw: Dict[str, Any] = {}
    if path is not None:
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ConfigError("Fichier de configuration introuvable : %s" % path)
        except yaml.YAMLError as exc:
            raise ConfigError("Configuration illisible (%s) : %s" % (path, exc))
        raw = loaded or {}

    server = raw.get("server") or {}
    agent = raw.get("agent") or {}

    server_url = (
        url_override
        or os.environ.get(SERVER_URL_ENV)
        or server.get("url")
        or ""
    ).strip()
    if not server_url:
        raise ConfigError(
            "Aucune URL de plateforme : renseigner server.url, %s ou --server-url."
            % SERVER_URL_ENV
        )
    if not server_url.startswith(("http://", "https://")):
        raise ConfigError("URL de plateforme invalide : %s" % server_url)

    token = (
        token_override
        or os.environ.get(ENROLLMENT_TOKEN_ENV)
        or server.get("enrollment_token")
        or ""
    ).strip()

    tls_verify = _as_bool(server.get("tls_verify"), True)
    if server_url.startswith("http://") and tls_verify:
        # Pas une erreur : le laboratoire sert du HTTP en clair. On ne prétend
        # simplement pas vérifier un certificat qui n'existe pas.
        tls_verify = False

    machine_type = str(agent.get("machine_type") or "workstation").strip().lower()
    if machine_type not in VALID_MACHINE_TYPES:
        raise ConfigError(
            "agent.machine_type doit valoir %s (reçu : %s)"
            % (" ou ".join(VALID_MACHINE_TYPES), machine_type)
        )

    try:
        timeout = float(agent.get("timeout_seconds") or 15)
    except (TypeError, ValueError):
        raise ConfigError("agent.timeout_seconds doit être un nombre.")

    return AgentConfig(
        server_url=server_url,
        enrollment_token=token,
        tls_verify=tls_verify,
        machine_type=machine_type,
        timeout_seconds=timeout,
    )
