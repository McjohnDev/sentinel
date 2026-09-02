"""A qui part une alerte.

Le destinataire principal ne se saisit pas : c'est le responsable de l'hote,
ou les membres de l'equipe responsable, dont l'adresse vient de l'annuaire.
Une liste tenue a la main divergerait le jour ou quelqu'un change de poste, et
les alertes continueraient de partir vers une personne qui n'a plus la machine
en charge.

La copie, elle, ne se deduit de rien -- un prestataire, le metier proprietaire
de l'application -- et se saisit hote par hote.
"""

from __future__ import annotations

import json
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
from src.messaging_service import MessagingService  # noqa: E402
from src.models import (  # noqa: E402
    Agent,
    AdminGroup,
    AdminGroupMember,
    MachineType,
    MessagingConfig,
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


def _user(db, email, *, active=True, role=UserRole.OPERATOR):
    user = User(
        id=str(uuid.uuid4()), username="u-%s" % uuid.uuid4().hex[:6], email=email,
        password_hash="!x", role=role, is_active=active,
    )
    db.add(user)
    db.commit()
    return user


def _agent(db, agent_id="A1B2C3", **kw):
    agent = Agent(
        id=agent_id, machine_id="mid-%s" % uuid.uuid4().hex[:6], hostname="SRV-%s" % agent_id,
        auth_key=str(uuid.uuid4()), status="active", os="linux",
        machine_type=MachineType.SERVER, **kw,
    )
    db.add(agent)
    db.commit()
    return agent


def _team(db, name, members):
    group = AdminGroup(id=str(uuid.uuid4()), name=name)
    db.add(group)
    db.commit()
    for member in members:
        db.add(AdminGroupMember(id=str(uuid.uuid4()), group_id=group.id, user_id=member.id))
    db.commit()
    return group


def _fallback(db, addresses):
    db.add(MessagingConfig(id="default", recipients=json.dumps(addresses)))
    db.commit()


def _client(db, role=UserRole.ADMIN):
    user = _user(db, "adm@cbcam.cm", role=role)
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client


def _resolve(db, agent):
    return MessagingService.resolve_recipients_for_agent(db, agent)


# ------------------------------------------------------ le destinataire principal


def test_the_host_owner_receives_the_alert(db):
    owner = _user(db, "alain.kengne@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id)

    assert _resolve(db, agent)["to"] == ["alain.kengne@cbcam.cm"]


def test_every_member_of_the_responsible_team_receives_it(db):
    """Un hote confie a une equipe n'alertait personne : seul le proprietaire
    etait consulte, et l'attribution a une equipe restait sans effet."""
    a = _user(db, "a@cbcam.cm")
    b = _user(db, "b@cbcam.cm")
    team = _team(db, "Exploitation", [a, b])
    agent = _agent(db, admin_group_id=team.id)

    assert sorted(_resolve(db, agent)["to"]) == ["a@cbcam.cm", "b@cbcam.cm"]


def test_owner_and_team_are_cumulative(db):
    owner = _user(db, "chef@cbcam.cm")
    member = _user(db, "equipe@cbcam.cm")
    team = _team(db, "Reseau", [member])
    agent = _agent(db, owner_user_id=owner.id, admin_group_id=team.id)

    assert sorted(_resolve(db, agent)["to"]) == ["chef@cbcam.cm", "equipe@cbcam.cm"]


def test_a_deactivated_owner_is_not_written_to(db):
    """Son adresse est souvent fermee avec le compte : l'alerte se perdrait."""
    owner = _user(db, "parti@cbcam.cm", active=False)
    agent = _agent(db, owner_user_id=owner.id)

    assert "parti@cbcam.cm" not in _resolve(db, agent)["to"]


def test_a_deactivated_team_member_is_skipped(db):
    present = _user(db, "present@cbcam.cm")
    gone = _user(db, "parti@cbcam.cm", active=False)
    team = _team(db, "Systeme", [present, gone])
    agent = _agent(db, admin_group_id=team.id)

    assert _resolve(db, agent)["to"] == ["present@cbcam.cm"]


def test_an_owner_without_an_email_does_not_produce_an_empty_recipient(db):
    """Un annuaire sans attribut `mail` rend une chaine vide, pas `null`
    (`LdapService._entry_value`). L'ajouter telle quelle ferait rejeter le
    message entier par le relais."""
    owner = _user(db, "")
    agent = _agent(db, owner_user_id=owner.id)

    assert _resolve(db, agent)["to"] == []


def test_the_same_person_is_not_written_to_twice(db):
    owner = _user(db, "double@cbcam.cm")
    team = _team(db, "Doublon", [owner])
    agent = _agent(db, owner_user_id=owner.id, admin_group_id=team.id)

    assert _resolve(db, agent)["to"] == ["double@cbcam.cm"]


# ---------------------------------------------------------------- la copie


def test_the_manual_cc_of_the_host_is_used(db):
    owner = _user(db, "resp@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id, alert_cc=json.dumps(["prestataire@ext.cm"]))

    resolved = _resolve(db, agent)

    assert resolved["to"] == ["resp@cbcam.cm"]
    assert resolved["cc"] == ["prestataire@ext.cm"]


def test_the_cc_is_specific_to_each_host(db):
    owner = _user(db, "resp@cbcam.cm")
    swift = _agent(db, "SWIFT1", owner_user_id=owner.id, alert_cc=json.dumps(["swift@cbcam.cm"]))
    poste = _agent(db, "POSTE1", owner_user_id=owner.id, alert_cc=json.dumps(["bureau@cbcam.cm"]))

    assert _resolve(db, swift)["cc"] == ["swift@cbcam.cm"]
    assert _resolve(db, poste)["cc"] == ["bureau@cbcam.cm"]


def test_someone_already_a_main_recipient_is_not_also_copied(db):
    """Sinon le meme lecteur recoit deux exemplaires et doute d'en manquer un."""
    owner = _user(db, "resp@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id, alert_cc=json.dumps(["resp@cbcam.cm"]))

    assert _resolve(db, agent)["cc"] == []


def test_a_broken_cc_column_does_not_break_the_notification(db):
    owner = _user(db, "resp@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id, alert_cc="{ceci n'est pas du json")

    assert _resolve(db, agent) == {"to": ["resp@cbcam.cm"], "cc": []}


# ------------------------------------------------------------------- le filet


def test_a_host_without_anyone_falls_back_to_the_global_list(db):
    """Une machine oubliee lors de l'attribution alerterait sinon dans le vide."""
    _fallback(db, ["supervision@cbcam.cm"])
    agent = _agent(db)

    assert _resolve(db, agent)["to"] == ["supervision@cbcam.cm"]


def test_the_global_list_does_not_override_a_responsible(db):
    _fallback(db, ["supervision@cbcam.cm"])
    owner = _user(db, "resp@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id)

    assert _resolve(db, agent)["to"] == ["resp@cbcam.cm"]


def test_a_host_with_nobody_and_no_fallback_notifies_no_one(db):
    assert _resolve(db, _agent(db)) == {"to": [], "cc": []}


# ---------------------------------------------------------------------- l'API


def test_the_cc_is_saved_on_the_host(db):
    client = _client(db)
    _agent(db)

    response = client.patch("/api/agents/A1B2C3", json={"alert_cc": ["metier@cbcam.cm"]})

    assert response.status_code == 200, response.text
    db.expire_all()
    stored = db.query(Agent).filter(Agent.id == "A1B2C3").first()
    assert MessagingService.parse_alert_cc(stored.alert_cc) == ["metier@cbcam.cm"]


def test_a_malformed_address_is_refused_rather_than_stored(db):
    """Le relais rejette le message entier : l'alerte se perdrait avec l'adresse."""
    client = _client(db)
    _agent(db)

    response = client.patch("/api/agents/A1B2C3", json={"alert_cc": ["pas-une-adresse"]})

    assert response.status_code == 400
    assert "pas-une-adresse" in response.json()["detail"]


def test_the_cc_can_be_emptied(db):
    client = _client(db)
    _agent(db, alert_cc=json.dumps(["x@cbcam.cm"]))

    client.patch("/api/agents/A1B2C3", json={"alert_cc": []})

    db.expire_all()
    assert MessagingService.parse_alert_cc(
        db.query(Agent).filter(Agent.id == "A1B2C3").first().alert_cc
    ) == []


def test_the_host_sheet_shows_who_will_actually_be_notified(db):
    """Un ecran qui affiche « responsable : aucun » laisse deviner la
    consequence. Celui-ci la montre."""
    client = _client(db)
    owner = _user(db, "resp@cbcam.cm")
    _agent(db, owner_user_id=owner.id, alert_cc=json.dumps(["copie@cbcam.cm"]))

    body = client.get("/api/agents/A1B2C3").json()

    assert body["alert_recipients"]["to"] == ["resp@cbcam.cm"]
    assert body["alert_recipients"]["cc"] == ["copie@cbcam.cm"]
    assert body["alert_cc"] == ["copie@cbcam.cm"]


def test_the_sheet_of_an_unassigned_host_shows_an_empty_recipient_list(db):
    client = _client(db)
    _agent(db)

    assert client.get("/api/agents/A1B2C3").json()["alert_recipients"]["to"] == []


# ---------------------------------------------- ce qui part reellement au relais


def test_the_alert_is_addressed_to_the_owner_and_copies_the_host_list(db, monkeypatch):
    owner = _user(db, "resp@cbcam.cm")
    agent = _agent(db, owner_user_id=owner.id, alert_cc=json.dumps(["copie@cbcam.cm"]))
    db.add(MessagingConfig(
        id="default", smtp_enabled=True, smtp_host="smtp.local", smtp_port=25,
        smtp_auth=False, smtp_encryption="none", smtp_from="sentinel@cbcam.cm",
        recipients="[]",
    ))
    db.commit()

    captured = {}

    def _capture(db_, *, to, subject, body_html):
        captured["to"] = to
        return True

    monkeypatch.setattr(MessagingService, "_send_via_smtp", staticmethod(_capture))

    delivered = MessagingService.send_alert_notification(
        alert_type="cpu_high", severity="major", message="CPU",
        hostname=agent.hostname, db=db, agent=agent,
    )

    assert delivered is True
    assert captured["to"] == ["resp@cbcam.cm", "copie@cbcam.cm"]


def test_a_host_with_no_one_responsible_sends_nothing(db):
    """L'echec se produit avant le relais : ce n'est pas une panne d'envoi."""
    agent = _agent(db)
    db.add(MessagingConfig(
        id="default", smtp_enabled=True, smtp_host="smtp.local", smtp_port=25,
        smtp_auth=False, smtp_encryption="none", smtp_from="sentinel@cbcam.cm",
        recipients="[]",
    ))
    db.commit()

    assert MessagingService.send_alert_notification(
        alert_type="cpu_high", severity="major", message="CPU",
        hostname=agent.hostname, db=db, agent=agent,
    ) is False
