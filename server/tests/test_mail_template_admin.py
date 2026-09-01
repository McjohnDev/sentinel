"""Réglage des gabarits par vérification, et essai du canal n8n (point 8).

`test_mail_templates.py` éprouve le rendu et la résolution. Celui-ci éprouve
ce qui manquait pour que l'exploitant puisse s'en servir : revenir au gabarit
livré, voir le rendu avant d'enregistrer, et vérifier que le webhook — le
canal par lequel n8n est déclenché — aboutit réellement.
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
from src.main import app  # noqa: E402
from src.mail_templates import DEFAULT_TEMPLATES  # noqa: E402
from src.models import MailTemplate, MessagingConfig, User, UserRole  # noqa: E402

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
        id=str(uuid.uuid4()), username="u-%s" % uuid.uuid4().hex[:6],
        email="u@cbcam.cm", password_hash="!x", role=role, is_active=True,
    )
    db.add(user)
    db.commit()
    token = AuthService.create_access_token(data={"sub": user.id})
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer %s" % token})
    return client


def _seed(client):
    """Les défauts sont installés à la première lecture."""
    assert client.get("/api/settings/mail-templates").status_code == 200


def _global_row(db, kind, event_key):
    db.expire_all()
    return (
        db.query(MailTemplate)
        .filter(MailTemplate.kind == kind, MailTemplate.event_key == event_key, MailTemplate.agent_id == "")
        .first()
    )


# --------------------------------------------------- un gabarit par vérification


def test_every_verification_has_a_template(db):
    client = _client(db)
    rows = client.get("/api/settings/mail-templates").json()["data"]

    keys = {(r["kind"], r["event_key"]) for r in rows if r["scope"] == "global"}
    # L'exploitant doit voir ce qui *peut* être réglé, pas seulement ce qu'il
    # a déjà personnalisé.
    assert set(DEFAULT_TEMPLATES.keys()) <= keys


def test_the_verifications_cover_the_checks_of_point_6(db):
    client = _client(db)
    rows = client.get("/api/settings/mail-templates").json()["data"]
    keys = {r["event_key"] for r in rows}
    for expected in ("cpu_high", "ram_high", "disk_high", "service_down", "file_anomaly", "agent_offline"):
        assert expected in keys, expected


# ----------------------------------------------------------- retour au défaut


def test_resetting_restores_the_shipped_template(db):
    client = _client(db)
    _seed(client)
    original = _global_row(db, "alert", "disk_high").subject

    client.put(
        "/api/settings/mail-templates",
        json={"kind": "alert", "event_key": "disk_high", "subject": "Sujet maison", "body_html": "<p>x</p>"},
    )
    db.expire_all()
    assert _global_row(db, "alert", "disk_high").subject == "Sujet maison"

    response = client.request(
        "DELETE", "/api/settings/mail-templates",
        params={"kind": "alert", "event_key": "disk_high"},
    )

    assert response.status_code == 200
    db.expire_all()
    # Réinstallé : sans quoi la vérification n'aurait plus de gabarit et
    # l'alerte partirait sans mise en forme.
    assert _global_row(db, "alert", "disk_high").subject == original


def test_resetting_an_agent_override_leaves_the_global_alone(db):
    client = _client(db)
    _seed(client)
    client.put(
        "/api/settings/mail-templates",
        json={"kind": "alert", "event_key": "cpu_high", "subject": "Pour cet hôte",
              "body_html": "<p>x</p>", "agent_id": "A3F09C"},
    )
    global_before = _global_row(db, "alert", "cpu_high").subject

    client.request(
        "DELETE", "/api/settings/mail-templates",
        params={"kind": "alert", "event_key": "cpu_high", "agent_id": "A3F09C"},
    )

    db.expire_all()
    assert _global_row(db, "alert", "cpu_high").subject == global_before
    remaining = (
        db.query(MailTemplate)
        .filter(MailTemplate.agent_id == "A3F09C", MailTemplate.event_key == "cpu_high")
        .count()
    )
    assert remaining == 0


def test_an_operator_cannot_reset_a_template(db):
    client = _client(db, UserRole.OPERATOR)
    response = client.request(
        "DELETE", "/api/settings/mail-templates",
        params={"kind": "alert", "event_key": "cpu_high"},
    )
    assert response.status_code == 403


# ------------------------------------------------------------------- aperçu


def test_the_preview_renders_without_sending(db):
    client = _client(db)

    response = client.post(
        "/api/settings/mail-templates/preview",
        json={"subject": "{hostname} — {alert_type}", "body_html": "<p>{message}</p>"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "web-01.prod — disk_high"
    assert "Disque /u01" in body["body_html"]


def test_the_preview_accepts_a_caller_context(db):
    client = _client(db)
    response = client.post(
        "/api/settings/mail-templates/preview",
        json={"subject": "{hostname}", "body_html": "<p>x</p>", "context": {"hostname": "swift-01"}},
    )
    assert response.json()["subject"] == "swift-01"


def test_an_unknown_placeholder_does_not_break_the_preview(db):
    # Découvrir un champ manquant au moment de la première vraie alerte serait
    # le pire moment : l'aperçu doit tenir, même incomplet.
    client = _client(db)
    response = client.post(
        "/api/settings/mail-templates/preview",
        json={"subject": "{champ_inexistant}", "body_html": "<p>{autre}</p>"},
    )
    assert response.status_code == 200


# ------------------------------------------------------- webhook / n8n


def test_the_webhook_test_is_refused_when_nothing_is_configured(db):
    client = _client(db)
    response = client.post("/api/settings/webhook/test", json={})
    assert response.status_code == 400
    assert "webhook" in response.json()["detail"].lower()


def _configure_webhook(db):
    cfg = db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()
    if not cfg:
        cfg = MessagingConfig(id="default")
        db.add(cfg)
    cfg.webhook_enabled = True
    cfg.webhook_url = "https://n8n.cbc.cm/webhook/supervision"
    cfg.webhook_secret = "secret-partage"
    db.commit()
    return cfg


def test_a_successful_test_sends_a_signed_marked_payload(db, monkeypatch):
    import src.main as main_module
    from src import webhook_service

    _configure_webhook(db)
    sent = {}

    def capture(url, secret, payload):
        sent.update({"url": url, "secret": secret, "payload": payload})
        return True

    monkeypatch.setattr(webhook_service, "post_signed", capture)
    monkeypatch.setattr(main_module, "webhook_service", webhook_service, raising=False)

    response = _client(db).post("/api/settings/webhook/test", json={})

    assert response.status_code == 200
    assert sent["url"] == "https://n8n.cbc.cm/webhook/supervision"
    # Marquée : un scénario n8n doit pouvoir la reconnaître et ne pas la
    # traiter comme un incident réel.
    assert sent["payload"]["test"] is True


def test_a_refused_webhook_says_what_to_check(db, monkeypatch):
    from src import webhook_service

    _configure_webhook(db)
    monkeypatch.setattr(webhook_service, "post_signed", lambda *a, **k: False)

    response = _client(db).post("/api/settings/webhook/test", json={})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "n8n" in detail or "secret" in detail


def test_an_operator_cannot_fire_the_webhook_test(db):
    _configure_webhook(db)
    response = _client(db, UserRole.OPERATOR).post("/api/settings/webhook/test", json={})
    assert response.status_code == 403
