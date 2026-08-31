"""Qui décide des droits : l'annuaire ou l'application ?

Décision de conception : **l'application**. L'annuaire répond à « qui
êtes-vous » ; les rôles se gèrent dans l'écran Utilisateurs.

Le comportement précédent réalignait le rôle sur l'annuaire à chaque
connexion. Conséquence concrète : un administrateur promouvait quelqu'un,
l'intéressé se reconnectait, et retrouvait ses droits d'origine — sans
message, sans trace visible. L'écran Utilisateurs paraissait fonctionner
alors qu'il était sans effet durable sur les comptes d'annuaire.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.auth_service import AuthService  # noqa: E402
from src.database import Base  # noqa: E402
from src.models import AuthSource, User, UserRole  # noqa: E402


@dataclass
class FakeProfile:
    """Profil tel que `LdapService.find_user` le renvoie."""

    username: str
    dn: str
    email: str
    role: UserRole
    groups: List[str] = field(default_factory=list)
    display_name: str = ""
    attributes: dict = field(default_factory=dict)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _profile(role=UserRole.READ_ONLY, username="jdupont"):
    return FakeProfile(
        username=username,
        dn=f"CN={username},OU=Utilisateurs,DC=gie,DC=local",
        email=f"{username}@groupecommercialbank.com",
        role=role,
    )


# ------------------------------------------------------- premier provisionnement


def test_first_login_seeds_the_role_from_the_directory(db):
    """À la création, l'annuaire fournit le rôle de départ."""
    user = AuthService.sync_ldap_user(db, _profile(role=UserRole.READ_ONLY))
    assert user.role == UserRole.READ_ONLY
    assert user.auth_source == AuthSource.LDAP
    assert user.external_id.startswith("CN=jdupont")


def test_directory_mapping_seeds_a_privileged_account(db):
    """Une correspondance d'annuaire peut amorcer un administrateur."""
    user = AuthService.sync_ldap_user(db, _profile(role=UserRole.ADMIN))
    assert user.role == UserRole.ADMIN


# ------------------------------------------- le rôle applicatif fait ensuite foi


def test_role_set_in_the_application_survives_reconnection(db):
    """Le cœur du sujet : une promotion doit tenir.

    Auparavant la reconnexion la remettait à `read_only` — l'utilisateur
    « n'arrivait pas à modifier la configuration » sans qu'aucun message
    n'explique pourquoi.
    """
    AuthService.sync_ldap_user(db, _profile(role=UserRole.READ_ONLY))

    promoted = db.query(User).filter(User.username == "jdupont").first()
    promoted.role = UserRole.ADMIN
    db.commit()

    # L'annuaire continue de proposer read_only : il ne doit plus l'imposer.
    AuthService.sync_ldap_user(db, _profile(role=UserRole.READ_ONLY))

    db.expire_all()
    assert db.query(User).filter(User.username == "jdupont").first().role == UserRole.ADMIN


def test_demotion_in_the_application_also_survives(db):
    """La règle vaut dans les deux sens, sinon elle n'est pas une règle."""
    AuthService.sync_ldap_user(db, _profile(role=UserRole.ADMIN))

    demoted = db.query(User).filter(User.username == "jdupont").first()
    demoted.role = UserRole.READ_ONLY
    db.commit()

    AuthService.sync_ldap_user(db, _profile(role=UserRole.ADMIN))

    db.expire_all()
    assert db.query(User).filter(User.username == "jdupont").first().role == UserRole.READ_ONLY


def test_repeated_logins_do_not_drift(db):
    AuthService.sync_ldap_user(db, _profile(role=UserRole.READ_ONLY))
    user = db.query(User).filter(User.username == "jdupont").first()
    user.role = UserRole.OPERATOR
    db.commit()

    for _ in range(5):
        AuthService.sync_ldap_user(db, _profile(role=UserRole.READ_ONLY))

    db.expire_all()
    assert db.query(User).filter(User.username == "jdupont").first().role == UserRole.OPERATOR


def test_deactivation_in_the_application_is_not_undone_by_a_login(db):
    """Même principe pour l'activation : c'est une décision applicative.

    Réactiver ici un compte désactivé par un administrateur viderait la
    désactivation de son sens — il suffirait de se reconnecter.
    """
    AuthService.sync_ldap_user(db, _profile(role=UserRole.OPERATOR))
    user = db.query(User).filter(User.username == "jdupont").first()
    user.is_active = False
    db.commit()

    AuthService.sync_ldap_user(db, _profile(role=UserRole.OPERATOR))

    db.expire_all()
    assert db.query(User).filter(User.username == "jdupont").first().is_active is False


# ------------------------------------------- ce que l'annuaire gouverne encore


def test_identity_facts_still_follow_the_directory(db):
    """Adresse et DN appartiennent à l'annuaire, pas à l'application."""
    AuthService.sync_ldap_user(db, _profile())

    renamed = _profile()
    renamed.email = "jean.dupont@groupecommercialbank.com"
    renamed.dn = "CN=jdupont,OU=Direction,DC=gie,DC=local"
    AuthService.sync_ldap_user(db, renamed)

    db.expire_all()
    user = db.query(User).filter(User.username == "jdupont").first()
    assert user.email == "jean.dupont@groupecommercialbank.com"
    assert "OU=Direction" in user.external_id


def test_account_is_matched_by_dn_across_a_rename(db):
    """Le DN est l'identifiant stable : un renommage ne doit pas créer un doublon."""
    first = AuthService.sync_ldap_user(db, _profile())
    dn = first.dn if hasattr(first, "dn") else first.external_id

    renamed = _profile(username="jdupont2")
    renamed.dn = dn
    AuthService.sync_ldap_user(db, renamed)

    assert db.query(User).count() == 1
