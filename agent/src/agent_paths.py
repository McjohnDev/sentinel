"""Où l'agent range son état sur l'hôte.

L'agent doit se souvenir de deux choses entre deux démarrages : l'identité de
la machine et les jetons obtenus à l'enrôlement. Les écrire à côté du binaire
ne tient pas : un agent installé en service tourne avec un répertoire courant
imposé par le gestionnaire de services, et le dossier d'installation est
souvent en lecture seule pour le compte de service.

L'emplacement suit donc la convention du système, avec une dérogation
explicite par variable d'environnement pour les tests et les conteneurs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Dérogation explicite. Le conteneur agent monte un volume ici, et les tests
#: l'utilisent pour ne jamais toucher l'état de la machine qui les exécute.
STATE_DIR_ENV = "CBC_AGENT_STATE_DIR"


def state_dir() -> Path:
    """Répertoire d'état, créé si absent."""
    override = os.environ.get(STATE_DIR_ENV)
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        base = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:/ProgramData"
        path = Path(base) / "CBC Agent"
    elif sys.platform == "darwin":
        path = Path("/usr/local/var/lib/cbc-agent")
    else:
        path = Path("/var/lib/cbc-agent")

    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Un agent lancé par un exploitant sans droits d'administration doit
        # pouvoir au moins s'enrôler pour un essai : on se replie sur le
        # profil utilisateur plutôt que d'échouer au démarrage.
        path = Path.home() / ".cbc-agent"
        path.mkdir(parents=True, exist_ok=True)
    return path


def machine_id_file() -> Path:
    """Fichier portant l'identité stable de la machine."""
    return state_dir() / "machine_id"


def credentials_file() -> Path:
    """Fichier portant l'identifiant d'agent et la clé d'authentification."""
    return state_dir() / "credentials.json"
