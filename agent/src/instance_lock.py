"""Un seul agent à la fois sur un hôte.

Deux `run` simultanés — un service installé plus un lancement à la main pour
diagnostiquer, le cas le plus courant — ne se contentent pas de doubler les
battements. Ils écrivent tous deux les mêmes fichiers d'état : identité
adoptée, plan de supervision, état de liaison. Le dernier qui écrit gagne, et
l'agent peut ainsi acquitter une version de plan que l'autre n'a pas rangée.

Le verrou porte le PID du détenteur, ce qui permet de nommer le processus
fautif au lieu d'annoncer un conflit sans coupable. Un verrou laissé par un
processus mort — arrêt brutal, coupure — est repris plutôt que de bloquer
l'agent définitivement : refuser de démarrer après un plantage serait pire que
le risque qu'on cherche à écarter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from agent_paths import state_dir


class AlreadyRunning(RuntimeError):
    """Un autre agent détient déjà le verrou."""


def lock_file() -> Path:
    return state_dir() / "agent.lock"


def _process_alive(pid: int) -> bool:
    """Ce PID correspond-il à un processus vivant ?

    En cas de doute — droits insuffisants pour interroger le processus — on
    répond « vivant ». Se tromper dans ce sens fait échouer un démarrage avec
    un message clair ; se tromper dans l'autre laisse deux agents tourner.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def read_holder(path: Optional[Path] = None) -> Optional[int]:
    """PID inscrit dans le verrou, s'il est lisible."""
    target = path or lock_file()
    try:
        raw = target.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class InstanceLock:
    """Verrou d'instance, utilisable comme gestionnaire de contexte."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or lock_file()
        self.acquired = False

    def acquire(self) -> "InstanceLock":
        holder = read_holder(self.path)
        if holder is not None and holder != os.getpid() and _process_alive(holder):
            raise AlreadyRunning(
                "Un agent tourne déjà sur cet hôte (PID %d). Arrêter le "
                "service avant de relancer, ou consulter « status »." % holder
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Un verrou périmé est repris : le processus qui l'a posé n'existe
        # plus, le bloquer indéfiniment interdirait tout redémarrage après un
        # arrêt brutal.
        self.path.write_text("%d\n" % os.getpid(), encoding="utf-8")
        self.acquired = True
        return self

    def release(self) -> None:
        if not self.acquired:
            return
        # On n'efface que son propre verrou : entre-temps, un autre agent a pu
        # légitimement reprendre la place.
        if read_holder(self.path) == os.getpid():
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False

    def __enter__(self) -> "InstanceLock":
        return self.acquire()

    def __exit__(self, *_exc) -> None:
        self.release()
