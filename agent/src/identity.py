"""Identité stable de la machine.

La plateforme reconnaît un hôte par son `machine_id`, pas par son nom : un
poste renommé reste le même poste, et deux postes clonés portant le même nom
doivent rester deux lignes distinctes dans l'inventaire.

Cet identifiant est donc tiré une fois puis relu à chaque démarrage. Le perdre
n'est pas neutre : au réenrôlement la plateforme créerait un second hôte pour
la même machine, et l'historique se scinderait en deux.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from agent_paths import machine_id_file

#: La plateforme valide `^[a-zA-Z0-9\-_]+$` sur ce champ (EnrollRequest).
#: Un UUID v4 canonique y satisfait ; on vérifie plutôt que de le supposer.
MACHINE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{8,255}$")


def is_valid_machine_id(value: Optional[str]) -> bool:
    """La valeur est-elle acceptable par la plateforme ?"""
    return bool(value) and bool(MACHINE_ID_PATTERN.match(value))


def read_machine_id(path: Optional[Path] = None) -> Optional[str]:
    """Relit l'identité posée par une exécution précédente, si elle est saine.

    Un fichier illisible ou corrompu est traité comme absent : l'appelant
    décidera d'en tirer un nouveau, ce qui est préférable à propager une
    identité invalide que la plateforme rejettera à l'enrôlement.
    """
    target = path or machine_id_file()
    try:
        value = target.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return value if is_valid_machine_id(value) else None


def load_or_create_machine_id(path: Optional[Path] = None) -> str:
    """Retourne l'identité de la machine, en la créant au premier appel."""
    target = path or machine_id_file()
    existing = read_machine_id(target)
    if existing:
        return existing

    created = str(uuid.uuid4())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(created + "\n", encoding="utf-8")
    return created
