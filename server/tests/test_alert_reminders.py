"""Relance des alertes restees ouvertes.

Une alerte notifiee une fois puis oubliee ne vaut guere mieux qu'une alerte
jamais emise. D'ou un rappel periodique -- trois heures par defaut -- reglable
alerte par alerte : c'est en traitant un incident qu'on sait s'il merite un
rappel rapproche, un rappel lointain, ou aucun.

Ce qui se joue ici tient en trois points : le decompte repart du dernier
message et non de l'ouverture, la prise en charge n'interrompt pas la relance,
et la resolution y met fin.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
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

from src.alert_service import AlertService  # noqa: E402
from src.auth_service import AuthService  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402
from src.models import (  # noqa: E402
    Agent,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertType,
    GlobalSettings,
    MachineType,
    User,
    UserRole,
)

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


@pytest.fixture
def sent(monkeypatch):
    """Capture les notifications, sans toucher a un relais."""
    calls = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(
        "src.alert_service.MessagingService.send_alert_notification",
        staticmethod(_capture),
    )
    return calls


def _agent(db, agent_id="A1B2C3"):
    agent = Agent(
        id=agent_id, machine_id="mid-%s" % uuid.uuid4().hex[:6], hostname="SRV-%s" % agent_id,
        auth_key=str(uuid.uuid4()), status="active", os="linux", machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.commit()
    return agent


def _alert(db, *, agent_id="A1B2C3", age_hours=0.0, status=AlertStatus.OPEN, **kw):
    alert = Alert(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        severity=AlertSeverity.CRITICAL,
        type=AlertType.CPU_HIGH,
        message="CPU au plafond",
        status=status,
        value=97.0,
        threshold=90.0,
        started_at=datetime.utcnow() - timedelta(hours=age_hours),
        **kw,
    )
    db.add(alert)
    db.commit()
    return alert


def _client(db, role=UserRole.ADMIN):
    user = User(
        id=str(uuid.uuid4()), username="adm-%s" % uuid.uuid4().hex[:5], email="a@cbcam.cm",
        password_hash="!x", role=role, is_active=True,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client, user


def _reload(db, alert_id):
    db.expire_all()
    return db.query(Alert).filter(Alert.id == alert_id).first()


# ------------------------------------------------------------------ delais


def test_the_default_is_twelve_hours(db):
    _agent(db)
    assert AlertService.reminder_interval_hours(db, _alert(db)) == 12.0


def test_an_alert_younger_than_the_delay_is_left_alone(db, sent):
    _agent(db)
    _alert(db, age_hours=6)

    assert AlertService.send_due_reminders(db) == 0
    assert sent == []


def test_an_alert_older_than_the_delay_is_reminded(db, sent):
    _agent(db)
    alert = _alert(db, age_hours=14)

    assert AlertService.send_due_reminders(db) == 1
    assert len(sent) == 1
    assert _reload(db, alert.id).reminder_count == 1


def test_the_countdown_restarts_from_the_last_reminder(db, sent):
    """Sans cela, chaque passage du planificateur relancerait la meme alerte."""
    _agent(db)
    _alert(db, age_hours=20)

    AlertService.send_due_reminders(db)
    again = AlertService.send_due_reminders(db)

    assert again == 0
    assert len(sent) == 1


def test_a_second_reminder_follows_after_another_delay(db, sent):
    _agent(db)
    alert = _alert(db, age_hours=14)
    AlertService.send_due_reminders(db)

    reloaded = _reload(db, alert.id)
    reloaded.last_reminder_at = datetime.utcnow() - timedelta(hours=14)
    db.commit()

    assert AlertService.send_due_reminders(db) == 1
    assert _reload(db, alert.id).reminder_count == 2


# -------------------------------------------------------------- ce qui arrete


def test_a_resolved_alert_is_never_reminded(db, sent):
    _agent(db)
    _alert(db, age_hours=48, status=AlertStatus.RESOLVED)

    assert AlertService.send_due_reminders(db) == 0
    assert sent == []


def test_an_assigned_alert_is_still_reminded(db, sent):
    """L'alerte attribuee puis oubliee est le cas que la relance rattrape."""
    _agent(db)
    _alert(db, age_hours=14, assigned_at=datetime.utcnow(), assigned_by="jkoum")

    assert AlertService.send_due_reminders(db) == 1


def test_an_acknowledged_alert_is_still_reminded(db, sent):
    _agent(db)
    _alert(db, age_hours=14, acknowledged_at=datetime.utcnow(), acknowledged_by="jkoum")

    assert AlertService.send_due_reminders(db) == 1


def test_zero_hours_on_the_alert_silences_it(db, sent):
    _agent(db)
    _alert(db, age_hours=72, reminder_hours=0)

    assert AlertService.send_due_reminders(db) == 0


