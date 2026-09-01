"""Mesures système minimales exigées par le battement.

Ce module ne couvre **que** les champs obligatoires de `HeartbeatRequest` :
processeur, mémoire, disque, temps de fonctionnement. La supervision
paramétrable par hôte — partitions choisies, services, fichiers — appartient
aux points 6 et 7 et n'est pas ici.

Ce n'est pas un choix de confort : le battement ne peut pas partir sans ces
valeurs, la plateforme les valide et rejette le message en 422 sans elles. Le
point 5 hérite donc du strict nécessaire, pas de la collecte complète.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - dépendance déclarée
    psutil = None

_BYTES_PER_GB = 1024 ** 3


class MetricsUnavailable(RuntimeError):
    """Impossible de mesurer l'hôte — le battement ne peut pas être construit."""


def _clamp_percent(value: float) -> float:
    """Ramène un pourcentage dans [0, 100].

    psutil peut rendre brièvement plus de 100 % (somme par cœur, compteurs
    qui débordent). La plateforme valide `0 <= v <= 100` et répond 422 : sans
    ce garde-fou, un pic de mesure fait rejeter le battement, l'hôte cesse de
    donner signe de vie et bascule « hors ligne » pour une raison purement
    arithmétique.
    """
    if value != value:  # NaN
        return 0.0
    return float(min(100.0, max(0.0, value)))


def _gb(value: Optional[float]) -> float:
    return round((value or 0) / _BYTES_PER_GB, 2)


@dataclass(frozen=True)
class SystemSample:
    cpu_percent: float
    cpu_cores: int
    ram_percent: float
    ram_total_gb: float
    ram_used_gb: float
    ram_free_gb: float
    disk_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    uptime_seconds: int

    def as_payload(self) -> dict:
        return asdict(self)


def _root_mount() -> str:
    import os

    return "C:\\" if os.name == "nt" else "/"


#: Durée de la toute première mesure processeur, en secondes.
#:
#: `psutil.cpu_percent(interval=None)` compare deux relevés successifs des
#: compteurs du noyau. Au premier appel il n'existe pas de relevé précédent :
#: psutil compare alors au démarrage du processus et rend une valeur
#: arbitraire — mesuré ici à **100 %**. Ce premier battement partait donc avec
#: un pic de charge inventé, capable de déclencher une alerte processeur
#: critique à chaque démarrage d'agent. La première mesure est donc bloquante
#: et réelle ; les suivantes sont instantanées.
FIRST_SAMPLE_SECONDS = 1.0

_cpu_primed = False


def _cpu_percent() -> float:
    global _cpu_primed
    if not _cpu_primed:
        value = psutil.cpu_percent(interval=FIRST_SAMPLE_SECONDS)
        _cpu_primed = True
        return value or 0.0
    return psutil.cpu_percent(interval=None) or 0.0


def collect(cpu_interval: float = 0.0) -> SystemSample:
    """Relève un échantillon système.

    Hors première mesure, le relevé processeur est instantané : il porte sur
    l'intervalle écoulé depuis l'appel précédent. La boucle obtient ainsi une
    moyenne sur sa propre cadence, sans immobiliser le fil d'exécution une
    seconde à chaque battement.
    """
    if psutil is None:
        raise MetricsUnavailable(
            "psutil est absent : impossible de mesurer l'hôte. Installer "
            "agent/requirements.txt."
        )

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(_root_mount())

    # `cpu_count` peut rendre None sur des plateformes exotiques ; la
    # plateforme exige >= 1 et refuserait le battement.
    cores = psutil.cpu_count(logical=True) or 1

    try:
        uptime = int(time.time() - psutil.boot_time())
    except Exception:
        uptime = 0

    return SystemSample(
        cpu_percent=_clamp_percent(
            psutil.cpu_percent(interval=cpu_interval) if cpu_interval else _cpu_percent()
        ),
        cpu_cores=max(1, int(cores)),
        ram_percent=_clamp_percent(memory.percent),
        ram_total_gb=_gb(memory.total),
        ram_used_gb=_gb(memory.total - memory.available),
        ram_free_gb=_gb(memory.available),
        disk_percent=_clamp_percent(disk.percent),
        disk_total_gb=_gb(disk.total),
        disk_used_gb=_gb(disk.used),
        disk_free_gb=_gb(disk.free),
        # La plateforme refuse un temps de fonctionnement négatif ; une
        # horloge reculée pendant la mesure en produirait un.
        uptime_seconds=max(0, uptime),
    )
