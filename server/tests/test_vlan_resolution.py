"""Du plan d'adressage au VLAN d'un hôte, par l'API.

`test_vlan_import.py` éprouve la lecture du fichier. Celui-ci éprouve ce à
quoi il sert : un fichier importé par l'équipe réseau doit donner un VLAN à
des hôtes qui n'ont jamais rien saisi, et ce VLAN doit suivre la machine
quand elle change d'adresse.
"""

from __future__ import annotations

import io
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
from src.models import Agent, MachineType, User, UserRole, VlanSubnet  # noqa: E402

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PLAN = (
    "Sous-réseau;VLAN;Libellé\n"
    "10.0.0.0/8;1;Global\n"
    "10.20.4.0/24;20;Monétique\n"
    "10.20.8.0/24;30;Agences\n"
).encode("utf-8")


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


def _user(db, username="admin", role=UserRole.ADMIN):
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


def _agent(db, agent_id="A3F09C", ip="10.20.4.17", vlan=None, vlan_observed=None):
    agent = Agent(
        id=agent_id,
        machine_id="mid-%s" % uuid.uuid4().hex[:8],
        hostname="SRV-%s" % agent_id,
        auth_key=str(uuid.uuid4()),
        status="active",
        os="linux",
        ip_address=ip,
        machine_type=MachineType.SERVER,
        vlan=vlan,
        vlan_observed=vlan_observed,
    )
    db.add(agent)
    db.commit()
    return agent


class _Client:
    def __init__(self, user):
        self.client = TestClient(app)
        token = AuthService.create_access_token(data={"sub": user.id})
        self.headers = {"Authorization": "Bearer %s" % token}

    def get(self, url):
        return self.client.get(url, headers=self.headers)

    def delete(self, url):
        return self.client.delete(url, headers=self.headers)

    def upload(self, content=PLAN, name="plan.csv"):
        return self.client.post(
            "/api/vlan-subnets/import",
            files={"file": (name, io.BytesIO(content), "text/csv")},
            headers=self.headers,
        )


def _detail(client, agent_id):
    response = client.get("/api/agents/%s" % agent_id)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------------------ import


def test_importing_the_plan_stores_the_subnets(db):
    client = _Client(_user(db))

    response = client.upload()

    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 3
    assert db.query(VlanSubnet).count() == 3


def test_a_second_import_replaces_rather_than_merges(db):
    # Un plan d'adressage est un document entier. Fusionner laisserait vivre
    # des sous-réseaux retirés du fichier, donc des hôtes rattachés à un VLAN
    # qui n'existe plus.
    client = _Client(_user(db))
    client.upload()

    client.upload(b"subnet;vlan\n10.90.0.0/16;90\n", "nouveau.csv")

    assert db.query(VlanSubnet).count() == 1
    assert db.query(VlanSubnet).first().cidr == "10.90.0.0/16"


def test_rejected_lines_come_back_to_the_caller(db):
    client = _Client(_user(db))

    response = client.upload(b"subnet;vlan\n10.20.4.0/24;20\nn-importe-quoi;30\n", "partiel.csv")

    body = response.json()
    assert body["imported"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["line"] == 3


def test_an_unusable_file_is_refused_outright(db):
    client = _Client(_user(db))
    response = client.upload(b"rien;du tout\n", "vide.csv")
    assert response.status_code == 400
    assert db.query(VlanSubnet).count() == 0


def test_an_operator_cannot_import_the_plan(db):
    client = _Client(_user(db, "sina", UserRole.OPERATOR))
    assert client.upload().status_code == 403


# -------------------------------------------------------------- déduction


def test_a_host_that_declared_nothing_gets_its_vlan_from_the_plan(db):
    """La raison d'être de l'import : couvrir le parc sans saisie par hôte."""
    client = _Client(_user(db))
    agent = _agent(db, ip="10.20.4.17")
    client.upload()

    body = _detail(client, agent.id)

    assert body["vlan_derived"] == "20"
    assert body["vlan_effective"] == "20"
    assert body["vlan_source"] == "derived"
    assert body["vlan_subnet"] == "10.20.4.0/24"
    assert body["vlan_label"] == "Monétique"


def test_the_most_specific_subnet_wins_over_the_site_range(db):
    # Le plan déclare un /8 et les /24 qui le découpent : rendre le /8
    # rattacherait tout le parc au mauvais VLAN.
    client = _Client(_user(db))
    agent = _agent(db, ip="10.20.8.9")
    client.upload()

    assert _detail(client, agent.id)["vlan_derived"] == "30"


def test_an_address_outside_the_plan_derives_nothing(db):
    client = _Client(_user(db))
    agent = _agent(db, ip="192.168.77.4")
    client.upload()

    body = _detail(client, agent.id)
    assert body["vlan_derived"] is None
    assert body["vlan_effective"] is None


def test_a_declared_vlan_outranks_the_plan(db):
    # La saisie sert justement à traiter l'exception que le plan ne décrit pas.
    client = _Client(_user(db))
    agent = _agent(db, ip="10.20.4.17", vlan="99")
    client.upload()

    body = _detail(client, agent.id)
    assert body["vlan_effective"] == "99"
    assert body["vlan_source"] == "declared"
    # Le déduit reste visible : l'écart est le fait intéressant.
    assert body["vlan_derived"] == "20"


def test_what_the_host_tags_is_used_when_nothing_else_answers(db):
    client = _Client(_user(db))
    agent = _agent(db, ip="192.168.77.4", vlan_observed="250")
    client.upload()

    body = _detail(client, agent.id)
    assert body["vlan_effective"] == "250"
    assert body["vlan_source"] == "observed"


def test_the_derivation_follows_a_host_that_changes_address(db):
    """Ce qu'une liste « hôte → VLAN » ne saurait pas faire."""
    client = _Client(_user(db))
    agent = _agent(db, ip="10.20.4.17")
    client.upload()
    assert _detail(client, agent.id)["vlan_derived"] == "20"

    # L'hôte est rebranché ailleurs ; son prochain battement remonte la
    # nouvelle adresse.
    agent.ip_address = "10.20.8.42"
    db.commit()

    assert _detail(client, agent.id)["vlan_derived"] == "30"


def test_clearing_the_plan_removes_the_derived_vlans(db):
    client = _Client(_user(db))
    agent = _agent(db, ip="10.20.4.17")
    client.upload()
    assert _detail(client, agent.id)["vlan_effective"] == "20"

    assert client.delete("/api/vlan-subnets").status_code == 200

    body = _detail(client, agent.id)
    assert body["vlan_derived"] is None
    assert body["vlan_effective"] is None


def test_the_fleet_list_carries_the_resolved_vlan(db):
    client = _Client(_user(db))
    _agent(db, ip="10.20.4.17")
    client.upload()

    response = client.get("/api/agents")
    assert response.status_code == 200
    rows = response.json()
    rows = rows.get("data", rows) if isinstance(rows, dict) else rows
    assert rows[0]["vlan_effective"] == "20"
    assert rows[0]["vlan_source"] == "derived"
