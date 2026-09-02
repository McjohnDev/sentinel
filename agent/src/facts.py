"""Ce que l'agent constate de son hôte.

Ces champs sont *constatés*, pas *attribués* : la plateforme les enregistre et
refuse qu'on les corrige depuis l'interface (point 2). Un inventaire qui
contredit la machine réelle ne vaut rien, donc tout ce qui est ici vient du
système et de rien d'autre.

Aucune collecte de métrique ici : la mesure du CPU, de la mémoire et des
disques appartient au point 7. On ne relève que les caractéristiques stables
nécessaires à l'enrôlement.
"""

from __future__ import annotations

import os
import platform
import re
import socket
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:  # psutil est une dépendance déclarée, mais l'agent doit rester diagnosticable sans elle.
    import psutil
except ImportError:  # pragma: no cover - chemin de repli
    psutil = None

#: La plateforme valide `^[a-zA-Z0-9\-_\.]+$` sur le nom de machine.
_HOSTNAME_ALLOWED = re.compile(r"[^A-Za-z0-9\-_.]")

_BYTES_PER_GB = 1024 ** 3


def sanitize_hostname(raw: str) -> str:
    """Ramène un nom de machine à ce que la plateforme accepte.

    Un poste nommé « PC-Comptabilité » serait refusé en 422 à l'enrôlement, ce
    qui est un échec incompréhensible pour celui qui installe l'agent. On
    remplace le caractère fautif au lieu de laisser l'enrôlement échouer.
    """
    cleaned = _HOSTNAME_ALLOWED.sub("-", (raw or "").strip())
    cleaned = cleaned.strip("-.") or "hote-inconnu"
    return cleaned[:255]


def detect_os() -> str:
    """Famille de système, dans le vocabulaire de la plateforme."""
    system = platform.system()
    return system or "Inconnu"


def detect_os_version() -> str:
    """Version lisible du système."""
    system = platform.system()
    if system == "Windows":
        version = platform.version()
        release = platform.release()
        detail = ("%s %s" % (release, version)).strip()
    elif system == "Darwin":
        detail = platform.mac_ver()[0] or platform.release()
    else:
        detail = platform.release()
    return (detail or "inconnue")[:50]


