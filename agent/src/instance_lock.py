"""Single-instance lock (AGT-001c)."""

from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional


class InstanceLockError(RuntimeError):
    pass


class InstanceLock:
    """PID file lock — refuse start if another agent instance is running."""

    #: Répertoire du verrou. `tempfile.gettempdir()` renvoie un dossier
    #: **propre à l'utilisateur** sous Windows : deux comptes pourraient donc
    #: chacun croire détenir un verrou « unique » sur la même machine. Pour
    #: une garantie à l'échelle de l'hôte, pointer cette variable vers un
    #: répertoire commun (`C:\ProgramData\CBC Agent`, `/var/run`).
    #: Sert aussi à isoler les tests du verrou réellement en service.
    LOCK_DIR_ENV = "CBC_AGENT_LOCK_DIR"

    def __init__(self, name: str = "cbc-agent", directory: Optional[str] = None) -> None:
        self.name = name
        base = directory or os.environ.get(self.LOCK_DIR_ENV) or tempfile.gettempdir()
        self._path = Path(base) / f"{name}.pid"
        self._fh: Optional[object] = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> None:
        if self._path.exists():
            try:
                old_pid = int(self._path.read_text(encoding="utf-8").strip())
            except ValueError:
                old_pid = -1
            # In Docker the agent is PID 1. A crash leaves the lock file behind;
            # the next start is also PID 1, so "pid exists" would false-positive.
            if old_pid > 0 and old_pid != os.getpid() and _pid_exists(old_pid):
                raise InstanceLockError(
                    f"Another agent instance is already running (pid={old_pid}, lock={self._path}). "
                    "Only one agent per host is allowed (AGT-000 / AGT-001c)."
                )
            # Stale lock
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass

        self._path.write_text(str(os.getpid()), encoding="utf-8")
        atexit.register(self.release)

    def release(self) -> None:
        try:
            if self._path.exists():
                content = self._path.read_text(encoding="utf-8").strip()
                if content == str(os.getpid()):
                    self._path.unlink(missing_ok=True)
        except OSError:
            pass


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True
