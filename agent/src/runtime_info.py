"""Comment et où l'agent s'exécute sur l'hôte (point 9 / AGT-012).

L'agent ne disait rien de lui-même : ni chemin d'installation, ni compte
d'exécution, ni PID, ni nom de service, ni mode de démarrage. Quand un hôte
n'émettait plus, l'exploitation n'avait aucun moyen — depuis la plateforme —
de savoir si l'agent était installé en service, lancé à la main dans une
console, ou tournait sous un compte sans les droits nécessaires. Il fallait
ouvrir une session sur la machine pour répondre à ces questions.

Ce module produit un descriptif que l'agent joint à son enrôlement et à
chaque heartbeat. Tout est en lecture seule et sans privilège particulier :
une introspection qui exigerait des droits qu'on n'a pas serait inutile
précisément dans le cas où l'on en a besoin.
"""

from __future__ import annotations

import getpass
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover — psutil est une dépendance ferme
    psutil = None  # type: ignore[assignment]


# --------------------------------------------------------------- packaging


def is_frozen() -> bool:
    """Exécution depuis un binaire PyInstaller plutôt que depuis les sources ?"""
    return bool(getattr(sys, "frozen", False))


def _running_in_docker() -> bool:
    """Détection de conteneur, par faisceau d'indices plutôt qu'un seul test.

    `/.dockerenv` disparaît selon les runtimes, et `/proc/1/cgroup` ne dit
    plus rien d'utile sous cgroup v2. On teste donc les deux, sans se fier à
    l'un ou à l'autre.
    """
    if Path("/.dockerenv").exists():
        return True
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
        if "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup:
            return True
    except OSError:
        pass
    return False


def packaging_channel() -> str:
    """Par quel canal cet agent a-t-il été posé sur l'hôte ?"""
    if _running_in_docker():
        return "docker"
    if is_frozen():
        return "binary"
    return "source"


# ------------------------------------------------------------- mode d'exécution


def _has_tty() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, AttributeError):
        # stdin fermé (cas d'un service) : pas de terminal.
        return False


def _windows_service_name() -> Optional[str]:
    """Nom du service Windows sous lequel ce processus tourne, si applicable."""
    if sys.platform != "win32" or psutil is None:
        return None
    try:
        me = psutil.Process()
        # Un service lancé par le SCM descend de services.exe.
        parent = me.parent()
        for _ in range(4):
            if parent is None:
                return None
            if (parent.name() or "").lower() == "services.exe":
                return os.environ.get("CBC_AGENT_SERVICE_NAME", "CBCAgent")
            parent = parent.parent()
    except Exception:
        return None
    return None


def _systemd_unit() -> Optional[str]:
    """Unité systemd propriétaire du processus, lue dans son cgroup."""
    if not sys.platform.startswith("linux"):
        return None
    if os.environ.get("INVOCATION_ID"):
        # Posé par systemd sur les processus qu'il lance.
        return os.environ.get("CBC_AGENT_SERVICE_NAME", "cbc-agent.service")
    try:
        cgroup = Path(f"/proc/{os.getpid()}/cgroup").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in cgroup.splitlines():
        if ".service" in line:
            return line.rsplit("/", 1)[-1].strip() or None
    return None


def detect_run_mode() -> Dict[str, Optional[str]]:
    """Mode de démarrage et nom du service, quand il y en a un.

    Renvoie `{"run_mode": ..., "service_name": ...}` avec `run_mode` parmi
    `docker | service | systemd | launchd | console | unknown`.
    """
    if _running_in_docker():
        return {"run_mode": "docker", "service_name": None}

    if sys.platform == "win32":
        service = _windows_service_name()
        if service:
            return {"run_mode": "service", "service_name": service}
    elif sys.platform == "darwin":
        # launchd exporte cette variable aux démons qu'il gère.
        if os.environ.get("XPC_SERVICE_NAME", "").startswith("com.cbc"):
            return {"run_mode": "launchd", "service_name": os.environ["XPC_SERVICE_NAME"]}
    else:
        unit = _systemd_unit()
        if unit:
            return {"run_mode": "systemd", "service_name": unit}

    if _has_tty():
        return {"run_mode": "console", "service_name": None}
    return {"run_mode": "unknown", "service_name": None}


# ------------------------------------------------------------------- compte


def _is_elevated() -> Optional[bool]:
    """Le processus dispose-t-il des privilèges d'administration ?

    None quand la question n'a pas de réponse fiable, plutôt que False : un
    « non » inventé serait plus trompeur qu'une absence de réponse.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            return None
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        return None


def _current_user() -> Optional[str]:
    try:
        return getpass.getuser()
    except Exception:
        # getuser() lève si aucune des variables d'environnement usuelles
        # n'est posée et que le compte n'est pas dans la base passwd — cas
        # courant dans un conteneur « distroless ».
        return os.environ.get("USERNAME") or os.environ.get("USER")


# ------------------------------------------------------------------ process


def _process_started_at() -> Optional[str]:
    if psutil is None:
        return None
    try:
        created = psutil.Process().create_time()
        return datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _process_uptime_seconds() -> Optional[int]:
    """Durée de vie du *processus agent*.

    À ne pas confondre avec `uptime_seconds` du heartbeat, qui est le temps
    depuis le démarrage de l'hôte. Un agent qui redémarre en boucle sur une
    machine allumée depuis des semaines est exactement le cas que cette
    distinction permet de voir.
    """
    if psutil is None:
        return None
    try:
        return max(0, int(time.time() - psutil.Process().create_time()))
    except Exception:
        return None


# -------------------------------------------------------------------- public


def collect_runtime_info(
    *,
    config_path: Optional[str] = None,
    server_url: Optional[str] = None,
    tls_verify: Optional[bool] = None,
    agent_version: Optional[str] = None,
    buffer_records: Optional[int] = None,
    last_error: Optional[str] = None,
    plugins: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Descriptif complet de l'exécution de l'agent sur son hôte.

    Les paramètres sont fournis par l'agent parce qu'ils relèvent de son état
    courant (configuration réellement chargée, profondeur du tampon, dernière
    erreur) et non de l'introspection système.
    """
    mode = detect_run_mode()
    executable = sys.executable or ""
    install_dir = (
        str(Path(executable).parent)
        if is_frozen() and executable
        else str(Path(__file__).resolve().parent.parent)
    )

    return {
        # Où
        "executable_path": executable,
        "install_dir": install_dir,
        "working_dir": os.getcwd(),
        # Le fichier réellement chargé — pas celui que la doc suppose. C'est
        # la réponse à « pourquoi ma configuration n'est-elle pas prise ? ».
        "config_path": config_path,
        # Comment
        "run_mode": mode["run_mode"],
        "service_name": mode["service_name"],
        "packaging": packaging_channel(),
        "pid": os.getpid(),
        "started_at": _process_started_at(),
        "uptime_seconds": _process_uptime_seconds(),
        # Sous quel compte
        "run_as_user": _current_user(),
        "elevated": _is_elevated(),
        # Avec quoi
        "python_version": platform.python_version(),
        "frozen": is_frozen(),
        "agent_version": agent_version,
        "platform": platform.platform(),
        # État de liaison
        "server_url": server_url,
        "tls_verify": tls_verify,
        "buffer_records": buffer_records,
        "last_error": last_error,
        "plugins": plugins or [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
