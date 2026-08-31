"""Connexion par nom d'utilisateur OU adresse email.

Régression : le formulaire imposait une adresse email puis n'en transmettait
que la partie locale (`email.split('@')[0]`), pendant que l'API rejetait en
422 tout identifiant contenant une arobase. Résultat : impossible de se
connecter avec son adresse, et impossible de se connecter avec un nom de
compte d'annuaire dont l'adresse ne dérive pas.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.auth_service import AuthService  # noqa: E402
from src.database import Base  # noqa: E402
from src.main import LoginRequest  # noqa: E402
from src.models import AuthSource, User, UserRole  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _user(db, *, username, email, password="Secret123!", active=True, source=None):
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=AuthService.get_password_hash(password),
        role=UserRole.OPERATOR,
        is_active=active,
    )
    if source is not None:
        user.auth_source = source
    db.add(user)
    db.commit()
    return user


# --------------------------------------------------------- validation d'entrée


@pytest.mark.parametrize(
    "identifier",
    [
        "admin",
        "jean.dupont",
        "jean.dupont@cbcam.cm",
        "JEAN.DUPONT@CBCAM.CM",
        "utilisateur@gie.local",
        "GIE\\cbciris",
        "o'brien",
        "prenom+alias@cbcam.cm",
        "josé.garcía@cbcam.cm",
        "a" * 200 + "@cbcam.cm",
    ],
)
def test_login_request_accepts_real_identifier_forms(identifier):
    """Email, UPN, DOMAINE\\utilisateur, patronyme accentué : tous recevables."""
    assert LoginRequest(username=identifier, password="x").username == identifier.strip()


def test_login_request_trims_surrounding_spaces():
    assert LoginRequest(username="  admin  ", password="x").username == "admin"


@pytest.mark.parametrize("identifier", ["", "   ", "admin\x00", "admin\nsecond"])
def test_login_request_rejects_empty_and_control_characters(identifier):
    with pytest.raises(ValidationError):
        LoginRequest(username=identifier, password="x")


def test_login_request_accepts_short_password():
    """La politique de robustesse s'applique à la création, pas à la connexion.

    Un minimum de 8 caractères ici rejetait en 422 des mots de passe
    d'annuaire parfaitement valides que la plateforme ne maîtrise pas.
    """
    assert LoginRequest(username="admin", password="abc").password == "abc"


# ------------------------------------------------------------ résolution locale


def test_resolves_by_username(db):
    user = _user(db, username="jdupont", email="jean.dupont@cbcam.cm")
    assert AuthService.resolve_local_user(db, "jdupont").id == user.id


def test_resolves_by_email(db):
    user = _user(db, username="jdupont", email="jean.dupont@cbcam.cm")
    assert AuthService.resolve_local_user(db, "jean.dupont@cbcam.cm").id == user.id


def test_resolution_ignores_case(db):
    user = _user(db, username="jdupont", email="jean.dupont@cbcam.cm")
    assert AuthService.resolve_local_user(db, "JDupont").id == user.id
    assert AuthService.resolve_local_user(db, "Jean.Dupont@CBCAM.CM").id == user.id


def test_exact_username_wins_over_someone_elses_email(db):
    """Un homonyme ne doit pas capter la connexion d'un autre compte."""
    target = _user(db, username="pierre", email="pierre@cbcam.cm")
    _user(db, username="autre", email="pierre@autre.cm")
    assert AuthService.resolve_local_user(db, "pierre").id == target.id


def test_unknown_identifier_resolves_to_nothing(db):
    _user(db, username="jdupont", email="jean.dupont@cbcam.cm")
    assert AuthService.resolve_local_user(db, "inconnu@cbcam.cm") is None
    assert AuthService.resolve_local_user(db, "") is None


# ---------------------------------------------------------- authentification


def test_authenticates_with_email(db):
    _user(db, username="jdupont", email="jean.dupont@cbcam.cm", password="Secret123!")
    user = AuthService.authenticate_user(db, "jean.dupont@cbcam.cm", "Secret123!")
    assert user is not None and user.username == "jdupont"


def test_authenticates_with_username(db):
    _user(db, username="jdupont", email="jean.dupont@cbcam.cm", password="Secret123!")
    assert AuthService.authenticate_user(db, "jdupont", "Secret123!") is not None


def test_wrong_password_still_refused_whatever_the_identifier(db):
    _user(db, username="jdupont", email="jean.dupont@cbcam.cm", password="Secret123!")
    assert AuthService.authenticate_user(db, "jdupont", "mauvais") is None
    assert AuthService.authenticate_user(db, "jean.dupont@cbcam.cm", "mauvais") is None


def test_inactive_account_refused_by_email_too(db):
    _user(db, username="parti", email="parti@cbcam.cm", password="Secret123!", active=False)
    assert AuthService.authenticate_user(db, "parti@cbcam.cm", "Secret123!") is None


def test_directory_account_never_authenticates_locally_via_email(db):
    """Un compte d'annuaire ne doit pas contourner le bind par son adresse."""
    _user(
        db,
        username="ldapuser",
        email="ldap.user@cbcam.cm",
        password="Secret123!",
        source=AuthSource.LDAP,
    )
    assert AuthService.authenticate_user(db, "ldap.user@cbcam.cm", "Secret123!") is None
