"""Champs constatés vs attribués, et cloisonnement des hôtes par responsable.

Deux règles de fond du lot A :

1. Ce que la machine déclare d'elle-même (nom machine, IP, OS, matériel) ne
   se corrige pas depuis l'interface. Un inventaire qui contredit la machine
   réelle est pire qu'un inventaire incomplet : la contradiction ne se
   découvre qu'au prochain incident.
2. Un hôte confié à quelqu'un n'est pas modifiable par tout le monde. Le rôle
   dit *ce que* l'on sait faire, la responsabilité dit *sur quoi*.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

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
    AGENT_EDITABLE_FIELDS,
    AGENT_IMMUTABLE_FIELDS,
    AdminGroup,
    AdminGroupMember,
    Agent,
    MachineType,
    User,
    UserRole,
)
from src.permissions import user_administers_agent  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _user(db, username, role=UserRole.OPERATOR):
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@cbcam.cm",
        password_hash="!x",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def _agent(db, agent_id="A3F09C", owner=None, group=None):
    agent = Agent(
        id=agent_id,
        machine_id=f"mid-{uuid.uuid4().hex[:8]}",
        hostname=f"SRV-{agent_id}",
        auth_key=str(uuid.uuid4()),
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
        owner_user_id=owner.id if owner else None,
        admin_group_id=group.id if group else None,
    )
    db.add(agent)
    db.commit()
    return agent


def _group(db, name="Équipe Monétique", members=()):
    group = AdminGroup(id=str(uuid.uuid4()), name=name)
    db.add(group)
    db.commit()
    for user in members:
        db.add(
            AdminGroupMember(id=str(uuid.uuid4()), group_id=group.id, user_id=user.id)
        )
    db.commit()
    return group


# ------------------------------------------- séparation constaté / attribué


def test_the_two_field_families_do_not_overlap():
    """Un champ ne peut pas être à la fois constaté et attribué."""
    assert not (AGENT_EDITABLE_FIELDS & AGENT_IMMUTABLE_FIELDS)


@pytest.mark.parametrize(
    "field",
    ["hostname", "ip_address", "os", "os_version", "agent_version", "machine_id", "id"],
)
def test_machine_declared_fields_are_locked(field):
    """Nom machine, réseau et système appartiennent à l'hôte, pas à l'IHM."""
    assert field in AGENT_IMMUTABLE_FIELDS
    assert field not in AGENT_EDITABLE_FIELDS


@pytest.mark.parametrize("field", ["name", "location", "owner_user_id", "admin_group_id"])
def test_operator_assigned_fields_are_editable(field):
    """Le nom d'hôte affiché, lui, est bien à la main de l'exploitation.

    C'est la distinction demandée : `hostname` (nom machine) est verrouillé,
    `name` (nom d'hôte) est modifiable.
    """
    assert field in AGENT_EDITABLE_FIELDS
    assert field not in AGENT_IMMUTABLE_FIELDS


def test_host_characteristics_are_locked():
    for field in ("cpu_cores", "ram_total_gb", "disk_total_gb"):
        assert field in AGENT_IMMUTABLE_FIELDS


# ------------------------------------------------------ portée par hôte


def test_global_admin_administers_everything(db):
    admin = _user(db, "admin", UserRole.ADMIN)
    assert user_administers_agent(db, admin, _agent(db)) is True


def test_named_owner_administers_their_host(db):
    owner = _user(db, "jdupont")
    assert user_administers_agent(db, owner, _agent(db, owner=owner)) is True


def test_group_member_administers_the_team_hosts(db):
    member = _user(db, "amballa")
    group = _group(db, members=[member])
    assert user_administers_agent(db, member, _agent(db, group=group)) is True


def test_outsider_is_refused_even_with_the_operator_role(db):
    """Un opérateur garde ses droits, mais plus sur les hôtes des autres."""
    owner = _user(db, "jdupont")
    outsider = _user(db, "autre", UserRole.OPERATOR)
    assert user_administers_agent(db, outsider, _agent(db, owner=owner)) is False


def test_leaving_the_team_removes_the_hold(db):
    member = _user(db, "parti")
    group = _group(db, members=[member])
    agent = _agent(db, group=group)
    assert user_administers_agent(db, member, agent) is True

    db.query(AdminGroupMember).filter(AdminGroupMember.user_id == member.id).delete()
    db.commit()
    db.expire_all()
    assert user_administers_agent(db, member, agent) is False


def test_unassigned_host_belongs_to_the_global_admin_only(db):
    """Un hôte sans responsable n'est pas « à tout le monde ».

    L'inverse ferait de l'oubli d'attribution une ouverture silencieuse : le
    jour où l'on enrôle un serveur sensible sans penser à le confier, il
    serait modifiable par n'importe quel opérateur.
    """
    orphan = _agent(db, "BBBBBB")
    assert user_administers_agent(db, _user(db, "quelconque"), orphan) is False
    assert user_administers_agent(db, _user(db, "chef", UserRole.ADMIN), orphan) is True


def test_membership_of_another_team_grants_nothing(db):
    member = _user(db, "reseau")
    _group(db, name="Équipe Réseau", members=[member])
    other_team_host = _agent(db, group=_group(db, name="Équipe Monétique"))
    assert user_administers_agent(db, member, other_team_host) is False
