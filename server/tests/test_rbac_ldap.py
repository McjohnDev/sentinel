"""RBAC déclaratif et authentification annuaire (DSH-025, API-003).

Couvre :
  * la matrice rôle -> permissions, y compris le nouveau rôle sécurité ;
  * les garde-fous de gestion de comptes (dernier administrateur, auto-
    rétrogradation, comptes d'annuaire) ;
  * l'échappement des filtres LDAP et la résolution de rôle par groupe ;
  * le provisionnement et le réalignement d'un compte d'annuaire ;
  * le fait qu'un compte d'annuaire ne puisse jamais s'authentifier localement.
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

from src.auth_service import AuthService
from src.config import settings
from src.database import Base
from src.ldap_service import LdapProfile, LdapService, _escape, _parse_role_mapping
from src.models import AuthSource, User, UserRole
from src.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    permission_matrix,
    permissions_for,
    role_has,
    serialize_permissions,
)


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


def _user(db, username, role=UserRole.OPERATOR, source=AuthSource.LOCAL, password="motdepasse1"):
    u = User(
        id=str(uuid.uuid4()),
        username=username,
        email=f"{username}@cbc.cm",
        password_hash=AuthService.get_password_hash(password) if source == AuthSource.LOCAL else "!ldap",
        role=role,
        auth_source=source,
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


# ----------------------------------------------------------------- matrice


def test_every_role_is_in_the_matrix():
    """Un rôle ajouté au modèle sans entrée dans la matrice n'aurait aucun droit."""
    for role in UserRole:
        assert role in ROLE_PERMISSIONS, f"rôle absent de la matrice : {role}"


def test_admin_holds_every_permission():
    assert permissions_for(UserRole.ADMIN) == frozenset(Permission)


def test_read_only_can_never_mutate():
    """Aucune permission d'écriture pour la lecture seule."""
    held = permissions_for(UserRole.READ_ONLY)
    forbidden = {
        Permission.AGENT_EDIT,
        Permission.AGENT_REVOKE,
        Permission.AGENT_DELETE,
        Permission.ALERT_ACK,
        Permission.ALERT_RESOLVE,
        Permission.CONFIG_PUBLISH,
        Permission.SETTINGS_EDIT,
        Permission.USER_MANAGE,
        Permission.MAINTENANCE_EDIT,
    }
    assert held.isdisjoint(forbidden)


def test_operator_runs_operations_but_not_administration():
    assert role_has(UserRole.OPERATOR, Permission.ALERT_ACK)
    assert role_has(UserRole.OPERATOR, Permission.ALERT_RESOLVE)
    assert role_has(UserRole.OPERATOR, Permission.AGENT_EDIT)
    assert role_has(UserRole.OPERATOR, Permission.MAINTENANCE_EDIT)
    # …mais pas l'administration
    assert not role_has(UserRole.OPERATOR, Permission.USER_MANAGE)
    assert not role_has(UserRole.OPERATOR, Permission.SETTINGS_EDIT)
    assert not role_has(UserRole.OPERATOR, Permission.AGENT_DELETE)


def test_security_role_reads_and_audits_without_mutating():
    """DSH-025 : profil conformité — audit et lecture, aucune modification."""
    assert role_has(UserRole.SECURITY, Permission.AUDIT_VIEW)
    assert role_has(UserRole.SECURITY, Permission.AUDIT_EXPORT)
    assert role_has(UserRole.SECURITY, Permission.AGENT_VIEW)
    # Contrôle à quatre yeux sur les actions distantes (SEC-005)
    assert role_has(UserRole.SECURITY, Permission.ACTION_APPROVE)
    assert not role_has(UserRole.SECURITY, Permission.ACTION_SUBMIT)
    assert not role_has(UserRole.SECURITY, Permission.AGENT_EDIT)
    assert not role_has(UserRole.SECURITY, Permission.SETTINGS_EDIT)
    assert not role_has(UserRole.SECURITY, Permission.USER_MANAGE)


def test_audit_is_not_visible_to_operators():
    """La piste d'audit est réservée à l'administration et à la sécurité."""
    assert not role_has(UserRole.OPERATOR, Permission.AUDIT_VIEW)
    assert not role_has(UserRole.READ_ONLY, Permission.AUDIT_VIEW)


def test_matrix_serialises_for_the_ui():
    matrix = permission_matrix()
    assert set(matrix) == {r.value for r in UserRole}
    assert "alert:ack" in matrix["operator"]
    assert serialize_permissions(UserRole.READ_ONLY) == sorted(
        serialize_permissions(UserRole.READ_ONLY)
    )


