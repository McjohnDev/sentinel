"""Changement de mot de passe par le titulaire du compte.

L'écran Profil proposait un formulaire complet — mot de passe actuel, nouveau,
confirmation — qui validait la saisie, vidait les champs et affichait
« Changement enregistré ». Aucune requête n'était émise : le mot de passe
restait inchangé et l'utilisateur repartait convaincu du contraire.

La réinitialisation administrateur `/api/auth/users/{user_id}/password` ne
pouvait pas servir de branchement : elle exige la permission USER_MANAGE, que
le titulaire n'a pas, et ne vérifie pas le secret courant.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.auth_service import AuthService
from src.database import Base, get_db
from src.main import app, get_current_user
from src.models import AuthSource, User, UserRole

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CURRENT = "Secret123!"


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
        app.dependency_overrides.pop(get_current_user, None)
        Base.metadata.drop_all(bind=engine)


def _account(db, *, source=AuthSource.LOCAL) -> User:
    user = User(
        id=str(uuid.uuid4()),
        username="operateur",
        email="operateur@cbc.cm",
        password_hash=AuthService.get_password_hash(CURRENT),
        role=UserRole.OPERATOR,
        is_active=True,
    )
    user.auth_source = source
    db.add(user)
    db.commit()
    return user


def _client_as(user: User) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _stored_hash(db, user_id: str) -> str:
    db.expire_all()
    return db.query(User).filter(User.id == user_id).first().password_hash


def test_password_actually_changes(db):
    user = _account(db)
    before = _stored_hash(db, user.id)

    response = _client_as(user).post(
        "/api/auth/me/password",
        json={"current_password": CURRENT, "new_password": "NouveauSecret1!"},
    )

    assert response.status_code == 200
    after = _stored_hash(db, user.id)
    assert after != before
    assert AuthService.verify_password("NouveauSecret1!", after)


def test_wrong_current_password_is_refused(db):
    user = _account(db)
    before = _stored_hash(db, user.id)

    response = _client_as(user).post(
        "/api/auth/me/password",
        json={"current_password": "PasLeBon1!", "new_password": "NouveauSecret1!"},
    )

    assert response.status_code == 400
    # Le point central de la régression : un refus doit laisser le secret intact.
    assert _stored_hash(db, user.id) == before


def test_directory_account_is_refused(db):
    user = _account(db, source=AuthSource.LDAP)
    before = _stored_hash(db, user.id)

    response = _client_as(user).post(
        "/api/auth/me/password",
        json={"current_password": CURRENT, "new_password": "NouveauSecret1!"},
    )

    assert response.status_code == 400
    assert "annuaire" in response.json()["detail"].lower()
    assert _stored_hash(db, user.id) == before


def test_reusing_the_current_password_is_refused(db):
    user = _account(db)

    response = _client_as(user).post(
        "/api/auth/me/password",
        json={"current_password": CURRENT, "new_password": CURRENT},
    )

    assert response.status_code == 400
    assert AuthService.verify_password(CURRENT, _stored_hash(db, user.id))


def test_short_password_is_rejected_before_reaching_the_account(db):
    user = _account(db)
    before = _stored_hash(db, user.id)

    response = _client_as(user).post(
        "/api/auth/me/password",
        json={"current_password": CURRENT, "new_password": "court"},
    )

    assert response.status_code == 422
    assert _stored_hash(db, user.id) == before
