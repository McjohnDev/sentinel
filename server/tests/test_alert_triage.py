"""Workflow interne d'une alerte : validation, prise en charge, résolution.

Trois moments distincts, et c'est la distinction qui compte. Savoir qu'un
incident est réel ne dit pas qui le traite ; une alerte validée mais non
attribuée n'appartient à personne, et c'est ainsi qu'elle reste ouverte
pendant que chacun suppose qu'un autre s'en occupe.
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

from src.auth_service import AuthService  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402
from src.models import (  # noqa: E402
    Agent,
    Alert,
    AlertEvent,
    AlertSeverity,
    AlertStatus,
    AlertType,
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


def _user(db, username, role=UserRole.OPERATOR, active=True):
    user = User(
        id=str(uuid.uuid4()), username=username, email="%s@cbcam.cm" % username,
        password_hash="!x", role=role, is_active=active,
    )
    db.add(user)
    db.commit()
    return user


def _client(user):
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client


def _agent(db):
    agent = Agent(
        id="A3F09C", machine_id="mid-1", hostname="web-01", auth_key=str(uuid.uuid4()),
        status="active", os="linux", machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.commit()
    return agent


def _alert(db, status=AlertStatus.OPEN):
    _agent(db) if not db.query(Agent).first() else None
    alert = Alert(
        id=str(uuid.uuid4()), agent_id="A3F09C", severity=AlertSeverity.CRITICAL,
        type=AlertType.DISK_HIGH, message="Disque /u01 à 96 %", status=status,
    )
    db.add(alert)
    db.commit()
    return alert


def _reload(db, alert_id):
    db.expire_all()
    return db.query(Alert).filter(Alert.id == alert_id).first()


def _events(db, alert_id):
    return [e.action for e in db.query(AlertEvent).filter(AlertEvent.alert_id == alert_id).all()]


# ----------------------------------------------------------- validation


def test_validating_records_who_and_the_verdict(db):
    sina = _user(db, "sina")
    alert = _alert(db)

    response = _client(sina).post(
        "/api/alerts/%s/acknowledge" % alert.id,
        json={"comment": "confirmé sur la machine", "verdict": "real"},
    )

    assert response.status_code == 200, response.text
    stored = _reload(db, alert.id)
    assert stored.status == AlertStatus.ACKNOWLEDGED
    assert stored.acknowledged_by == "sina"
    assert stored.verdict == "real"


def test_a_false_positive_is_recorded_as_such(db):
    # Une vérification qui crie pour rien doit se voir : sans cette trace on
    # ne la corrige jamais, et les opérateurs apprennent à ignorer ses alertes.
    sina = _user(db, "sina")
    alert = _alert(db)

    _client(sina).post(
        "/api/alerts/%s/acknowledge" % alert.id,
        json={"verdict": "false_positive", "comment": "seuil trop bas"},
    )

    assert _reload(db, alert.id).verdict == "false_positive"
    assert "dismissed_false_positive" in _events(db, alert.id)


def test_an_unknown_verdict_is_refused(db):
    sina = _user(db, "sina")
    alert = _alert(db)
    response = _client(sina).post(
        "/api/alerts/%s/acknowledge" % alert.id, json={"verdict": "peut-etre"}
    )
    assert response.status_code == 400


def test_validating_without_a_verdict_still_works(db):
    # Le verdict est un enrichissement, pas une contrainte nouvelle : les
    # appels existants ne doivent pas se mettre à échouer.
    sina = _user(db, "sina")
    alert = _alert(db)
    response = _client(sina).post("/api/alerts/%s/acknowledge" % alert.id, json={})
    assert response.status_code == 200
    assert _reload(db, alert.id).verdict is None


# ------------------------------------------------------- prise en charge


def test_assigning_gives_the_alert_an_owner(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    bryan = _user(db, "bryan")
    alert = _alert(db)

    response = _client(admin).post(
        "/api/alerts/%s/assign" % alert.id, json={"user_id": bryan.id}
    )

    assert response.status_code == 200, response.text
    assert response.json()["assigned_to_username"] == "bryan"
    stored = _reload(db, alert.id)
    assert stored.assigned_to == bryan.id
    assert stored.assigned_by == "admin"
    assert stored.assigned_at is not None
    assert "assigned" in _events(db, alert.id)


def test_an_alert_can_be_handed_back_to_nobody(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    bryan = _user(db, "bryan")
    alert = _alert(db)
    client = _client(admin)
    client.post("/api/alerts/%s/assign" % alert.id, json={"user_id": bryan.id})

    response = client.post("/api/alerts/%s/assign" % alert.id, json={"user_id": None})

    assert response.status_code == 200
    stored = _reload(db, alert.id)
    assert stored.assigned_to is None
    assert stored.assigned_at is None
    assert "unassigned" in _events(db, alert.id)


def test_an_unknown_user_cannot_be_given_the_alert(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    alert = _alert(db)
    response = _client(admin).post(
        "/api/alerts/%s/assign" % alert.id, json={"user_id": str(uuid.uuid4())}
    )
    assert response.status_code == 400
    assert _reload(db, alert.id).assigned_to is None


def test_a_disabled_account_cannot_take_charge(db):
    # Confier un incident à un compte désactivé revient à ne le confier à
    # personne, en donnant l'apparence du contraire.
    admin = _user(db, "admin", UserRole.ADMIN)
    parti = _user(db, "parti", active=False)
    alert = _alert(db)

    response = _client(admin).post(
        "/api/alerts/%s/assign" % alert.id, json={"user_id": parti.id}
    )

    assert response.status_code == 400
    assert "désactivé" in response.json()["detail"]
    assert _reload(db, alert.id).assigned_to is None


def test_a_resolved_alert_can_no_longer_be_assigned(db):
    # Lui donner un responsable après coup ferait apparaître du travail à
    # faire là où il n'y en a plus.
    admin = _user(db, "admin", UserRole.ADMIN)
    bryan = _user(db, "bryan")
    alert = _alert(db, status=AlertStatus.RESOLVED)

    response = _client(admin).post(
        "/api/alerts/%s/assign" % alert.id, json={"user_id": bryan.id}
    )

    assert response.status_code == 400


def test_assignment_is_independent_of_validation(db):
    """Savoir qu'un incident est réel ne dit pas qui le traite."""
    admin = _user(db, "admin", UserRole.ADMIN)
    bryan = _user(db, "bryan")
    alert = _alert(db)

    _client(admin).post("/api/alerts/%s/assign" % alert.id, json={"user_id": bryan.id})

    stored = _reload(db, alert.id)
    assert stored.assigned_to == bryan.id
    # L'alerte n'a pas été validée pour autant : elle reste ouverte.
    assert stored.status == AlertStatus.OPEN
    assert stored.verdict is None


