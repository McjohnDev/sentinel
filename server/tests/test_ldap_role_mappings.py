"""Attribution de rôles à portée applicative (API-003).

Le rôle Sentinel d'un compte d'annuaire est décidé **dans cette base**, pas
dans l'annuaire : CBC n'a aucun groupe à créer côté Active Directory et le
compte de service reste en lecture seule.

Ordre de résolution vérifié ici : mappings en base -> configuration
d'environnement -> rôle par défaut (le moins privilégié).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database import Base
from src.ldap_service import LdapService
from src.models import LdapRoleMapping, UserRole

# Groupes réellement observés sur le domaine gie.local.
G_ADMINS = "CN=Admins_local_CBC,OU=GROUPES,OU=CBC,DC=gie,DC=local"
G_DTDSI = "CN=cbc_dtdsi,CN=Users,DC=gie,DC=local"
G_DEV = "CN=CBC_Developpeurs,CN=Users,DC=gie,DC=local"


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


def _map(db, kind, value, role, priority=100, enabled=True):
    row = LdapRoleMapping(
        id=str(uuid.uuid4()),
        kind=kind,
        value=value,
        role=role,
        priority=priority,
        enabled=enabled,
        created_by="admin",
    )
    db.add(row)
    db.commit()
    return row


def test_no_mapping_yields_least_privilege(db):
    """Sans correspondance, aucun droit n'est accordé — y compris à un membre
    d'un groupe d'administration du domaine."""
    assert LdapService.resolve_role([G_ADMINS], username="jkoum", db=db) == UserRole.READ_ONLY


def test_group_mapping_grants_the_role(db):
    _map(db, "group", G_DTDSI, UserRole.OPERATOR)
    assert LdapService.resolve_role([G_DTDSI], username="jkoum", db=db) == UserRole.OPERATOR


def test_group_matching_is_case_insensitive(db):
    """Les annuaires ne sont pas cohérents sur la casse des DN."""
    _map(db, "group", G_DTDSI.upper(), UserRole.OPERATOR)
    assert LdapService.resolve_role([G_DTDSI.lower()], username="x", db=db) == UserRole.OPERATOR


def test_user_mapping_bootstraps_an_administrator(db):
    """Permet de désigner un administrateur avant qu'un groupe dédié existe."""
    _map(db, "user", "jkoum", UserRole.ADMIN)
    assert LdapService.resolve_role([], username="jkoum", db=db) == UserRole.ADMIN
    # …sans affecter les autres comptes.
    assert LdapService.resolve_role([], username="lkengne", db=db) == UserRole.READ_ONLY


def test_priority_decides_between_two_groups(db):
    """Une double appartenance ne doit pas dépendre de l'ordre de lecture
    de l'annuaire."""
    _map(db, "group", G_ADMINS, UserRole.ADMIN, priority=10)
    _map(db, "group", G_DEV, UserRole.READ_ONLY, priority=50)

    assert LdapService.resolve_role([G_DEV, G_ADMINS], username="x", db=db) == UserRole.ADMIN
    # Ordre inverse : même résultat.
    assert LdapService.resolve_role([G_ADMINS, G_DEV], username="x", db=db) == UserRole.ADMIN


def test_named_exception_wins_over_group_at_equal_priority(db):
    """À priorité égale, une attribution nominative prime — c'est le sens
    d'une exception."""
    _map(db, "group", G_DTDSI, UserRole.OPERATOR, priority=100)
    _map(db, "user", "jkoum", UserRole.SECURITY, priority=100)

    assert LdapService.resolve_role([G_DTDSI], username="jkoum", db=db) == UserRole.SECURITY
    assert LdapService.resolve_role([G_DTDSI], username="autre", db=db) == UserRole.OPERATOR


def test_disabled_mapping_is_ignored(db):
    _map(db, "group", G_ADMINS, UserRole.ADMIN, enabled=False)
    assert LdapService.resolve_role([G_ADMINS], username="x", db=db) == UserRole.READ_ONLY


def test_db_mapping_overrides_environment(db, monkeypatch):
    """La base fait autorité : la variable d'environnement ne sert qu'à
    amorcer un déploiement."""
    monkeypatch.setattr(settings, "ldap_role_mapping", '{"%s": "read_only"}' % G_DTDSI)
    _map(db, "group", G_DTDSI, UserRole.OPERATOR)
    assert LdapService.resolve_role([G_DTDSI], username="x", db=db) == UserRole.OPERATOR


def test_environment_mapping_still_applies_without_db_rows(db, monkeypatch):
    monkeypatch.setattr(settings, "ldap_role_mapping", '{"%s": "operator"}' % G_DTDSI)
    assert LdapService.resolve_role([G_DTDSI], username="x", db=db) == UserRole.OPERATOR


def test_resolution_never_escalates_on_database_error(monkeypatch):
    """Une base injoignable ne doit pas élever les droits."""

    class Broken:
        def query(self, *_a, **_k):
            raise RuntimeError("base indisponible")

    monkeypatch.setattr(settings, "ldap_role_mapping", "{}")
    assert LdapService.resolve_role([G_ADMINS], username="jkoum", db=Broken()) == UserRole.READ_ONLY


def test_works_without_a_session(db):
    """Les appels historiques sans session restent valides."""
    assert LdapService.resolve_role([G_ADMINS], username="jkoum") == UserRole.READ_ONLY
