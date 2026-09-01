"""Attribution d'un hôte à un responsable ou à une équipe (point 3).

`test_agent_fields_and_scope.py` vérifie la *règle* : qui administre un hôte
selon ce qui est posé dessus. Ce module vérifie le *chemin d'attribution* —
`PATCH /api/agents/{id}` — c'est-à-dire ce qui se passe réellement quand un
administrateur confie une machine à quelqu'un depuis l'interface.

La distinction compte : jusqu'ici les tests posaient `owner_user_id` à la main
sur le modèle. Rien ne prouvait que l'API sache l'écrire, ni qu'elle refuse un
responsable inexistant, ni qu'une attribution donne effectivement la main à
son destinataire.
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

from src.database import Base, get_db  # noqa: E402
from src.auth_service import AuthService  # noqa: E402
from src.main import app  # noqa: E402
from src.models import (  # noqa: E402
    AdminGroup,
    AdminGroupMember,
    Agent,
    MachineType,
    User,
    UserRole,
)
from src.permissions import user_administers_agent  # noqa: E402

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


def _user(db, username, role=UserRole.OPERATOR):
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email="%s@cbcam.cm" % username,
        password_hash="!x",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _agent(db, agent_id="A3F09C"):
    agent = Agent(
        id=agent_id,
        machine_id="mid-%s" % uuid.uuid4().hex[:8],
        hostname="SRV-%s" % agent_id,
        auth_key=str(uuid.uuid4()),
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.commit()
    return agent


def _group(db, name="Équipe Monétique", members=()):
    group = AdminGroup(id=str(uuid.uuid4()), name=name)
    db.add(group)
    db.commit()
    for user in members:
        db.add(AdminGroupMember(id=str(uuid.uuid4()), group_id=group.id, user_id=user.id))
    db.commit()
    return group


class _AuthedClient:
    """Client authentifie comme `user`, par un vrai jeton.

    `require_auth()` construit une fermeture a chaque appel : elle n'est donc
    pas surchargeable par identite via `dependency_overrides`. On emet un
    jeton reel, ce qui a l'avantage de faire passer les tests par le meme
    chemin d'authentification que la production.
    """

    def __init__(self, user):
        self.client = TestClient(app)
        token = AuthService.create_access_token(data={"sub": user.id})
        self.headers = {"Authorization": "Bearer %s" % token}

    def patch(self, url, json=None):
        return self.client.patch(url, json=json, headers=self.headers)


def _as(user):
    return _AuthedClient(user)


def _reload(db, agent_id):
    db.expire_all()
    return db.query(Agent).filter(Agent.id == agent_id).first()


def test_naming_a_responsible_gives_them_the_host(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    operator = _user(db, "sina")
    agent = _agent(db)

    assert not user_administers_agent(db, operator, agent)

    response = _as(admin).patch("/api/agents/%s" % agent.id, json={"owner_user_id": operator.id})

    assert response.status_code == 200
    stored = _reload(db, agent.id)
    assert stored.owner_user_id == operator.id
    # Le point de l'attribution : le destinataire peut désormais intervenir.
    assert user_administers_agent(db, operator, stored)


def test_assigning_a_team_gives_the_host_to_its_members(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    member = _user(db, "membre")
    outsider = _user(db, "autre")
    group = _group(db, members=[member])
    agent = _agent(db)

    response = _as(admin).patch("/api/agents/%s" % agent.id, json={"admin_group_id": group.id})

    assert response.status_code == 200
    stored = _reload(db, agent.id)
    assert user_administers_agent(db, member, stored)
    assert not user_administers_agent(db, outsider, stored)


def test_a_host_may_carry_both_a_responsible_and_a_team(db):
    # Le serveur traite les deux voies en union (user_administers_agent) :
    # l'interface doit pouvoir les poser ensemble, sinon elle décrirait
    # faussement qui a la main.
    admin = _user(db, "admin", UserRole.ADMIN)
    owner = _user(db, "responsable")
    member = _user(db, "membre")
    group = _group(db, members=[member])
    agent = _agent(db)

    response = _as(admin).patch(
        "/api/agents/%s" % agent.id,
        json={"owner_user_id": owner.id, "admin_group_id": group.id},
    )

    assert response.status_code == 200
    stored = _reload(db, agent.id)
    assert user_administers_agent(db, owner, stored)
    assert user_administers_agent(db, member, stored)


def test_clearing_the_assignment_returns_the_host_to_global_admins(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    operator = _user(db, "sina")
    agent = _agent(db)

    client = _as(admin)
    client.patch("/api/agents/%s" % agent.id, json={"owner_user_id": operator.id})
    response = client.patch(
        "/api/agents/%s" % agent.id,
        json={"owner_user_id": None, "admin_group_id": None},
    )

    assert response.status_code == 200
    stored = _reload(db, agent.id)
    assert stored.owner_user_id is None
    # Un hôte sans attribution n'est pas « à tout le monde ».
    assert not user_administers_agent(db, operator, stored)
    assert user_administers_agent(db, admin, stored)


def test_an_unknown_responsible_is_refused(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    agent = _agent(db)

    response = _as(admin).patch(
        "/api/agents/%s" % agent.id, json={"owner_user_id": str(uuid.uuid4())}
    )

    assert response.status_code == 400
    assert "esponsable" in response.json()["detail"]
    assert _reload(db, agent.id).owner_user_id is None


def test_an_unknown_team_is_refused(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    agent = _agent(db)

    response = _as(admin).patch(
        "/api/agents/%s" % agent.id, json={"admin_group_id": str(uuid.uuid4())}
    )

    assert response.status_code == 400
    assert _reload(db, agent.id).admin_group_id is None


def test_an_operator_outside_the_perimeter_cannot_reassign_the_host(db):
    # Sans quoi n'importe quel opérateur pourrait s'attribuer une machine
    # dont il n'a pas la charge.
    _user(db, "admin", UserRole.ADMIN)
    owner = _user(db, "responsable")
    intruder = _user(db, "intrus")
    agent = _agent(db)
    agent.owner_user_id = owner.id
    db.commit()

    response = _as(intruder).patch(
        "/api/agents/%s" % agent.id, json={"owner_user_id": intruder.id}
    )

    assert response.status_code == 403
    assert _reload(db, agent.id).owner_user_id == owner.id


def test_an_observed_field_is_refused_by_name(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    agent = _agent(db)

    response = _as(admin).patch("/api/agents/%s" % agent.id, json={"hostname": "renomme"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    # Nommer le champ : « non modifiable » sans précision laisse deviner.
    assert detail["fields"] == ["hostname"]
    assert _reload(db, agent.id).hostname.startswith("SRV-")
