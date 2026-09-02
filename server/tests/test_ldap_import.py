"""Import de comptes depuis l'annuaire.

Deux voies coexistent, demandees ensemble : l'import manuel prepare les acces
a l'avance, et la creation automatique a la premiere connexion rattrape ceux
qui ne l'ont pas ete. La seconde existait deja (`sync_ldap_user`) ; ce module
eprouve la premiere, et surtout ce qui les distingue de la creation locale —
**aucun mot de passe n'est detenu par la plateforme**.
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

from src.auth_service import AuthService  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.ldap_service import LdapProfile, LdapService  # noqa: E402
from src.main import app  # noqa: E402
from src.models import AuthSource, User, UserRole  # noqa: E402

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


def _client(db, role=UserRole.ADMIN):
    user = User(
        id=str(uuid.uuid4()), username="adm-%s" % uuid.uuid4().hex[:5],
        email="a@cbcam.cm", password_hash="!x", role=role, is_active=True,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client


PROFILE = LdapProfile(
    username="akengne",
    email="alain.kengne@cbcam.cm",
    display_name="Alain Kengne",
    dn="CN=Alain Kengne,OU=IT,DC=cbc,DC=local",
    groups=["CN=Exploitation,OU=Groupes,DC=cbc,DC=local"],
    role=UserRole.OPERATOR,
    attributes={"department": "Informatique"},
)


def _enable_ldap(monkeypatch, profiles=None, found=PROFILE):
    monkeypatch.setattr(LdapService, "is_enabled", staticmethod(lambda: True))
    monkeypatch.setattr(
        LdapService, "search_users",
        staticmethod(lambda term, limit=25, db=None: list(profiles if profiles is not None else [PROFILE])),
    )
    monkeypatch.setattr(LdapService, "find_user", staticmethod(lambda username, db=None: found))


# ------------------------------------------------------------- recherche


def test_a_search_returns_directory_candidates(db, monkeypatch):
    _enable_ldap(monkeypatch)

    body = _client(db).get("/api/settings/ldap/search", params={"q": "keng"}).json()

    assert body["count"] == 1
    row = body["data"][0]
    assert row["username"] == "akengne"
    assert row["display_name"] == "Alain Kengne"
    assert row["department"] == "Informatique"
    assert row["already_imported"] is False


def test_an_account_already_present_is_flagged(db, monkeypatch):
    # Sans ce repere, l'administrateur tente un import qui echouera en 409.
    _enable_ldap(monkeypatch)
    db.add(User(
        id=str(uuid.uuid4()), username="akengne", email="x@cbcam.cm",
        password_hash="!x", role=UserRole.OPERATOR, is_active=True,
    ))
    db.commit()

    body = _client(db).get("/api/settings/ldap/search", params={"q": "keng"}).json()

    assert body["data"][0]["already_imported"] is True


def test_a_disabled_directory_is_refused_clearly(db, monkeypatch):
    monkeypatch.setattr(LdapService, "is_enabled", staticmethod(lambda: False))
    response = _client(db).get("/api/settings/ldap/search", params={"q": "keng"})
    assert response.status_code == 400
    assert "nnuaire" in response.json()["detail"]


def test_an_operator_cannot_search_the_directory(db, monkeypatch):
    _enable_ldap(monkeypatch)
    assert _client(db, UserRole.OPERATOR).get(
        "/api/settings/ldap/search", params={"q": "keng"}
    ).status_code == 403


# ---------------------------------------------------------------- import


def test_importing_creates_an_account_without_a_local_password(db, monkeypatch):
    """Le point central : la plateforme ne detient aucun secret.

    Un mot de passe local ferait survivre l'acces a un depart traite cote
    annuaire — la revocation cesserait d'etre immediate.
    """
    _enable_ldap(monkeypatch)

    response = _client(db).post("/api/settings/ldap/import", json={"username": "akengne"})

    assert response.status_code == 200, response.text
    created = db.query(User).filter(User.username == "akengne").first()
    assert created is not None
    assert created.auth_source == AuthSource.LDAP
    assert created.external_id == PROFILE.dn
    # Aucun mot de passe exploitable : l'authentification reste a l'annuaire.
    assert not AuthService.verify_password("nimporte", created.password_hash or "!")


def test_the_chosen_role_wins_over_the_directory_suggestion(db, monkeypatch):
    _enable_ldap(monkeypatch)

    _client(db).post("/api/settings/ldap/import", json={"username": "akengne", "role": "admin"})

    assert db.query(User).filter(User.username == "akengne").first().role == UserRole.ADMIN


def test_an_unknown_role_is_refused(db, monkeypatch):
    _enable_ldap(monkeypatch)
    response = _client(db).post(
        "/api/settings/ldap/import", json={"username": "akengne", "role": "chef"}
    )
    assert response.status_code == 400
    assert db.query(User).filter(User.username == "akengne").first() is None


def test_an_account_absent_from_the_directory_is_refused(db, monkeypatch):
    _enable_ldap(monkeypatch, found=None)
    response = _client(db).post("/api/settings/ldap/import", json={"username": "fantome"})
    assert response.status_code == 404


def test_importing_twice_is_refused_rather_than_duplicating(db, monkeypatch):
    _enable_ldap(monkeypatch)
    client = _client(db)
    client.post("/api/settings/ldap/import", json={"username": "akengne"})

    response = client.post("/api/settings/ldap/import", json={"username": "akengne"})

    assert response.status_code == 409
    assert db.query(User).filter(User.username == "akengne").count() == 1


def test_an_operator_cannot_import(db, monkeypatch):
    _enable_ldap(monkeypatch)
    assert _client(db, UserRole.OPERATOR).post(
        "/api/settings/ldap/import", json={"username": "akengne"}
    ).status_code == 403


def test_a_role_granted_here_survives_the_next_login(db, monkeypatch):
    """L'annuaire repond a « qui etes-vous », pas a « que pouvez-vous ».

    Realigner le role a chaque connexion annulerait une promotion accordee
    dans la plateforme, sans trace ni message.
    """
    _enable_ldap(monkeypatch)
    _client(db).post("/api/settings/ldap/import", json={"username": "akengne", "role": "admin"})

    # Connexion suivante : l'annuaire propose « operator ».
    AuthService.sync_ldap_user(db, PROFILE)

    assert db.query(User).filter(User.username == "akengne").first().role == UserRole.ADMIN
