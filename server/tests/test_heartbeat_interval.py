"""Cadence de battement : globale, et par hote.

Imposer la meme cadence a tout le parc oblige a choisir entre surveiller trop
peu les machines critiques et trop souvent les autres. D'ou deux reglages :
une cadence de parc, et une surcharge par hote.

Le point delicat est la borne haute. Le serveur declare un hote hors ligne
au-dela de `heartbeat_timeout_seconds` : une cadence plus lente que ce seuil
ferait basculer *tous* les hotes en panne permanente sans qu'aucun ne le soit.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_DISABLED", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src import monitoring_plan  # noqa: E402
from src.auth_service import AuthService  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402
from src.models import Agent, GlobalSettings, MachineType, User, UserRole  # noqa: E402

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(bind=engine)


def _admin(db):
    user = User(
        id=str(uuid.uuid4()), username="adm-%s" % uuid.uuid4().hex[:5],
        email="a@cbcam.cm", password_hash="!x", role=UserRole.ADMIN, is_active=True,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client


def _agent(db, agent_id="A3F09C", interval=None):
    agent = Agent(
        id=agent_id, machine_id="mid-%s" % uuid.uuid4().hex[:6], hostname="SRV-%s" % agent_id,
        auth_key=str(uuid.uuid4()), status="active", os="linux",
        machine_type=MachineType.SERVER, heartbeat_interval_seconds=interval,
    )
    db.add(agent)
    db.commit()
    return agent


def _reload(db, agent_id):
    db.expire_all()
    return db.query(Agent).filter(Agent.id == agent_id).first()


THRESHOLDS = {
    "cpu_warning": 80, "cpu_critical": 90,
    "ram_warning": 80, "ram_critical": 90,
    "disk_warning": 85, "disk_critical": 95,
}


# ----------------------------------------------------------------- bornes


def test_the_ceiling_stays_below_the_offline_threshold():
    """La borne haute n'est pas arbitraire : elle protege d'un parc fantome."""
    from src.config import settings

    timeout = int(getattr(settings, "heartbeat_timeout_seconds", 90) or 90)
    assert monitoring_plan.max_heartbeat_seconds() < timeout


def test_the_default_applies_when_nothing_is_set(db):
    agent = _agent(db)
    assert monitoring_plan.effective_heartbeat_seconds(db, agent) == monitoring_plan.DEFAULT_HEARTBEAT_SECONDS


# --------------------------------------------------------------- globale


def test_the_fleet_cadence_is_stored_and_applied(db):
    client = _admin(db)
    agent = _agent(db)

    response = client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 15})

    assert response.status_code == 200, response.text
    assert monitoring_plan.effective_heartbeat_seconds(db, _reload(db, agent.id)) == 15


def test_a_cadence_slower_than_the_offline_threshold_is_refused(db):
    # Sans ce refus, tout le parc serait affiche en panne en permanence.
    client = _admin(db)
    response = client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 600})
    assert response.status_code == 400
    assert "hors ligne" in response.json()["detail"]


def test_an_absurdly_fast_cadence_is_refused(db):
    # Un reglage a la seconde noierait la plateforme sous les battements.
    client = _admin(db)
    assert client.put(
        "/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 1}
    ).status_code == 400


def test_changing_the_fleet_cadence_republishes_to_followers(db):
    """Sans republication, le reglage resterait affiche sans atteindre les hotes."""
    client = _admin(db)
    follower = _agent(db, "AAAAAA")
    before = int(follower.monitoring_version or 0)

    client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 20})

    assert int(_reload(db, "AAAAAA").monitoring_version or 0) > before


def test_a_host_with_its_own_cadence_is_not_republished(db):
    # Lui repousser un plan inchange le ferait travailler pour rien.
    client = _admin(db)
    own = _agent(db, "BBBBBB", interval=45)
    before = int(own.monitoring_version or 0)

    client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 20})

    assert int(_reload(db, "BBBBBB").monitoring_version or 0) == before


# --------------------------------------------------------------- par hote


def test_a_host_cadence_overrides_the_fleet(db):
    """Un serveur SWIFT merite dix secondes la ou un poste se contente d'une minute."""
    client = _admin(db)
    client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 30})
    agent = _agent(db, "CCCCCC")

    response = client.patch("/api/agents/CCCCCC", json={"heartbeat_interval_seconds": 10})

    assert response.status_code == 200, response.text
    assert monitoring_plan.effective_heartbeat_seconds(db, _reload(db, "CCCCCC")) == 10


def test_clearing_the_host_cadence_returns_to_the_fleet(db):
    client = _admin(db)
    client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 25})
    _agent(db, "DDDDDD", interval=10)

    client.patch("/api/agents/DDDDDD", json={"heartbeat_interval_seconds": None})

    assert monitoring_plan.effective_heartbeat_seconds(db, _reload(db, "DDDDDD")) == 25


def test_a_host_cadence_out_of_bounds_is_refused_with_the_reason(db):
    client = _admin(db)
    _agent(db, "EEEEEE")

    response = client.patch("/api/agents/EEEEEE", json={"heartbeat_interval_seconds": 900})

    assert response.status_code == 400
    assert "hors ligne" in response.json()["detail"]
    assert _reload(db, "EEEEEE").heartbeat_interval_seconds is None


def test_setting_a_host_cadence_republishes_its_plan(db):
    client = _admin(db)
    agent = _agent(db, "FFFFFF")
    before = int(agent.monitoring_version or 0)

    client.patch("/api/agents/FFFFFF", json={"heartbeat_interval_seconds": 15})

    assert int(_reload(db, "FFFFFF").monitoring_version or 0) > before


# ------------------------------------------------------ transmission a l'agent


def test_the_plan_carries_the_cadence_to_the_agent(db):
    client = _admin(db)
    client.put("/api/settings/thresholds", json={**THRESHOLDS, "heartbeat_interval_seconds": 20})
    agent = _agent(db, "GGGGGG")

    payload = monitoring_plan.agent_config_payload(db, _reload(db, agent.id))

    assert payload["agent"]["heartbeat_interval_seconds"] == 20


def test_a_value_written_directly_in_the_database_is_still_bounded(db):
    """Un reglage herite d'une version anterieure ne doit pas rendre un hote muet."""
    agent = _agent(db, "HHHHHH")
    agent.heartbeat_interval_seconds = 86400
    db.commit()

    effective = monitoring_plan.effective_heartbeat_seconds(db, _reload(db, "HHHHHH"))

    assert effective <= monitoring_plan.max_heartbeat_seconds()


def test_a_stored_global_value_out_of_bounds_is_also_clamped(db):
    row = GlobalSettings(id="default", heartbeat_interval_seconds=0)
    db.add(row)
    db.commit()
    agent = _agent(db, "IIIIII")

    assert monitoring_plan.effective_heartbeat_seconds(db, agent) >= monitoring_plan.HEARTBEAT_MIN_SECONDS
