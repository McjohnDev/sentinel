"""Mail templates + DB-backed messaging config."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

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
from src.models import Agent, MachineType, MailTemplate, MessagingConfig  # noqa: E402
from src.mail_templates import render, resolve, seed_defaults  # noqa: E402
from src.messaging_service import MessagingService  # noqa: E402


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


def test_resolve_prefers_agent_override(db):
    seed_defaults(db)
    db.add(
        MailTemplate(
            id="t-agent",
            kind="alert",
            event_key="disk_high",
            agent_id="ag-1",
            subject="DISQUE {hostname} {mount}",
            body_html="<p>{message}</p>",
        )
    )
    db.commit()
    subj, body = resolve(db, "alert", "disk_high", "ag-1")
    assert subj == "DISQUE {hostname} {mount}"
    assert "{message}" in body
    global_subj, _ = resolve(db, "alert", "disk_high", "other-agent")
    assert "Disque" in global_subj or "DISK" in global_subj.upper() or "{mount}" in global_subj


def test_render_fills_placeholders():
    subject, body = render(
        "[{severity_upper}] {hostname}",
        "<p>{mount}</p>",
        {"severity": "critical", "hostname": "web-01", "mount": "/var"},
    )
    assert subject == "[CRITICAL] web-01"
    assert "/var" in body


def test_db_config_enables_send(db):
    db.add(
        MessagingConfig(
            id="default",
            enabled=True,
            api_endpoint="http://mail.test",
            api_key="k",
            recipients='["ops@cbc.cm"]',
            api_timeout=5,
        )
    )
    db.add(
        Agent(
            id="ag-1",
            machine_id="m1",
            hostname="web-01",
            name="SWIFT-DOU",
            ip_address="10.0.0.8",
            auth_key="k",
            status="active",
            os="linux",
            machine_type=MachineType.SERVER,
        )
    )
    db.commit()
    with patch("src.messaging_service.requests.post") as post:
        post.return_value.status_code = 200
        ok = MessagingService.send_alert_notification(
            alert_type="disk_high",
            severity="critical",
            message="Disque /var 96%",
            hostname="web-01",
            value=96,
            threshold=85,
            db=db,
            agent=db.query(Agent).first(),
            mount="/var",
        )
        assert ok is True
        assert post.called
        payload = post.call_args.kwargs["json"]
        assert payload["to"] == ["ops@cbc.cm"]
        assert payload["is_html"] is True
        assert "web-01" in payload["subject"] or "Disque" in payload["subject"]
        assert "/var" in payload["body"] or "96" in payload["body"]


def test_task_template_lookup(db):
    seed_defaults(db)
    subj, _ = resolve(db, "task", "service.manage:succeeded", None)
    assert "hostname" in subj.lower() or "service" in subj.lower() or "Action" in subj or "{plugin}" in subj
