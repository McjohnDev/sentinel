"""STO-002 — application effective de la politique de rétention.

Régression couverte : `retention_config` était administrable depuis l'interface
mais aucun traitement ne la lisait. Les heartbeats et les alertes résolues
s'accumulaient donc sans limite.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import (
    Agent,
    Alert,
    AlertEvent,
    AlertSeverity,
    AlertStatus,
    AlertType,
    Heartbeat,
    MachineType,
    RetentionConfig,
)
from src.scheduler import job_apply_retention


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


@pytest.fixture
def agent(db):
    a = Agent(
        id=str(uuid.uuid4()),
        machine_id=str(uuid.uuid4()),
        hostname="srv-01",
        ip_address="10.0.0.1",
        os="Linux",
        auth_key=str(uuid.uuid4()),
        status="active",
        machine_type=MachineType.SERVER,
    )
    db.add(a)
    db.commit()
    return a


def _heartbeat(db, agent, *, days_old: int):
    hb = Heartbeat(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        cpu_percent=10.0,
        ram_percent=20.0,
        created_at=datetime.utcnow() - timedelta(days=days_old),
    )
    db.add(hb)
    db.commit()
    return hb


def _alert(db, agent, *, days_old: int, status: AlertStatus):
    a = Alert(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        severity=AlertSeverity.MAJOR,
        type=AlertType.CPU_HIGH,
        message="CPU",
        value=95.0,
        threshold=80.0,
        status=status,
        started_at=datetime.utcnow() - timedelta(days=days_old),
    )
    db.add(a)
    db.commit()
    return a


def _config(db, *, alerts_days: int, heartbeats_days: int):
    db.add(RetentionConfig(id="default", alerts_days=alerts_days, heartbeats_days=heartbeats_days))
    db.commit()


def test_old_heartbeats_are_removed(db, agent):
    _config(db, alerts_days=30, heartbeats_days=7)
    _heartbeat(db, agent, days_old=30)
    _heartbeat(db, agent, days_old=1)

    result = job_apply_retention(db)

    assert result["heartbeats"] == 1
    assert db.query(Heartbeat).count() == 1


def test_resolved_alerts_older_than_policy_are_removed(db, agent):
    _config(db, alerts_days=30, heartbeats_days=7)
    _alert(db, agent, days_old=60, status=AlertStatus.RESOLVED)
    _alert(db, agent, days_old=1, status=AlertStatus.RESOLVED)

    result = job_apply_retention(db)

    assert result["alerts"] == 1
    assert db.query(Alert).count() == 1


def test_open_alerts_are_never_removed(db, agent):
    """Une alerte encore ouverte doit rester visible quel que soit son âge."""
    _config(db, alerts_days=30, heartbeats_days=7)
    _alert(db, agent, days_old=400, status=AlertStatus.OPEN)
    _alert(db, agent, days_old=400, status=AlertStatus.ACKNOWLEDGED)

    result = job_apply_retention(db)

    assert result["alerts"] == 0
    assert db.query(Alert).count() == 2


def test_alert_events_are_removed_with_their_alert(db, agent):
    _config(db, alerts_days=30, heartbeats_days=7)
    alert = _alert(db, agent, days_old=60, status=AlertStatus.RESOLVED)
    db.add(
        AlertEvent(
            id=str(uuid.uuid4()),
            alert_id=alert.id,
            agent_id=agent.id,
            action="opened",
        )
    )
    db.commit()

    result = job_apply_retention(db)

    assert result["alert_events"] == 1
    assert db.query(AlertEvent).count() == 0


def test_defaults_apply_when_no_config_row_exists(db, agent):
    """Sans ligne de configuration, les valeurs par défaut (30 / 7) s'appliquent."""
    _heartbeat(db, agent, days_old=30)
    _alert(db, agent, days_old=60, status=AlertStatus.RESOLVED)

    result = job_apply_retention(db)

    assert result["heartbeats"] == 1
    assert result["alerts"] == 1


def test_zero_disables_the_purge(db, agent):
    """Une valeur nulle signifie « conserver » et ne doit rien supprimer."""
    _config(db, alerts_days=0, heartbeats_days=0)
    _heartbeat(db, agent, days_old=500)
    _alert(db, agent, days_old=500, status=AlertStatus.RESOLVED)

    result = job_apply_retention(db)

    assert result == {"alerts": 0, "alert_events": 0, "heartbeats": 0}
    assert db.query(Heartbeat).count() == 1
    assert db.query(Alert).count() == 1


def test_audit_trail_is_never_purged(db, agent):
    """La conservation de la piste d'audit relève d'une obligation
    réglementaire : elle ne doit pas dépendre d'un réglage d'exploitation."""
    from src.models import AuditLog

    db.add(
        AuditLog(
            id=str(uuid.uuid4()),
            event_type="CREATE_GROUP",
            user_id="u1",
            status="success",
            created_at=datetime.utcnow() - timedelta(days=3000),
        )
    )
    db.commit()
    _config(db, alerts_days=1, heartbeats_days=1)

    job_apply_retention(db)

    assert db.query(AuditLog).count() == 1
