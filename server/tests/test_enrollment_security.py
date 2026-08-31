"""SEC-001 / AGT-004 — jetons d'enrôlement à usage unique et datés.

Couvre les régressions corrigées :
  * un jeton émis par l'API d'administration (table enrollment_tokens) était
    ignoré par l'endpoint d'enrôlement, qui ne consultait qu'un dictionnaire
    mémoire ;
  * le jeton d'amorçage de laboratoire était exempté de la consommation, donc
    réutilisable indéfiniment ;
  * un hôte déjà connu (machine_id existant) retournait avant toute
    consommation, ce qui rendait n'importe quel jeton réutilisable ;
  * l'expiration n'était jamais vérifiée.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import EnrollmentToken
from src import main as main_module


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


@pytest.fixture(autouse=True)
def clean_bootstrap():
    """Isole le cache mémoire du jeton d'amorçage entre les tests."""
    saved = dict(main_module.enrollment_tokens)
    main_module.enrollment_tokens.clear()
    yield
    main_module.enrollment_tokens.clear()
    main_module.enrollment_tokens.update(saved)


def _issue(db, token: str, *, hours: int = 24, status: str = "active") -> EnrollmentToken:
    row = EnrollmentToken(
        id=str(uuid.uuid4()),
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=hours),
        status=status,
        created_by="admin",
    )
    db.add(row)
    db.commit()
    return row


def test_unknown_token_is_rejected(db):
    with pytest.raises(HTTPException) as exc:
        main_module._resolve_enrollment_token(db, "jeton-inexistant")
    assert exc.value.status_code == 401


def test_admin_issued_token_is_accepted(db):
    """Régression : les jetons émis en base n'étaient jamais consultés."""
    _issue(db, "CBC-ENROLL-ABCDE-2026")
    handle = main_module._resolve_enrollment_token(db, "CBC-ENROLL-ABCDE-2026")
    assert handle[0] == "db"


def test_admin_issued_token_is_single_use(db):
    _issue(db, "CBC-ENROLL-ONCE1-2026")
    handle = main_module._resolve_enrollment_token(db, "CBC-ENROLL-ONCE1-2026")
    main_module._consume_enrollment_token(db, handle)

    row = db.query(EnrollmentToken).filter_by(token="CBC-ENROLL-ONCE1-2026").first()
    assert row.status == "consumed"

    with pytest.raises(HTTPException) as exc:
        main_module._resolve_enrollment_token(db, "CBC-ENROLL-ONCE1-2026")
    assert exc.value.status_code == 400


def test_expired_token_is_rejected_and_marked(db):
    _issue(db, "CBC-ENROLL-OLD01-2026", hours=-1)
    with pytest.raises(HTTPException) as exc:
        main_module._resolve_enrollment_token(db, "CBC-ENROLL-OLD01-2026")
    assert exc.value.status_code == 401
    row = db.query(EnrollmentToken).filter_by(token="CBC-ENROLL-OLD01-2026").first()
    assert row.status == "expired"


def test_revoked_token_is_rejected(db):
    _issue(db, "CBC-ENROLL-REVOK-2026", status="revoked")
    with pytest.raises(HTTPException) as exc:
        main_module._resolve_enrollment_token(db, "CBC-ENROLL-REVOK-2026")
    assert exc.value.status_code == 401


def test_bootstrap_token_is_consumed_by_default(db):
    """Sans opt-in explicite, le jeton d'amorçage est à usage unique."""
    main_module.enrollment_tokens["lab-token"] = {
        "used": False,
        "expires_at": None,
        "reusable": False,
    }
    handle = main_module._resolve_enrollment_token(db, "lab-token")
    main_module._consume_enrollment_token(db, handle)

    with pytest.raises(HTTPException) as exc:
        main_module._resolve_enrollment_token(db, "lab-token")
    assert exc.value.status_code == 400


def test_bootstrap_token_reusable_only_when_opted_in(db):
    main_module.enrollment_tokens["lab-token"] = {
        "used": False,
        "expires_at": None,
        "reusable": True,
    }
    for _ in range(3):
        handle = main_module._resolve_enrollment_token(db, "lab-token")
        main_module._consume_enrollment_token(db, handle)
    # Toujours accepté : réutilisation explicitement autorisée pour les démos.
    assert main_module._resolve_enrollment_token(db, "lab-token")[0] == "memory"


def test_no_bootstrap_token_without_configuration():
    """Aucun jeton codé en dur ne doit exister par défaut.

    `demo-token-123` était auparavant présent en dur dans le module et exempté
    de consommation.
    """
    from src.config import settings

    assert settings.bootstrap_enrollment_token is None
    assert settings.bootstrap_token_reusable is False
