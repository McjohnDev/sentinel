"""Per-mount disk alert rules."""

from __future__ import annotations

import json
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
from src.models import Agent, Alert, AlertType, GlobalSettings, Heartbeat, MachineType  # noqa: E402
from src.alert_service import AlertService  # noqa: E402


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
        hostname="web-01",
        auth_key=f"key-{agent_id}",
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.add(
        GlobalSettings(
            id="default",
            disk_warning_threshold=80,
            disk_critical_threshold=90,
            threshold_duration_seconds=0,
        )
    )
    db.commit()
    return agent


def _hb(db, agent_id, disks, when):
    primary = disks[0] if disks else {"mount": "/", "percent": 10}
    db.add(
        Heartbeat(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            timestamp=when,
            cpu_percent=1,
            ram_percent=1,
            disk_percent=primary["percent"],
            disk_mount=primary.get("mount"),
            disks_json=json.dumps(disks),
        )
    )
    db.commit()


def test_disk_alert_only_on_flagged_mount(db):
    agent = _agent(db)
    now = datetime.utcnow()
    disks = [
        {"mount": "/", "percent": 95, "alert": False},
        {"mount": "/var", "percent": 92, "alert": True},
    ]
    _hb(db, agent.id, disks, now)
    AlertService.check_disk_alerts(db, agent.id, disks, 95, "/")
    mounts = {a.mount for a in db.query(Alert).filter(Alert.type == AlertType.DISK_HIGH).all()}
    assert mounts == {"/var"}


def test_separate_alerts_per_mount(db):
    agent = _agent(db)
    now = datetime.utcnow()
    disks = [
        {"mount": "/", "percent": 91, "alert": True},
        {"mount": "/var", "percent": 93, "alert": True},
    ]
    _hb(db, agent.id, disks, now)
    AlertService.check_disk_alerts(db, agent.id, disks, 91, "/")
    rows = db.query(Alert).filter(Alert.type == AlertType.DISK_HIGH).all()
    assert len(rows) == 2
    assert {r.mount for r in rows} == {"/", "/var"}


def test_sustained_mount_uses_disks_json(db):
    agent = _agent(db)
    gs = db.query(GlobalSettings).first()
    gs.threshold_duration_seconds = 60
    db.commit()
    now = datetime.utcnow()
    disks_high = [{"mount": "/data", "percent": 88, "alert": True}]
    _hb(db, agent.id, disks_high, now - timedelta(seconds=70))
    _hb(db, agent.id, disks_high, now)
    AlertService.check_disk_alerts(db, agent.id, disks_high, 88, "/data")
    row = db.query(Alert).filter(Alert.mount == "/data").first()
    assert row is not None


def test_per_mount_threshold_overrides_global(db):
    agent = _agent(db)
    gs = db.query(GlobalSettings).first()
    # Global would alert at 80; /u01 only alerts from 95
    gs.disk_mount_rules = json.dumps([{"mount": "/u01", "warning": 95, "critical": 98}])
    db.commit()
    now = datetime.utcnow()
    disks = [
        {"mount": "/", "percent": 50, "alert": False},
        {"mount": "/u01", "percent": 92, "alert": False},
    ]
    _hb(db, agent.id, disks, now)
    AlertService.check_disk_alerts(db, agent.id, disks, 50, "/")
    assert db.query(Alert).count() == 0

    disks_high = [
        {"mount": "/", "percent": 50, "alert": False},
        {"mount": "/u01", "percent": 96, "alert": False},
    ]
    _hb(db, agent.id, disks_high, now)
    AlertService.check_disk_alerts(db, agent.id, disks_high, 50, "/")
    row = db.query(Alert).filter(Alert.mount == "/u01").first()
    assert row is not None
    assert row.threshold == 95
