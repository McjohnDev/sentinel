"""Garde-fous contre la disparition silencieuse d'un agent vivant.

Le défaut d'origine tenait en trois temps : la purge effaçait un agent bien
vivant, l'API répondait ensuite 401 en boucle, et **rien** ne le signalait —
ni écran, ni métrique. Ces tests figent les protections qui rendent chacun de
ces trois temps impossible ou visible.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.agent_rejections import FORGET_AFTER, MAX_TRACKED_SOURCES, RejectionLedger  # noqa: E402


# ------------------------------------------------- la lecture ne détruit rien


def test_agent_listing_never_purges():
    """`GET /api/agents` doit être en lecture seule.

    La purge y tournait « opportunément » : ouvrir la liste des agents pouvait
    supprimer des lignes, y compris celle d'un hôte en train de se ré-enrôler.
    Consulter un inventaire ne doit jamais le modifier.
    """
    import inspect

    from src.main import list_agents

    source = inspect.getsource(list_agents)
    assert "purge_stale_agents" not in source, (
        "la purge est repassée dans la route de lecture — "
        "elle appartient à l'ordonnanceur seul"
    )
    assert "db.commit()" not in source, "une route GET ne doit rien écrire"


def test_scheduler_owns_the_purge():
    """La purge doit rester planifiée : sinon plus rien ne nettoie l'inventaire."""
    from src.scheduler import register_default_jobs, scheduler

    register_default_jobs()
    assert any(j["name"] == "purge_stale_agents" for j in scheduler.jobs_state())


# ------------------------------------------- un agent refusé devient visible


@pytest.fixture
def ledger():
    return RejectionLedger()


def test_rejection_is_recorded(ledger):
    ledger.record("10.0.0.4", path="/api/agents/heartbeat")
    rows = ledger.snapshot()
    assert len(rows) == 1
    assert rows[0]["source"] == "10.0.0.4"
    assert rows[0]["attempts"] == 1
    assert rows[0]["paths"] == ["/api/agents/heartbeat"]


def test_repeated_rejections_accumulate_per_source(ledger):
    """Un agent qui boucle doit apparaître une fois, avec son volume."""
    for _ in range(40):
        ledger.record("10.0.0.4", path="/api/agents/heartbeat")
    ledger.record("10.0.0.4", path="/api/agents/ping")
    ledger.record("10.0.0.9", path="/api/agents/heartbeat")

    rows = ledger.snapshot()
    assert len(rows) == 2
    noisy = next(r for r in rows if r["source"] == "10.0.0.4")
    assert noisy["attempts"] == 41
    assert noisy["paths"] == ["/api/agents/heartbeat", "/api/agents/ping"]


def test_summary_reports_something_to_act_on(ledger):
    assert ledger.summary()["sources"] == 0
    ledger.record("10.0.0.4", path="/api/agents/ping")
    summary = ledger.summary()
    assert summary["sources"] == 1
    assert summary["attempts"] == 1
    assert summary["most_recent"]["source"] == "10.0.0.4"


def test_source_forgotten_once_quiet(ledger):
    """Un agent ré-enrôlé ou désinstallé ne doit pas rester en alerte à vie."""
    old = datetime.now(timezone.utc) - (FORGET_AFTER + timedelta(minutes=1))
    ledger.record("10.0.0.4", path="/api/agents/ping", now=old)
    assert ledger.snapshot() == []


def test_ledger_is_bounded(ledger):
    """Registre borné : un balayage d'adresses ne doit pas gonfler la mémoire."""
    for i in range(MAX_TRACKED_SOURCES + 50):
        ledger.record(f"10.0.{i // 256}.{i % 256}", path="/api/agents/ping")
    assert len(ledger.snapshot()) == MAX_TRACKED_SOURCES
