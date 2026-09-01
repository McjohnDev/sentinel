"""État de la liaison, tel que l'hôte le voit.

Quand le parc affiche « hors ligne » et que l'exploitant est devant la
machine, il faut pouvoir trancher sans interroger la plateforme — c'est
justement elle qui est en cause. Ce fichier est la version de l'hôte : depuis
quand la liaison est rompue, sur quelle erreur, et combien de tentatives ont
échoué.

Il est écrit de façon atomique (fichier temporaire puis remplacement) pour
qu'une coupure d'alimentation en pleine écriture ne laisse pas un fichier
tronqué à la place d'un état lisible.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_paths import state_dir


def session_file() -> Path:
    return state_dir() / "session.json"


@dataclass(frozen=True)
class LinkState:
    connected: bool = False
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    server_url: Optional[str] = None
    agent_id: Optional[str] = None


def read_state(path: Optional[Path] = None) -> LinkState:
    target = path or session_file()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LinkState()
    if not isinstance(raw, dict):
        return LinkState()
    return LinkState(
        connected=bool(raw.get("connected")),
        last_success_at=raw.get("last_success_at") or None,
        last_error=raw.get("last_error") or None,
        consecutive_failures=int(raw.get("consecutive_failures") or 0),
        server_url=raw.get("server_url") or None,
        agent_id=raw.get("agent_id") or None,
    )


def _write(state: LinkState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(asdict(state), handle, indent=2, ensure_ascii=False)
        handle.flush()
        # Sans cette synchronisation, le remplacement atomique peut publier un
        # fichier vide après une coupure : le nom est bien remplacé, le
        # contenu n'a pas encore atteint le disque.
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def record_success(
    *,
    server_url: str,
    agent_id: str,
    at: datetime,
    path: Optional[Path] = None,
) -> LinkState:
    target = path or session_file()
    state = LinkState(
        connected=True,
        last_success_at=at.astimezone(timezone.utc).isoformat(),
        last_error=None,
        consecutive_failures=0,
        server_url=server_url,
        agent_id=agent_id,
    )
    _write(state, target)
    return state


def record_failure(
    *,
    server_url: str,
    agent_id: Optional[str],
    error: str,
    path: Optional[Path] = None,
) -> LinkState:
    """Enregistre un échec **sans effacer** la date du dernier succès.

    C'est cette date qui répond à « hors ligne depuis quand ? ». La remettre à
    zéro à chaque échec — le réflexe naturel quand on réécrit l'état complet —
    effacerait la seule information utile au moment précis où on en a besoin.
    """
    target = path or session_file()
    previous = read_state(target)
    state = LinkState(
        connected=False,
        last_success_at=previous.last_success_at,
        last_error=error,
        consecutive_failures=previous.consecutive_failures + 1,
        server_url=server_url,
        agent_id=agent_id or previous.agent_id,
    )
    _write(state, target)
    return state


def clear_state(path: Optional[Path] = None) -> None:
    try:
        (path or session_file()).unlink()
    except FileNotFoundError:
        pass
