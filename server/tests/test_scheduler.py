"""ALR-002 / ALR-006 / NFR-010 — ordonnanceur de tâches périodiques.

Régression couverte : la détection hors ligne et l'escalade tournaient dans le
handler de heartbeat. Lors d'une panne de parc, plus aucun agent n'émettait de
heartbeat, donc l'évaluation ne tournait plus et aucune alerte AGENT_OFFLINE
n'était levée — précisément le scénario que le produit doit détecter.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import Agent, Alert, AlertStatus, AlertType, MachineType
from src.alert_service import AlertService
from src.scheduler import PlatformScheduler, job_offline_and_escalation


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _agent(db, *, silent_for_seconds: int, machine_type=MachineType.SERVER) -> Agent:
    agent = Agent(
        id=str(uuid.uuid4()),
        machine_id=str(uuid.uuid4()),
        hostname="srv-test",
        ip_address="10.0.0.1",
        os="Linux",
        auth_key=str(uuid.uuid4()),
        status="active",
        machine_type=machine_type,
        enrolled_at=datetime.utcnow() - timedelta(days=1),
        last_communication=datetime.utcnow() - timedelta(seconds=silent_for_seconds),
    )
    db.add(agent)
    db.commit()
    return agent


# ------------------------------------------------------------- boucle de jobs


def test_job_runs_without_any_inbound_request():
    scheduler = PlatformScheduler(tick_seconds=0.05)
    calls = []
    scheduler.register("probe", 0.1, lambda _db: calls.append(1), run_on_start=True)
    scheduler.start()
    try:
        deadline = time.monotonic() + 3.0
        while len(calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        scheduler.stop()
    assert len(calls) >= 2, "le job doit s'exécuter de lui-même, sans requête entrante"


def test_failing_job_does_not_kill_the_loop():
    scheduler = PlatformScheduler(tick_seconds=0.05)
    healthy = []

    def boom(_db):
        raise RuntimeError("échec simulé")

    scheduler.register("boom", 0.1, boom)
    scheduler.register("healthy", 0.1, lambda _db: healthy.append(1))
    scheduler.start()
    try:
        deadline = time.monotonic() + 3.0
        while len(healthy) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        scheduler.stop()

    assert len(healthy) >= 2, "un job en échec ne doit pas arrêter les autres"
    state = {j["name"]: j for j in scheduler.jobs_state()}
    assert state["boom"]["error_count"] >= 1
    assert "échec simulé" in (state["boom"]["last_error"] or "")


def test_stop_is_idempotent_and_reports_state():
    scheduler = PlatformScheduler(tick_seconds=0.05)
    scheduler.register("noop", 1, lambda _db: None)
    scheduler.start()
    assert scheduler.running
    scheduler.stop()
    scheduler.stop()
    assert not scheduler.running


def test_duplicate_registration_is_ignored():
    scheduler = PlatformScheduler()
    scheduler.register("dup", 1, lambda _db: None)
    scheduler.register("dup", 1, lambda _db: None)
    assert len([j for j in scheduler.jobs_state() if j["name"] == "dup"]) == 1


def test_invalid_interval_is_rejected():
    scheduler = PlatformScheduler()
    scheduler.register("bad", 0, lambda _db: None)
    assert scheduler.jobs_state() == []


# ------------------------------------------- détection hors ligne sans agent


def test_offline_detected_with_no_heartbeat_at_all(db):
    """Le cœur de la régression : un parc entier muet doit lever une alerte.

    L'agent n'émet plus depuis bien au-delà du seuil serveur (90 s). Le job
    doit produire une alerte AGENT_OFFLINE sans qu'aucune requête n'arrive.
    """
    agent = _agent(db, silent_for_seconds=3600)

    job_offline_and_escalation(db)

    alert = (
        db.query(Alert)
        .filter(Alert.agent_id == agent.id, Alert.type == AlertType.AGENT_OFFLINE)
        .first()
    )
    assert alert is not None, "aucune alerte hors ligne levée pour un agent muet"
    assert alert.status == AlertStatus.OPEN


def test_live_agent_raises_no_offline_alert(db):
    agent = _agent(db, silent_for_seconds=5)

    job_offline_and_escalation(db)

    alert = (
        db.query(Alert)
        .filter(Alert.agent_id == agent.id, Alert.type == AlertType.AGENT_OFFLINE)
        .first()
    )
    assert alert is None


def test_offline_job_is_idempotent(db):
    """Deux passages consécutifs ne doivent pas empiler les alertes."""
    agent = _agent(db, silent_for_seconds=3600)

    job_offline_and_escalation(db)
    job_offline_and_escalation(db)

    count = (
        db.query(Alert)
        .filter(Alert.agent_id == agent.id, Alert.type == AlertType.AGENT_OFFLINE)
        .count()
    )
    assert count == 1
