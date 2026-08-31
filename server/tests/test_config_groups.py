"""FS5 — machine groups, remote config, footprint, overlaps."""

from __future__ import annotations

import os
import sys
import uuid
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
from src.models import Agent, MachineType
from src.config_service import ConfigService, deep_merge
from src.alert_service import AlertService
from src.models import Alert, AlertType, GlobalSettings


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


def _agent(db, agent_id="ag-1"):
    agent = Agent(
        id=agent_id,
        machine_id=f"mid-{agent_id}",
        hostname="agence-01",
        auth_key=f"key-{agent_id}",
        status="active",
        os="linux",
        machine_type=MachineType.WORKSTATION,
        config_version_acked=0,
    )
    db.add(agent)
    db.add(GlobalSettings(id="default", agent_cpu_max_percent=2.0, agent_ram_max_mb=300.0))
    db.commit()
    return agent


def test_deep_merge():
    assert deep_merge({"a": 1, "b": {"x": 1}}, {"b": {"y": 2}, "c": 3}) == {
        "a": 1,
        "b": {"x": 1, "y": 2},
        "c": 3,
    }


def test_publish_and_pending(db):
    agent = _agent(db)
    group = ConfigService.create_group(db, "Agence", "Branches")
    ConfigService.assign_agent(db, agent.id, group.id)
    rev = ConfigService.publish(
        db,
        group.id,
        {
            "metrics": {"processes": {"watched": ["nginx"]}},
            "services_monitoring": {"enabled": True, "services": ["sshd"]},
        },
        created_by="admin",
        note="initial",
    )
    assert rev.version == 1
    db.refresh(agent)
    pending = ConfigService.pending_for_agent(db, agent)
    assert pending is not None
    version, payload = pending
    assert version == 1
    assert payload["services_monitoring"]["services"] == ["sshd"]
    ConfigService.ack(db, agent.id, 1)
    db.refresh(agent)
    assert ConfigService.pending_for_agent(db, agent) is None


def test_rollback_creates_new_version(db):
    agent = _agent(db)
    group = ConfigService.create_group(db, "HQ")
    ConfigService.assign_agent(db, agent.id, group.id)
    ConfigService.publish(db, group.id, {"agent": {"heartbeat_interval": 30}}, note="v1")
    ConfigService.publish(db, group.id, {"agent": {"heartbeat_interval": 60}}, note="v2")
    rev = ConfigService.rollback(db, group.id, 1, created_by="admin")
    assert rev.version == 3
    assert '"heartbeat_interval": 30' in rev.payload or '"heartbeat_interval":30' in rev.payload.replace(" ", "")


def test_footprint_alert(db):
    agent = _agent(db)
    alert = AlertService.check_footprint_alert(db, agent.id, 5.0, 50.0)
    assert alert is not None
    assert alert.type == AlertType.AGENT_FOOTPRINT
    AlertService.check_footprint_alert(db, agent.id, 0.5, 50.0)
    row = (
        db.query(Alert)
        .filter(Alert.type == AlertType.AGENT_FOOTPRINT, Alert.agent_id == agent.id)
        .first()
    )
    assert row is not None
    assert row.status.value == "resolved"
