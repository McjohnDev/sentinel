"""Identifiant d'agent attribué par la plateforme.

Format retenu : **6 caractères hexadécimaux majuscules** (`A3F09C`).

L'identifiant précédent était un UUID v4 de 36 caractères — exact, mais
illisible : impossible à dicter au téléphone à un exploitant, impossible à
retenir, et il saturait chaque colonne de l'interface. Un code court est
manipulable par un humain, ce qui est le point de vue qui compte pour un
inventaire de parc.

La contrepartie assumée : 16 777 216 combinaisons seulement. C'est très
largement suffisant pour un parc bancaire, mais assez peu pour que la
collision doive être **gérée** et non pas supposée impossible — d'où la
vérification d'unicité en base à chaque génération.
"""

from __future__ import annotations

import re
import secrets
from typing import Optional

from sqlalchemy.orm import Session

#: Longueur du code, en caractères hexadécimaux.
AGENT_ID_LENGTH = 6

#: Forme acceptée sur les routes et à la génération. Majuscules uniquement :
#: une seule casse évite deux identifiants distincts à l'œil identiques.
AGENT_ID_PATTERN = re.compile(r"^[0-9A-F]{%d}$" % AGENT_ID_LENGTH)

#: Nombre de tirages avant d'abandonner. Avec un parc de quelques milliers
#: d'hôtes, la probabilité d'échouer 12 fois de suite est négligeable ; si
#: cela arrive, c'est que la base est saturée et le silence serait pire.
MAX_GENERATION_ATTEMPTS = 12


class AgentIdExhaustedError(RuntimeError):
    """Aucun identifiant libre trouvé — l'espace d'adressage est saturé."""


def is_valid_agent_id(value: Optional[str]) -> bool:
    """Le code est-il bien formé ? N'interroge pas la base."""
    return bool(value) and bool(AGENT_ID_PATTERN.match(value))


def normalize_agent_id(value: Optional[str]) -> Optional[str]:
    """Met en forme un code saisi par un humain (casse, espaces).

    Un exploitant qui recopie « a3f09c » depuis un ticket doit tomber sur le
    bon hôte.
    """
    if not value:
        return None
    candidate = value.strip().upper()
    return candidate if is_valid_agent_id(candidate) else None


def _draw() -> str:
    """Un tirage aléatoire cryptographique, sans biais de format."""
    return secrets.token_hex(AGENT_ID_LENGTH // 2).upper()


def generate_agent_id(db: Session) -> str:
    """Attribue un code libre, en vérifiant réellement l'unicité en base.

    On ne se repose pas sur la seule contrainte de clé primaire : une
    collision remonterait alors en 500 pendant un enrôlement, au pire moment
    (installation d'un poste). Ici elle coûte un tirage supplémentaire.
    """
    from src.models import Agent  # import différé : évite un cycle de modules

    for _ in range(MAX_GENERATION_ATTEMPTS):
        candidate = _draw()
        exists = db.query(Agent.id).filter(Agent.id == candidate).first()
        if exists is None:
            return candidate

    raise AgentIdExhaustedError(
        f"Aucun identifiant d'agent libre après {MAX_GENERATION_ATTEMPTS} tirages "
        f"sur {AGENT_ID_LENGTH} caractères hexadécimaux."
    )
