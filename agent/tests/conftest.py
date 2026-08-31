"""Configuration commune aux tests de l'agent.

`agent/src` est ajouté au chemin d'import : les modules de l'agent s'importent
entre eux à plat (`from config import ...`), parce que le binaire figé les
embarque sans paquet parent.

Chaque test reçoit un répertoire d'état isolé : sans cela, la suite écrirait
l'identité et les jetons de la machine qui l'exécute, et un `enroll` de test
laisserait des traces dans /var/lib ou ProgramData.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_paths import STATE_DIR_ENV  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Isole l'état de l'agent dans un répertoire temporaire."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    # Les surcharges par environnement ne doivent pas fuiter d'une machine de
    # développement vers les assertions.
    monkeypatch.delenv("CBC_ENROLLMENT_TOKEN", raising=False)
    monkeypatch.delenv("CBC_SERVER_URL", raising=False)
    return state
