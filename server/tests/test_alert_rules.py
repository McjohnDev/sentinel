"""FS4 rules: duration thresholds, maintenance, HMAC, log-pattern."""

from __future__ import annotations

import hmac
import hashlib
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from src.models import (  # noqa: E402
    Agent,
    Alert,
    AlertStatus,
    AlertType,
    GlobalSettings,
    Heartbeat,
    MachineType,
    MaintenanceWindow,
    MessagingConfig,
)
from src.alert_service import AlertService  # noqa: E402
from src.webhook_service import sign_body  # noqa: E402


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
            cpu_warning_threshold=80,
            cpu_critical_threshold=90,
            ram_warning_threshold=80,
            ram_critical_threshold=90,
            disk_warning_threshold=85,
            disk_critical_threshold=95,
            threshold_duration_seconds=60,
            escalate_after_minutes=15,
        )
    )
    db.commit()
    return agent


def _hb(db, agent_id, cpu, when):
    db.add(
        Heartbeat(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            timestamp=when,
            cpu_percent=cpu,
            ram_percent=10,
            disk_percent=10,
        )
    )
    db.commit()


def test_hmac_signature_stable():
    sig = sign_body("secret", b'{"a":1}')
    assert sig == hmac.new(b"secret", b'{"a":1}', hashlib.sha256).hexdigest()
    assert len(sig) == 64


def test_spike_does_not_alert(db):
    agent = _agent(db)
    now = datetime.utcnow()
    _hb(db, agent.id, 95, now)
    alert = AlertService.check_cpu_alert(db, agent.id, 95)
    assert alert is None
    assert db.query(Alert).count() == 0


def test_sustained_cpu_creates_major(db):
    agent = _agent(db)
    now = datetime.utcnow()
    _hb(db, agent.id, 85, now - timedelta(seconds=70))
    _hb(db, agent.id, 86, now)
    alert = AlertService.check_cpu_alert(db, agent.id, 86)
    assert alert is not None
    assert alert.severity.value == "major"
    assert alert.type == AlertType.CPU_HIGH


def test_maintenance_suppresses(db):
    agent = _agent(db)
    gs = db.query(GlobalSettings).first()
    gs.threshold_duration_seconds = 0
    db.add(
        MaintenanceWindow(
            id="mw-1",
            agent_id=agent.id,
            starts_at=datetime.utcnow() - timedelta(hours=1),
            ends_at=datetime.utcnow() + timedelta(hours=1),
            reason="patch window",
            created_by="admin",
        )
    )
    db.commit()
    now = datetime.utcnow()
    _hb(db, agent.id, 99, now)
    alert = AlertService.check_cpu_alert(db, agent.id, 99)
    assert alert is None
    assert db.query(Alert).count() == 0


def test_log_pattern_creates_alert(db):
    agent = _agent(db)
    n = AlertService.check_log_pattern_alerts(db, agent.id, [{"message": "segfault nginx"}])
    assert n == 1
    row = db.query(Alert).filter(Alert.type == AlertType.LOG_PATTERN).first()
    assert row is not None
    assert "segfault" in row.message
    assert row.status == AlertStatus.OPEN


def test_webhook_posted_when_configured(db):
    agent = _agent(db)
    gs = db.query(GlobalSettings).first()
    gs.threshold_duration_seconds = 0
    db.add(
        MessagingConfig(
            id="default",
            webhook_url="http://example.invalid/hook",
            webhook_secret="s3cret",
            webhook_enabled=True,
            enabled=False,
            recipients="[]",
        )
    )
    db.commit()
    now = datetime.utcnow()
    _hb(db, agent.id, 99, now)
    with patch("src.webhook_service.httpx.post") as post:
        post.return_value = MagicMock(status_code=204)
        AlertService.check_cpu_alert(db, agent.id, 99)
        assert post.called
        headers = post.call_args.kwargs["headers"]
        assert headers["X-CBC-Signature"].startswith("sha256=")
    row = db.query(Alert).first()
    assert row.webhook_status == "sent"
    assert row.mail_status in ("failed", "skipped", "sent")
