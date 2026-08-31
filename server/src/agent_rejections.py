"""Journal des agents refusés faute d'identité connue.

Motivation : un agent bien vivant peut voir sa clé d'authentification cesser
d'être reconnue (ligne purgée, base restaurée, ré-installation partielle). Il
émet alors dans le vide. Jusqu'ici la plateforme se contentait de répondre 401
sans rien conserver : l'hôte disparaissait de l'inventaire et **aucun écran ne
montrait qu'une machine frappait à la porte**. Le diagnostic reposait sur la
lecture manuelle des journaux du conteneur.

Ce registre garde en mémoire les frappes récentes, par adresse source, pour
que l'exploitation les voie et déclenche un ré-enrôlement.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

#: Nombre de sources distinctes mémorisées (au-delà, la plus ancienne sort).
MAX_TRACKED_SOURCES = 200

#: Une source inactive plus longtemps que cela sort du registre : l'agent a
#: été ré-enrôlé ou désinstallé, la faire figurer indéfiniment serait un faux
#: positif permanent.
FORGET_AFTER = timedelta(hours=24)


class RejectionLedger:
    """Compteur borné, sûr en contexte multi-thread (uvicorn + ordonnanceur)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def record(self, source: str, *, path: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        key = source or "unknown"
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = {
                    "source": key,
                    "first_seen": now,
                    "attempts": 0,
                    "paths": set(),
                }
                self._entries[key] = entry
            entry["last_seen"] = now
            entry["attempts"] += 1
            entry["paths"].add(path)
            self._entries.move_to_end(key)
            while len(self._entries) > MAX_TRACKED_SOURCES:
                self._entries.popitem(last=False)

    def _prune(self, now: datetime) -> None:
        stale = [k for k, e in self._entries.items() if now - e["last_seen"] > FORGET_AFTER]
        for key in stale:
            self._entries.pop(key, None)

    def snapshot(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Frappes récentes, de la plus récente à la plus ancienne."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            self._prune(now)
            rows = [
                {
                    "source": e["source"],
                    "attempts": e["attempts"],
                    "paths": sorted(e["paths"]),
                    "first_seen": e["first_seen"].isoformat(),
                    "last_seen": e["last_seen"].isoformat(),
                    "silent_for_seconds": int((now - e["last_seen"]).total_seconds()),
                }
                for e in self._entries.values()
            ]
        return sorted(rows, key=lambda r: r["last_seen"], reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def summary(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Résumé pour la santé plateforme : y a-t-il des agents à ré-enrôler ?"""
        rows = self.snapshot(now=now)
        return {
            "sources": len(rows),
            "attempts": sum(r["attempts"] for r in rows),
            "most_recent": rows[0] if rows else None,
        }


ledger = RejectionLedger()