def detect_ip_address() -> Optional[str]:
    """Adresse IP par laquelle l'hôte sort vers le réseau.

    On n'ouvre pas de connexion : un socket UDP « connecté » ne fait que
    choisir une route, ce qui suffit à connaître l'interface sortante sans
    dépendre d'un DNS ni joindre quoi que ce soit.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 1))  # TEST-NET-1, jamais routé
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return None
    finally:
        sock.close()


#: Interface porteuse d'une étiquette 802.1Q : `eth0.100`, `bond0.20`.
_TAGGED_INTERFACE = re.compile(r"^(?P<link>[^.]+)\.(?P<vlan>\d{1,4})$")

#: Table des VLAN du noyau Linux, quand le module 8021q est chargé.
_PROC_VLAN = "/proc/net/vlan/config"


def detect_vlan() -> Optional[str]:
    """VLAN que l'hôte *étiquette lui-même*, s'il en étiquette un.

    Attention à ce que cette valeur signifie. Une machine branchée sur un port
    d'accès ne voit pas son VLAN : le commutateur pose et retire l'étiquette
    de façon transparente, et l'hôte n'a aucun moyen de la connaître. `None`
    veut donc dire « non déterminable depuis l'hôte », pas « aucun VLAN » —
    ce sera le cas de la plupart des postes.

    Seul un hôte sur port trunk, portant des sous-interfaces étiquetées, peut
    répondre. C'est pourquoi le VLAN *déclaré* par l'exploitation reste un
    champ distinct : lui existe pour tous les hôtes.
    """
    found = _vlan_from_proc() or _vlan_from_interface_names()
    return found


def _vlan_from_proc() -> Optional[str]:
    """Lit la table 802.1Q du noyau — la source la plus sûre sous Linux."""
    try:
        with open(_PROC_VLAN, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return None

    ids = []
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        if not parts[1].isdigit():
            continue  # en-tête du fichier
        ids.append(parts[1])
    return _single(ids)


def _vlan_from_interface_names() -> Optional[str]:
    """Repli : déduit le VLAN du nom des interfaces (`eth0.100`)."""
    if psutil is None:
        return None
    try:
        names = list(psutil.net_if_addrs().keys())
    except Exception:
        return None

    ids = []
    for name in names:
        match = _TAGGED_INTERFACE.match(name)
        if match:
            ids.append(match.group("vlan"))
    return _single(ids)


#: Longueur de la colonne côté plateforme.
_VLAN_FIELD_MAX = 64


def _single(ids) -> Optional[str]:
    """Rend le VLAN observé, ou None si l'hôte n'étiquette rien.

    Un hôte trunk peut porter plusieurs VLAN. En désigner un seul serait
    arbitraire et faux dans l'inventaire ; on les rend tous, séparés par des
    virgules, pour que l'exploitant voie la réalité.

    La troncature se fait **par élément entier**, jamais au caractère. Couper
    la chaîne à 64 caractères transformait `115` en `11` : un VLAN qui existe,
    qui n'est pas le bon, et que rien ne signale comme tronqué. Mieux vaut
    déclarer moins de VLAN que d'en inventer un faux.
    """
    unique = sorted({i for i in ids if i.isdigit() and 0 < int(i) < 4095}, key=int)
    if not unique:
        return None

    kept: List[str] = []
    length = 0
    for value in unique:
        addition = len(value) + (1 if kept else 0)
        if length + addition > _VLAN_FIELD_MAX:
            break
        kept.append(value)
        length += addition
    return ",".join(kept) if kept else None


@dataclass(frozen=True)
class HostFacts:
    hostname: str
    os: str
    os_version: str
    ip_address: Optional[str]
    cpu_cores: Optional[int]
    ram_total_gb: Optional[float]
    disk_total_gb: Optional[float]
    runtime: Dict[str, Any] = field(default_factory=dict)
    vlan_observed: Optional[str] = None


def _hardware() -> Dict[str, Optional[float]]:
    """Caractéristiques matérielles, ou None si psutil est absent.

    None signifie « non mesuré ». Renvoyer 0 laisserait croire à une machine
    sans processeur ni mémoire, ce qui est pire qu'une case vide.
    """
    if psutil is None:
        return {"cpu_cores": None, "ram_total_gb": None, "disk_total_gb": None}

    cores = psutil.cpu_count(logical=True)
    try:
        ram = round(psutil.virtual_memory().total / _BYTES_PER_GB, 2)
    except Exception:
        ram = None

    total = 0
    for part in psutil.disk_partitions(all=False):
        try:
            total += psutil.disk_usage(part.mountpoint).total
        except (PermissionError, OSError):
            # Lecteur amovible vide ou volume chiffré non monté : il ne compte
            # pas, et ce n'est pas une raison d'échouer l'enrôlement.
            continue
    return {
        "cpu_cores": cores,
        "ram_total_gb": ram,
        "disk_total_gb": round(total / _BYTES_PER_GB, 2) if total else None,
    }


def _is_elevated() -> Optional[bool]:
    """L'agent tourne-t-il avec des droits d'administration ?

    Détermine ce qu'il pourra lire : sans élévation, certains services et
    fichiers protégés remontent « inconnu » plutôt que leur état réel, et
    l'exploitant doit pouvoir faire le lien plutôt que de croire à une panne.
    """
    if os.name == "nt":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return None
    try:
        return os.geteuid() == 0
    except AttributeError:
        return None


def _run_mode() -> str:
    """Service installé, ou lancement à la main.

    Le gestionnaire de services renseigne la variable ; à défaut, l'absence de
    terminal attaché en tient lieu. La distinction compte pour l'exploitant :
    un agent lancé à la main disparaît à la fermeture de la session, ce qui
    explique un hôte qui « retombe hors ligne tous les soirs ».
    """
    declared = (os.environ.get("CBC_AGENT_RUN_MODE") or "").strip().lower()
    if declared in ("service", "console"):
        return declared
    try:
        return "console" if sys.stdin is not None and sys.stdin.isatty() else "service"
    except Exception:
        return "unknown"


def runtime_info(agent_version: str, config: Any = None) -> Dict[str, Any]:
    """Où et comment l'agent s'exécute sur l'hôte (point 10).

    Les noms de champs suivent ce que la fiche d'hôte affiche : un relevé qui
    ne porte pas les mêmes clés que le panneau produit un écran vide sans
    qu'aucune erreur ne se produise nulle part.
    """
    from pathlib import Path

    frozen = bool(getattr(sys, "frozen", False))
    executable = sys.executable
    install_dir = (
        str(Path(executable).parent) if frozen else str(Path(__file__).resolve().parent)
    )

    info: Dict[str, Any] = {
        "run_mode": _run_mode(),
        "run_as_user": _current_user(),
        "elevated": _is_elevated(),
        "executable_path": executable,
        "install_dir": install_dir,
        "packaging": "pyinstaller" if frozen else "source",
        "platform": "%s %s" % (platform.system(), platform.release()),
        "python_version": platform.python_version(),
        "pid": os.getpid(),
        "uptime_seconds": _process_uptime(),
        "agent_version": agent_version,
    }

    if config is not None:
        # Ce que l'agent croit joindre. Un hôte qui bat vers la mauvaise
        # plateforme se diagnostique ici et nulle part ailleurs.
        info["server_url"] = getattr(config, "server_url", None)
        info["tls_verify"] = getattr(config, "tls_verify", None)
        info["config_path"] = getattr(config, "source_path", None)

    if info["run_mode"] == "service":
        info["service_name"] = os.environ.get("CBC_AGENT_SERVICE_NAME") or "cbc-agent"

    return info


def _process_uptime() -> Optional[int]:
    """Depuis combien de temps ce processus tourne."""
    if psutil is None:
        return None
    try:
        import time

        return max(0, int(time.time() - psutil.Process(os.getpid()).create_time()))
    except Exception:
        return None


def _current_user() -> Optional[str]:
    import getpass

    try:
        return getpass.getuser()
    except Exception:
        return None


def collect(agent_version: str, config: Any = None) -> HostFacts:
    """Relève l'état complet de l'hôte, matériel compris."""
    hardware = _hardware()
    return HostFacts(
        hostname=sanitize_hostname(socket.gethostname()),
        os=detect_os(),
        os_version=detect_os_version(),
        ip_address=detect_ip_address(),
        cpu_cores=hardware["cpu_cores"],
        ram_total_gb=hardware["ram_total_gb"],
        disk_total_gb=hardware["disk_total_gb"],
        runtime=runtime_info(agent_version, config),
        vlan_observed=detect_vlan(),
    )


def refreshed(previous: HostFacts, agent_version: str, config: Any = None) -> HostFacts:
    """Rafraîchit ce qui bouge, en gardant le matériel déjà relevé.

    Un agent installé en service tourne des mois sans redémarrer. Relever les
    faits une seule fois au lancement fige l'inventaire à cet instant : un
    poste en DHCP change d'adresse et la plateforme continue d'afficher
    l'ancienne, une montée de version d'OS reste invisible. Les faits
    doivent donc être repris à chaque battement, pas seulement embarqués dans
    chaque battement.

    Le matériel, lui, est repris tel quel : l'énumération des partitions
    interroge chaque volume monté, et un partage réseau injoignable y bloque.
    Le faire à chaque battement mettrait la liaison à la merci d'un montage
    figé — précisément ce que la supervision doit signaler, pas subir.
    """
    return HostFacts(
        hostname=sanitize_hostname(socket.gethostname()),
        os=detect_os(),
        os_version=detect_os_version(),
        ip_address=detect_ip_address(),
        cpu_cores=previous.cpu_cores,
        ram_total_gb=previous.ram_total_gb,
        disk_total_gb=previous.disk_total_gb,
        runtime=runtime_info(agent_version, config),
        vlan_observed=detect_vlan(),
    )
