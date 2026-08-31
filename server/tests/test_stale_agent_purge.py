"""Live-only fleet + stale agent purge."""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.database import Base  # noqa: E402
from src.models import Agent, MachineType  # noqa: E402
from src.agent_purge import (  # noqa: E402
    RETIRED,
    derived_agent_status,
    is_agent_live,
    last_seen_age_seconds,
    note_platform_start,
    purge_stale_agents,
)

#: La purge ne compte que le silence écoulé pendant que la plateforme tournait.
#: Les tests simulent donc une plateforme en ligne depuis longtemps.
LONG_UPTIME = 400 * 86400


@pytest.fixture(autouse=True)
def platform_up():
    """Par défaut : plateforme en ligne depuis longtemps (sas de démarrage passé)."""
    note_platform_start(assume_uptime_seconds=LONG_UPTIME)


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


def _agent(db, *, hostname="host-1", machine_type=MachineType.SERVER, last_communication=None, status="active"):
    agent = Agent(
        id=str(uuid.uuid4()),
        machine_id=f"mid-{hostname}-{uuid.uuid4().hex[:6]}",
        hostname=hostname,
        auth_key=str(uuid.uuid4()),
        status=status,
        os="linux",
        machine_type=machine_type,
        last_communication=last_communication,
        enrolled_at=datetime.utcnow() - timedelta(days=10),
    )
    db.add(agent)
    db.commit()
    return agent


def test_live_agent_not_purged(db):
    live = _agent(db, hostname="live", last_communication=datetime.utcnow())
    deleted = purge_stale_agents(db)
    db.commit()
    assert deleted == []
    assert db.query(Agent).filter(Agent.id == live.id).first() is not None
    assert is_agent_live(live) is True


def test_stale_server_retired_after_24h(db):
    """Premier étage : l'hôte silencieux sort de l'inventaire mais garde son identité."""
    stale = _agent(
        db,
        hostname="ghost",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(hours=25),
    )
    key_before = stale.auth_key
    actions = purge_stale_agents(db)
    db.commit()
    assert len(actions) == 1
    assert actions[0]["hostname"] == "ghost"
    assert actions[0]["action"] == "retired"
    row = db.query(Agent).filter(Agent.id == stale.id).first()
    assert row is not None, "un agent retiré doit conserver sa ligne"
    assert row.status == RETIRED
    assert row.auth_key == key_before, "la clé d'auth survit : retour possible sans jeton"


def test_retired_agent_deleted_after_retention(db):
    """Second étage : abandon confirmé, suppression définitive."""
    stale = _agent(
        db,
        hostname="abandoned",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(days=45),
        status=RETIRED,
    )
    actions = purge_stale_agents(db)
    db.commit()
    assert [a["action"] for a in actions] == ["deleted"]
    assert db.query(Agent).filter(Agent.id == stale.id).first() is None


def test_retired_agent_kept_when_platform_just_came_back(db):
    """Sortie de panne : rétention atteinte à l'horloge murale, mais pas de
    silence réellement observé — l'hôte garde sa place le temps de se manifester."""
    stale = _agent(
        db,
        hostname="long-outage",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(days=45),
        status=RETIRED,
    )
    note_platform_start(assume_uptime_seconds=1200)  # sas franchi, 20 min d'écoute
    assert purge_stale_agents(db) == []
    assert db.query(Agent).filter(Agent.id == stale.id).first() is not None


def test_nothing_purged_during_startup_grace(db):
    """Après un redémarrage, tout le parc paraît muet : ne rien supprimer."""
    stale = _agent(
        db,
        hostname="post-outage",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(days=6),
    )
    note_platform_start()  # plateforme qui vient de démarrer
    assert purge_stale_agents(db) == []
    assert db.query(Agent).filter(Agent.id == stale.id).first() is not None
    assert db.query(Agent).filter(Agent.id == stale.id).first().status == "active"


def test_outage_silence_not_charged_to_agent(db):
    """6 jours de coupure plateforme ne valent pas 6 jours de silence agent."""
    stale = _agent(
        db,
        hostname="blamed",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(days=6),
    )
    # Sas franchi, mais la plateforme n'écoute que depuis 20 minutes.
    note_platform_start(assume_uptime_seconds=1200)
    assert purge_stale_agents(db) == []
    assert db.query(Agent).filter(Agent.id == stale.id).first().status == "active"


def test_freshly_enrolled_agent_survives_purge(db):
    """Course enrôlement / purge : un hôte ré-enrôlé à l'instant reste en base."""
    fresh = _agent(
        db,
        hostname="just-enrolled",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow(),
    )
    fresh.enrolled_at = datetime.utcnow()
    db.commit()
    assert purge_stale_agents(db) == []
    assert db.query(Agent).filter(Agent.id == fresh.id).first() is not None


def test_recently_offline_server_kept(db):
    recent = _agent(
        db,
        hostname="blip",
        machine_type=MachineType.SERVER,
        last_communication=datetime.utcnow() - timedelta(hours=2),
    )
    deleted = purge_stale_agents(db)
    db.commit()
    assert deleted == []
    assert db.query(Agent).filter(Agent.id == recent.id).first() is not None
    assert is_agent_live(recent) is False
    assert derived_agent_status(recent) == "offline"
    assert last_seen_age_seconds(recent) >= 2 * 3600


def test_derived_status_active_when_heartbeating(db):
    live = _agent(db, hostname="now", last_communication=datetime.utcnow())
    assert derived_agent_status(live) == "active"
    assert last_seen_age_seconds(live) == 0


def test_derived_status_revoked(db):
    gone = _agent(db, hostname="rev", last_communication=datetime.utcnow(), status="revoked")
    assert is_agent_live(gone) is False
    assert derived_agent_status(gone) == "revoked"