# -------------------------------------------------------------------- LDAP


def test_ldap_filter_escaping_blocks_wildcard_injection():
    """Sans échappement, un nom `*` transformerait le filtre en joker et
    ferait remonter le premier compte de l'annuaire."""
    assert _escape("*") == "\\2a"
    assert _escape("a)(uid=admin") == "a\\29\\28uid=admin"
    assert _escape("norm.al") == "norm.al"


def test_role_mapping_parsing_is_case_insensitive_and_tolerant():
    mapping = _parse_role_mapping('{"CN=SOC,DC=cbc,DC=cm": "operator"}')
    assert mapping["cn=soc,dc=cbc,dc=cm"] == UserRole.OPERATOR

    # JSON invalide ou rôle inconnu : ignorés, jamais d'exception.
    assert _parse_role_mapping("pas du json") == {}
    assert _parse_role_mapping('{"CN=X": "roi"}') == {}
    assert _parse_role_mapping("") == {}


def test_role_resolution_falls_back_to_least_privilege(monkeypatch):
    monkeypatch.setattr(settings, "ldap_role_mapping", '{"CN=SOC,DC=cbc,DC=cm": "operator"}')
    monkeypatch.setattr(settings, "ldap_default_role", "read_only")

    assert LdapService._role_from_groups(["CN=SOC,DC=cbc,DC=cm"]) == UserRole.OPERATOR
    # Aucun groupe connu -> rôle par défaut, le moins privilégié.
    assert LdapService._role_from_groups(["CN=Autre,DC=cbc,DC=cm"]) == UserRole.READ_ONLY
    assert LdapService._role_from_groups([]) == UserRole.READ_ONLY


def test_invalid_default_role_falls_back_to_read_only(monkeypatch):
    monkeypatch.setattr(settings, "ldap_role_mapping", "{}")
    monkeypatch.setattr(settings, "ldap_default_role", "superuser")
    assert LdapService._role_from_groups([]) == UserRole.READ_ONLY


def test_ldap_disabled_by_default():
    assert settings.ldap_enabled is False
    assert LdapService.is_enabled() is False
    assert LdapService.status()["operational"] is False


def test_ldap_authenticate_refuses_empty_password(monkeypatch):
    """Un bind avec mot de passe vide réussit en anonyme sur certains
    annuaires : cela authentifierait n'importe qui."""
    monkeypatch.setattr(LdapService, "is_enabled", staticmethod(lambda: True))
    assert LdapService.authenticate("jdupont", "") is None
    assert LdapService.authenticate("", "secret") is None


# ------------------------------------------------- provisionnement annuaire


def test_ldap_user_is_provisioned_on_first_login(db):
    profile = LdapProfile(
        username="jdupont",
        email="j.dupont@cbcam.cm",
        display_name="Jean Dupont",
        dn="CN=Jean Dupont,OU=Users,DC=cbc,DC=cm",
        groups=["CN=SOC,DC=cbc,DC=cm"],
        role=UserRole.OPERATOR,
    )
    user = AuthService.sync_ldap_user(db, profile)

    assert user.username == "jdupont"
    assert user.auth_source == AuthSource.LDAP
    assert user.external_id == profile.dn
    assert user.role == UserRole.OPERATOR
    assert user.last_login_at is not None


def test_application_role_is_not_overwritten_by_the_directory(db):
    """Les droits se gèrent dans l'application, pas dans l'annuaire.

    Ce test vérifiait auparavant l'inverse — le rôle était réaligné sur
    l'annuaire à chaque connexion. La décision a été retournée : l'annuaire
    dit *qui* vous êtes, l'application dit *ce que* vous pouvez faire. Sous
    l'ancien comportement, une promotion accordée depuis l'écran
    Utilisateurs était silencieusement annulée à la reconnexion de
    l'intéressé.

    Contrepartie assumée : retirer quelqu'un d'un groupe d'annuaire ne lui
    retire plus ses droits applicatifs. La révocation d'accès reste immédiate
    par la désactivation du compte côté annuaire, qui empêche toute
    authentification. Le détail du contrat est couvert par
    `test_ldap_role_ownership.py`.
    """
    profile = LdapProfile(
        username="jdupont",
        email="j.dupont@cbcam.cm",
        display_name="Jean Dupont",
        dn="CN=Jean Dupont,OU=Users,DC=cbc,DC=cm",
        groups=["CN=SOC,DC=cbc,DC=cm"],
        role=UserRole.OPERATOR,
    )
    AuthService.sync_ldap_user(db, profile)

    profile.role = UserRole.READ_ONLY  # retiré du groupe SOC côté annuaire
    user = AuthService.sync_ldap_user(db, profile)

    assert user.role == UserRole.OPERATOR, "le rôle applicatif doit primer"
    assert db.query(User).count() == 1, "le compte doit être réutilisé, pas dupliqué"


