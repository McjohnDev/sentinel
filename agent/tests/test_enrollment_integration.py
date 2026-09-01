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
from datetime import datetime, timedelta, timezone

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


# --------------------------------------------------- point 5 : battement


def _beat(session, creds, config, **kw):
    """Un battement complet contre la vraie route."""
    import heartbeat as hb
    from metrics import collect as collect_metrics

    payload = hb.build_payload(
        collect_metrics(), collect(AGENT_VERSION),
        taken_at=datetime.now(timezone.utc), **kw
    )
    return hb.send(config, creds, payload, session=session)


def test_a_heartbeat_is_accepted_by_the_real_route(db):
    """Le corps construit par l'agent satisfait-il reellement le schema ?"""
    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    result = _beat(session, creds, _config(""))

    # L'echo est le seul canal descendant : il doit revenir renseigne.
    assert result.echo.agent_id == creds.agent_id
    assert result.echo.server_time


def test_a_heartbeat_is_what_makes_the_host_stop_reading_offline(db):
    """La raison d'etre du point 5, verifiee de bout en bout."""
    from src.agent_purge import derived_agent_status

    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    # On force un silence prolonge : l'hote doit alors se lire hors ligne.
    # `enrolled_at` doit reculer aussi : is_agent_live accorde une grace de
    # deux minutes apres l'enrolement, quel que soit last_communication, pour
    # qu'un hote reenrole ne soit pas purge dans la seconde.
    stale = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    stale.last_communication = datetime.utcnow() - timedelta(days=2)
    stale.enrolled_at = datetime.utcnow() - timedelta(days=2)
    db.commit()
    db.expire_all()
    assert derived_agent_status(
        db.query(Agent).filter(Agent.id == creds.agent_id).first()
    ) != "active"

    _beat(session, creds, _config(""))

    db.expire_all()
    revived = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    assert derived_agent_status(revived) == "active"


def test_the_platform_reports_the_gap_after_an_outage(db):
    """« l'agent qui envoie a nouveau un heartbeat, la plateforme qui repond »."""
    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    _beat(session, creds, _config(""))

    db.expire_all()
    row = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    row.last_communication = datetime.utcnow() - timedelta(hours=3)
    db.commit()

    result = _beat(session, creds, _config(""))

    assert result.echo.resumed_after_outage is True
    assert result.echo.previous_gap_seconds is not None
    assert result.echo.previous_gap_seconds > 3000


def test_an_unknown_key_cannot_beat(db):
    from enrollment import Credentials
    import heartbeat as hb

    session = _ClientSession(TestClient(app))
    with pytest.raises(hb.HeartbeatRefused):
        _beat(session, Credentials("ZZZZZZ", "cle-inventee"), _config(""))


# --------------------------------------------------------------- VLAN


def test_an_observed_vlan_reaches_the_platform_at_enrolment(db, monkeypatch):
    import facts as facts_module

    monkeypatch.setattr(facts_module, "detect_vlan", lambda: "100,250")
    session = _ClientSession(TestClient(app))

    creds = enroll(
        _config(_issue_token(db)), load_or_create_machine_id(),
        facts_module.collect(AGENT_VERSION), session=session,
    )

    stored = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    assert stored.vlan_observed == "100,250"


def test_a_vlan_change_is_picked_up_by_the_next_beat(db, monkeypatch):
    """Un hote rebranche sur un autre port ne se reenrole pas : c'est le
    battement qui doit rapporter le nouveau VLAN."""
    import facts as facts_module
    import heartbeat as hb
    from metrics import collect as collect_metrics

    monkeypatch.setattr(facts_module, "detect_vlan", lambda: "100")
    session = _ClientSession(TestClient(app))
    creds = enroll(
        _config(_issue_token(db)), load_or_create_machine_id(),
        facts_module.collect(AGENT_VERSION), session=session,
    )
    assert db.query(Agent).filter(Agent.id == creds.agent_id).first().vlan_observed == "100"

    # L'hote change de port reseau.
    monkeypatch.setattr(facts_module, "detect_vlan", lambda: "250")
    payload = hb.build_payload(
        collect_metrics(), facts_module.collect(AGENT_VERSION),
        taken_at=datetime.now(timezone.utc),
    )
    hb.send(_config(""), creds, payload, session=session)

    db.expire_all()
    assert db.query(Agent).filter(Agent.id == creds.agent_id).first().vlan_observed == "250"


def test_an_untagged_host_leaves_the_observed_vlan_empty(db, monkeypatch):
    """La plupart des postes sont sur port d'acces : ils ne peuvent pas
    connaitre leur VLAN, et vide veut dire « non determinable »."""
    import facts as facts_module

    monkeypatch.setattr(facts_module, "detect_vlan", lambda: None)
    session = _ClientSession(TestClient(app))

    creds = enroll(
        _config(_issue_token(db)), load_or_create_machine_id(),
        facts_module.collect(AGENT_VERSION), session=session,
    )

    assert db.query(Agent).filter(Agent.id == creds.agent_id).first().vlan_observed is None


# ------------------------------------------- point 6 : plan de supervision