# -------------------------------------------------------------- résolution


def test_resolving_no_longer_erases_who_validated(db):
    """Régression : la résolution écrasait `acknowledged_by`.

    Une alerte validée par l'un et résolue par l'autre ne gardait qu'un seul
    nom — celui du résolveur — et la trace de la validation disparaissait au
    moment où elle devenait un fait établi.
    """
    sina = _user(db, "sina")
    bryan = _user(db, "bryan")
    alert = _alert(db)

    _client(sina).post(
        "/api/alerts/%s/acknowledge" % alert.id, json={"verdict": "real", "comment": "vu"}
    )
    _client(bryan).post("/api/alerts/%s/resolve" % alert.id, json={"comment": "disque étendu"})

    stored = _reload(db, alert.id)
    assert stored.acknowledged_by == "sina", "le validateur doit survivre à la résolution"
    assert stored.resolved_by == "bryan"
    assert stored.status == AlertStatus.RESOLVED


def test_resolving_without_a_comment_keeps_the_validation_comment(db):
    sina = _user(db, "sina")
    alert = _alert(db)
    client = _client(sina)
    client.post("/api/alerts/%s/acknowledge" % alert.id, json={"comment": "constaté sur site"})

    client.post("/api/alerts/%s/resolve" % alert.id, json={})

    assert _reload(db, alert.id).acknowledged_comment == "constaté sur site"


# ------------------------------------------------------------- restitution


def test_the_alert_list_carries_the_whole_workflow(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    bryan = _user(db, "bryan")
    alert = _alert(db)
    client = _client(admin)
    client.post("/api/alerts/%s/acknowledge" % alert.id, json={"verdict": "real"})
    client.post("/api/alerts/%s/assign" % alert.id, json={"user_id": bryan.id})

    rows = client.get("/api/alerts").json()
    rows = rows.get("data", rows) if isinstance(rows, dict) else rows
    row = next(r for r in rows if r["id"] == alert.id)

    assert row["verdict"] == "real"
    assert row["assigned_to_username"] == "bryan"
    assert row["assigned_by"] == "admin"


def test_the_timeline_keeps_every_step(db):
    sina = _user(db, "sina")
    bryan = _user(db, "bryan", UserRole.ADMIN)
    alert = _alert(db)

    _client(sina).post("/api/alerts/%s/acknowledge" % alert.id, json={"verdict": "real"})
    _client(bryan).post("/api/alerts/%s/assign" % alert.id, json={"user_id": sina.id})
    _client(sina).post("/api/alerts/%s/resolve" % alert.id, json={"comment": "corrigé"})

    actions = _events(db, alert.id)
    assert "acknowledged" in actions
    assert "assigned" in actions