def test_ldap_account_is_matched_by_dn_after_rename(db):
    profile = LdapProfile(
        username="jdupont",
        email="j.dupont@cbcam.cm",
        display_name="Jean Dupont",
        dn="CN=Jean Dupont,OU=Users,DC=cbc,DC=cm",
        groups=[],
        role=UserRole.READ_ONLY,
    )
    first = AuthService.sync_ldap_user(db, profile)

    profile.username = "jean.dupont"  # renommage côté annuaire, même DN
    second = AuthService.sync_ldap_user(db, profile)

    assert first.id == second.id
    assert db.query(User).count() == 1


def test_ldap_account_cannot_authenticate_locally(db):
    """Le compte miroir porte une empreinte inutilisable ; il ne doit jamais
    être authentifiable par mot de passe local."""
    profile = LdapProfile(
        username="jdupont",
        email="j.dupont@cbcam.cm",
        display_name="Jean Dupont",
        dn="CN=Jean Dupont,OU=Users,DC=cbc,DC=cm",
        groups=[],
        role=UserRole.OPERATOR,
    )
    AuthService.sync_ldap_user(db, profile)

    assert AuthService.authenticate_user(db, "jdupont", "!ldap") is None
    assert AuthService.authenticate_user(db, "jdupont", "motdepasse1") is None


def test_local_login_still_works_when_ldap_is_off(db):
    _user(db, "admin.local", role=UserRole.ADMIN, password="motdepasse1")
    user = AuthService.authenticate_user(db, "admin.local", "motdepasse1")
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.last_login_at is not None


def test_inactive_local_user_is_refused(db):
    u = _user(db, "parti", password="motdepasse1")
    u.is_active = False
    db.commit()
    assert AuthService.authenticate_user(db, "parti", "motdepasse1") is None


# ------------------------------------------------- spécificités Active Directory


def test_referrals_are_not_followed_by_default():
    """Active Directory renvoie des référencements que ldap3 suivrait sur un
    bind anonyme : la recherche paraîtrait alors infructueuse. Tous les clients
    AD les désactivent."""
    assert settings.ldap_follow_referrals is False


def test_ad_account_type_filter_excludes_machines_and_groups(monkeypatch):
    """Le filtre AD doit cibler les comptes utilisateurs normaux.

    `samaccounttype=805306368` (SAM_NORMAL_USER_ACCOUNT) exclut les comptes
    machine et les groupes, qui répondraient sinon au filtre et pourraient
    être « authentifiés ».
    """
    ad_filter = "(&(sAMAccountName={username})(samaccounttype=805306368))"
    monkeypatch.setattr(settings, "ldap_user_filter", ad_filter)
    rendered = settings.ldap_user_filter.replace("{username}", _escape("jdupont"))
    assert "samaccounttype=805306368" in rendered
    assert "sAMAccountName=jdupont" in rendered


def test_plaintext_bind_is_surfaced_in_status(monkeypatch):
    """Un bind en clair est une information d'exploitation, pas un détail."""
    monkeypatch.setattr(settings, "ldap_enabled", True)
    monkeypatch.setattr(settings, "ldap_use_ssl", False)
    monkeypatch.setattr(settings, "ldap_start_tls", False)
    assert LdapService.status()["plaintext_bind"] is True

    monkeypatch.setattr(settings, "ldap_use_ssl", True)
    assert LdapService.status()["plaintext_bind"] is False


def test_extra_attributes_are_carried_on_the_profile(db):
    """Les attributs métier (matricule, service, agence) suivent le compte."""
    profile = LdapProfile(
        username="jdupont",
        email="j.dupont@cbcam.cm",
        display_name="Jean Dupont",
        dn="CN=Jean Dupont,OU=Utilisateurs,DC=gie,DC=local",
        groups=[],
        role=UserRole.READ_ONLY,
        attributes={"department": "DTDSI", "office": "Siège", "title": "Ingénieur"},
    )
    user = AuthService.sync_ldap_user(db, profile)
    assert user.username == "jdupont"
    assert profile.attributes["department"] == "DTDSI"