def test_a_plan_set_on_the_platform_reaches_the_agent_and_is_acknowledged(db):
    """Boucle complete du point 6 : la plateforme decide, l'agent recoit,
    range, acquitte — et la plateforme cesse de republier."""
    import plan as plan_module
    import heartbeat as hb
    from metrics import collect as collect_metrics
    from src import monitoring_plan

    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)
    row = db.query(Agent).filter(Agent.id == creds.agent_id).first()

    # L'exploitant pose un plan depuis l'interface.
    monitoring_plan.replace_plan(
        db, row,
        {
            "services": [{"name": "swift-alliance", "expected_state": "running"}],
            "files": [{"path": "/var/lock/cbc.flag", "condition": "must_not_exist"}],
        },
    )
    db.commit()

    def beat():
        payload = hb.build_payload(
            collect_metrics(), collect(AGENT_VERSION),
            taken_at=datetime.now(timezone.utc),
            config_version=plan_module.current_version(),
        )
        return hb.send(_config(""), creds, payload, session=session)

    first = beat()
    assert first.config is not None, "le plan doit descendre dans la reponse au battement"

    applied = plan_module.apply_offered(_config(""), creds, first.config, session=session)
    assert applied is not None
    assert plan_module.current_version() == applied

    # Le plan est range sur l'hote : services et fichiers demandes.
    stored = plan_module.read_plan().payload
    assert stored is not None

    # Acquitte : la plateforme ne le repousse plus.
    db.expire_all()
    second = beat()
    assert second.config is None, "un plan acquitte ne doit plus etre republie"


def test_an_unacknowledged_plan_keeps_being_offered(db):
    """Sans accuse, la plateforme republie indefiniment — c'est ce qui rend
    l'acquittement obligatoire et non optionnel."""
    import heartbeat as hb
    from metrics import collect as collect_metrics
    from src import monitoring_plan

    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)
    row = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    monitoring_plan.replace_plan(db, row, {"services": [{"name": "nginx"}]})
    db.commit()

    def beat():
        payload = hb.build_payload(
            collect_metrics(), collect(AGENT_VERSION), taken_at=datetime.now(timezone.utc)
        )
        return hb.send(_config(""), creds, payload, session=session)

    assert beat().config is not None
    db.expire_all()
    assert beat().config is not None, "sans accuse, le plan doit revenir"


# ------------------------------------------- point 7 : releves et inventaire


def test_the_agent_reports_what_the_plan_designates(db, tmp_path):
    """Boucle complete du point 7 : la plateforme designe, l'agent observe."""
    import collectors
    import heartbeat as hb
    from metrics import collect as collect_metrics
    from src import monitoring_plan
    from src.models import FileMonitoring, ServiceMonitoring

    present = tmp_path / "swift.log"
    present.write_text("x" * 42, encoding="utf-8")
    absent = tmp_path / "interdit.flag"

    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)
    row = db.query(Agent).filter(Agent.id == creds.agent_id).first()

    monitoring_plan.replace_plan(
        db, row,
        {
            "services": [{"name": "un-service-absent", "expected_state": "running"}],
            "files": [{"path": str(present)}, {"path": str(absent)}],
        },
    )
    db.commit()

    plan_payload = monitoring_plan.agent_config_payload(db, row)
    observations = collectors.observe(plan_payload)

    payload = hb.build_payload(
        collect_metrics(), collect(AGENT_VERSION),
        taken_at=datetime.now(timezone.utc), observations=observations,
    )
    hb.send(_config(""), creds, payload, session=session)

    db.expire_all()
    # Le fichier present et le fichier absent sont tous deux enregistres.
    states = {
        f.file_path: f.exists
        for f in db.query(FileMonitoring).filter(FileMonitoring.agent_id == creds.agent_id).all()
    }
    assert states.get(str(present)) is True
    assert states.get(str(absent)) is False

    # Le service introuvable est remonte, sans etre declare arrete.
    observed = {
        s.service_name: s.status
        for s in db.query(ServiceMonitoring).filter(ServiceMonitoring.agent_id == creds.agent_id).all()
    }
    assert observed.get("un-service-absent") == "unknown"


def test_the_inventory_reaches_the_platform_and_feeds_the_picker(db):
    """La plateforme doit pouvoir choisir parmi les services existants."""
    import inventory as inventory_module

    session = _ClientSession(TestClient(app))
    creds = enroll(_config(_issue_token(db)), load_or_create_machine_id(), collect(AGENT_VERSION), session=session)

    report = inventory_module.Inventory(
        services=[{"name": "swift-alliance", "display_name": "SWIFT Alliance", "status": "running"}],
        applications=[{"name": "Oracle Client", "version": "19.3"}],
        drivers=[{"name": "acpi", "state": "Running"}],
    )
    inventory_module.push(_config(""), creds, report, session=session)

    db.expire_all()
    stored = db.query(Agent).filter(Agent.id == creds.agent_id).first()
    assert stored.inventory_at is not None

    # Relu par l'interface : c'est ce qui alimente le selecteur de services.
    client = TestClient(app)
    from src.auth_service import AuthService
    from src.models import User, UserRole
    import uuid as _uuid

    admin = User(
        id=str(_uuid.uuid4()), username="adm-inv", email="adm-inv@cbcam.cm",
        password_hash="!x", role=UserRole.ADMIN, is_active=True,
    )
    db.add(admin)
    db.commit()
    token = AuthService.create_access_token(data={"sub": admin.id})

    response = client.get(
        "/api/agents/%s/inventory" % creds.agent_id,
        headers={"Authorization": "Bearer %s" % token},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["name"] for s in body["services"]] == ["swift-alliance"]
    assert body["applications"][0]["version"] == "19.3"
    assert body["drivers"][0]["state"] == "Running"


def test_an_unknown_key_cannot_push_an_inventory(db):
    import inventory as inventory_module
    from enrollment import Credentials

    session = _ClientSession(TestClient(app))
    with pytest.raises(inventory_module.InventoryPushFailed):
        inventory_module.push(
            _config(""), Credentials("ZZZZZZ", "cle-inventee"),
            inventory_module.Inventory(), session=session,
        )
