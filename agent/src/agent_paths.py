"""Emplacements des fichiers d'état locaux de l'agent.

Une seule définition, partagée. Le chemin de l'identifiant machine était
calculé à deux endroits — dans `agent.py` en honorant la variable
`AGENT_MACHINE_ID_FILE`, et dans la désinstallation en la codant en dur à
côté du paquet. Les deux divergeaient exactement là où il ne fallait pas :
sous Docker, l'identifiant vit dans un volume désigné par la variable, si
bien que la désinstallation laissait le vrai fichier en place et effaçait à
la place un fichier sans rapport dans le répertoire d'installation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: Variable d'environnement qui déplace l'identifiant machine — utilisée par
#: l'image Docker pour le ranger dans un volume persistant.
MACHINE_ID_ENV = "AGENT_MACHINE_ID_FILE"


def machine_id_path() -> Path:
    """Fichier contenant l'identifiant machine persistant."""
    override = os.environ.get(MACHINE_ID_ENV)
    if override:
        return Path(override)
    # Par défaut : à la racine du paquet agent, à côté de config.yaml.
    return Path(__file__).resolve().parent.parent / ".machine_id"


def resolve_buffer_dir(buffer_dir: str, config_path: Optional[str] = None) -> Path:
    r"""Ancre un `buffer_dir` relatif sur un point fixe, jamais sur le CWD.

    `degraded_mode.buffer_dir` vaut « data/agent-buffer » par défaut, et
    Python résout un chemin relatif depuis le **répertoire courant**. Pour un
    service Windows, ce répertoire est `C:\Windows\System32` : le tampon
    d'envoi et `session.json` — qui contient la clé d'authentification en
    clair — y auraient atterri. Le même agent lancé à la main depuis un autre
    dossier aurait repris une file d'attente vide et se serait cru
    non enrôlé.

    Ancre retenue : le répertoire du fichier de configuration. C'est le point
    de référence qu'un administrateur a en tête quand il écrit un chemin
    relatif dans ce fichier. À défaut, la racine du paquet agent.
    """
    path = Path(buffer_dir)
    if path.is_absolute():
        return path
    anchor = Path(config_path).resolve().parent if config_path else Path(__file__).resolve().parent.parent
    return anchor / path