def test_zero_hours_on_the_fleet_silences_everything(db, sent):
    _agent(db)
    db.add(GlobalSettings(id="default", alert_reminder_hours=0))
    db.commit()
    _alert(db, age_hours=72)

    assert AlertService.send_due_reminders(db) == 0


def test_a_maintenance_window_suspends_the_reminder(db, sent, monkeypatch):
    _agent(db)
    _alert(db, age_hours=14)
    monkeypatch.setattr(AlertService, "in_maintenance", staticmethod(lambda db, agent_id: True))

    assert AlertService.send_due_reminders(db) == 0


# ------------------------------------------------------------- par alerte


def test_an_alert_delay_overrides_the_fleet(db, sent):
    _agent(db)
    db.add(GlobalSettings(id="default", alert_reminder_hours=12))
    db.commit()
    _alert(db, age_hours=2, reminder_hours=1)

    assert AlertService.send_due_reminders(db) == 1


def test_a_delay_below_the_floor_is_raised_to_it(db):
    """Une relance a la minute ferait filtrer tous les messages de la plateforme."""
    _agent(db)
    alert = _alert(db, reminder_hours=0.01)

    assert AlertService.reminder_interval_hours(db, alert) == AlertService.MIN_REMINDER_HOURS


# ------------------------------------------------------------------ l'API


THRESHOLDS = {
    "cpu_warning": 80, "cpu_critical": 90, "ram_warning": 80,
    "ram_critical": 90, "disk_warning": 85, "disk_critical": 95,
}


def test_the_fleet_delay_is_stored_and_returned(db):
    client, _ = _client(db)

    response = client.put(
        "/api/settings/thresholds", json={**THRESHOLDS, "alert_reminder_hours": 6}
    )

    assert response.status_code == 200, response.text
    assert client.get("/api/settings/thresholds").json()["alert_reminder_hours"] == 6


def test_the_fleet_delay_defaults_to_twelve_when_never_set(db):
    """Sans cela l'interface annoncerait « aucune relance » et le planificateur relancerait."""
    client, _ = _client(db)
    assert client.get("/api/settings/thresholds").json()["alert_reminder_hours"] == 12.0


def test_setting_an_alert_delay_through_the_api(db):
    client, _ = _client(db)
    _agent(db)
    alert = _alert(db)

    response = client.put("/api/alerts/%s/reminder" % alert.id, json={"hours": 1.5})

    assert response.status_code == 200, response.text
    assert response.json()["effective_hours"] == 1.5
    assert _reload(db, alert.id).reminder_hours == 1.5


def test_clearing_an_alert_delay_returns_it_to_the_fleet(db):
    client, _ = _client(db)
    _agent(db)
    alert = _alert(db, reminder_hours=1)

    client.put("/api/alerts/%s/reminder" % alert.id, json={"hours": None})

    assert _reload(db, alert.id).reminder_hours is None
    assert AlertService.reminder_interval_hours(db, _reload(db, alert.id)) == 12.0


def test_shortening_the_delay_does_not_fire_at_once(db, sent):
    """Un delai raccourci se compte depuis maintenant, non depuis l'ouverture."""
    client, _ = _client(db)
    _agent(db)
    alert = _alert(db, age_hours=48)

    client.put("/api/alerts/%s/reminder" % alert.id, json={"hours": 1})

    # L'API a ecrit dans sa propre session ; sans cela, celle du test
    # relirait son instantane et le decompte paraitrait inchange.
    db.expire_all()
    assert AlertService.send_due_reminders(db) == 0


def test_a_negative_delay_is_refused(db):
    client, _ = _client(db)
    _agent(db)
    alert = _alert(db)

    assert client.put("/api/alerts/%s/reminder" % alert.id, json={"hours": -3}).status_code == 400


def test_an_unknown_alert_is_reported_as_such(db):
    client, _ = _client(db)
    assert client.put("/api/alerts/inconnue/reminder", json={"hours": 1}).status_code == 404


def test_a_reader_cannot_change_the_delay(db):
    client, _ = _client(db, UserRole.READ_ONLY)
    _agent(db)
    alert = _alert(db)

    assert client.put("/api/alerts/%s/reminder" % alert.id, json={"hours": 1}).status_code == 403


# ------------------------------------------------------ ce que recoit le lecteur


def test_the_reminder_is_marked_as_such_in_the_message(db, sent):
    """Sans marque, la relance se lit comme un second incident."""
    _agent(db)
    _alert(db, age_hours=14)

    AlertService.send_due_reminders(db)

    assert sent[0]["reminder_number"] == 1


def test_a_first_notification_is_not_marked_as_a_reminder(db, sent):
    _agent(db)
    AlertService._notify(db, _alert(db))

    assert sent[0]["reminder_number"] == 0
