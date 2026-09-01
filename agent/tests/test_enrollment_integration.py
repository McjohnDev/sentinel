"""Enrôlement de bout en bout, contre la vraie route de la plateforme.

Les tests unitaires d'enrôlement travaillent sur une session HTTP factice :
ils vérifient que l'agent se comporte bien face à des réponses *supposées*.
Celui-ci enrôle contre `POST /api/agents/enroll` réellement montée, ce qui est
le seul moyen de prouver que la charge utile construite par l'agent satisfait
les contraintes de la plateforme — et que l'identifiant reçu est bien le code
à 6 caractères hexadécimaux attendu au point 2.

C'est ce test qui échouerait si les deux moitiés dérivaient l'une de l'autre.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

pytest.importorskip("fastapi", reason="dépendances serveur absentes")

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for candidate in (str(ROOT), str(ROOT / "server")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import os  # noqa: E402

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_DISABLED", "true")
os.environ["LDAP_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402
from src.models import Agent, EnrollmentToken  # noqa: E402

from config import AgentConfig  # noqa: E402
from enrollment import (  # noqa: E402
    AGENT_VERSION,
    EnrollmentError,
    clear_credentials,
    deregister,
    enroll,
    read_credentials,
)
from facts import collect  # noqa: E402
from identity import load_or_create_machine_id  # noqa: E402

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


def _issue_token(db, value="jeton-integration-001"):
    db.add(
        EnrollmentToken(
            id=str(uuid.uuid4()),
            token=value,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            status="active",
        )
    )
    db.commit()
    return value


class _ClientSession:
    """Adapte TestClient à l'interface de session attendue par l'agent.

    TestClient ne connaît ni `verify` ni les URL absolues : on retient le
    drapeau pour l'assertion et on ne transmet que le chemin.
    """

    def __init__(self, client):
        self.client = client
        self.verify_seen = None

    def post(self, url, json=None, timeout=None, verify=None, headers=None):
        self.verify_seen = verify
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        return self.client.post("/" + path, json=json, headers=headers or {})


def _config(token):
    return AgentConfig(
        server_url="http://testserver",
        enrollment_token=token,
        tls_verify=False,
        machine_type="server",
        timeout_seconds=5,
    )


def test_agent_enrols_against_the_real_endpoint(db):
    token = _issue_token(db)
    session = _ClientSession(TestClient(app))

    creds = enroll(_config(token), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    # L'identifiant vient de la plateforme, au format du point 2.
    assert len(creds.agent_id) == 6
    assert all(c in "0123456789ABCDEF" for c in creds.agent_id)
    assert creds.auth_key

    stored = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    assert stored is not None
    assert stored.status == "active"
    # Relu depuis le disque de l'hôte : le prochain démarrage saura qui il est.
    assert read_credentials().agent_id == creds.agent_id


def test_the_same_host_does_not_become_two_entries(db):
    token_a = _issue_token(db, "jeton-integration-a")
    token_b = _issue_token(db, "jeton-integration-b")
    session = _ClientSession(TestClient(app))
    machine = load_or_create_machine_id()
    host = collect(AGENT_VERSION)

    first = enroll(_config(token_a), machine, host, session=session)
    second = enroll(_config(token_b), machine, host, session=session)

    # Réenrôler la même machine la met à jour : c'est la reprise après
    # réinstallation, pas un nouvel hôte.
    assert first.agent_id == second.agent_id
    assert db.query(Agent).count() == 1


def test_a_used_token_is_refused_the_second_time(db):
    token = _issue_token(db)
    session = _ClientSession(TestClient(app))
    host = collect(AGENT_VERSION)

    enroll(_config(token), load_or_create_machine_id(), host, session=session)

    with pytest.raises(EnrollmentError) as exc:
        enroll(_config(token), str(uuid.uuid4()), host, session=session)
    assert "utilis" in str(exc.value).lower()
    assert db.query(Agent).count() == 1


def test_an_unknown_token_enrols_nothing(db):
    session = _ClientSession(TestClient(app))

    with pytest.raises(EnrollmentError):
        enroll(_config("jeton-jamais-emis-000"), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    assert db.query(Agent).count() == 0
    assert read_credentials() is None


def test_uninstall_marks_the_host_without_deleting_it(db):
    """Point 4 : le desenrolement marque, il n'efface pas."""
    token = _issue_token(db)
    session = _ClientSession(TestClient(app))
    creds = enroll(_config(token), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    deregister(_config(""), creds, reason="poste reforme", session=session)

    stored = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    # La ligne survit : sans elle on perdrait l'historique au moment precis ou
    # l'on veut savoir depuis quand l'hote n'est plus supervise.
    assert stored is not None
    assert stored.uninstalled_at is not None
    assert stored.uninstalled_by == "agent"


def test_reinstalling_recovers_the_same_host(db):
    """La promesse affichee par la CLI a la desinstallation."""
    session = _ClientSession(TestClient(app))
    machine = load_or_create_machine_id()
    host = collect(AGENT_VERSION)

    first = enroll(_config(_issue_token(db, "jeton-cycle-un")), machine, host, session=session)
    deregister(_config(""), first, reason="remplacement disque", session=session)
    clear_credentials()

    second = enroll(_config(_issue_token(db, "jeton-cycle-deux")), machine, host, session=session)

    assert second.agent_id == first.agent_id, "une reinstallation ne doit pas creer un second hote"
    assert db.query(Agent).count() == 1
    stored = db.query(Agent).filter(Agent.id == second.agent_id).first()
    # La marque de desinstallation est levee : l'hote est de nouveau supervise.
    assert stored.uninstalled_at is None
    assert stored.status == "active"


def test_deregistration_without_credentials_is_refused(db):
    session = _ClientSession(TestClient(app))
    from enrollment import Credentials, DeregistrationError

    with pytest.raises(DeregistrationError):
        deregister(_config(""), Credentials("ZZZZZZ", "cle-inventee"), session=session)
