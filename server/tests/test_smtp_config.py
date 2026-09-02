"""Relais SMTP : réglage, secret, et essai.

Le point sensible est le mot de passe. Il ne doit jamais repartir vers le
navigateur — une clé rendue par une API finit dans un cache, un journal de
proxy ou une capture d'écran — et un formulaire qui ne le réaffiche pas ne
doit pas l'effacer en enregistrant le reste.
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

from src import email_service  # noqa: E402
from src.auth_service import AuthService  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402
from src.models import MessagingConfig, User, UserRole  # noqa: E402

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
        email="ops@cbcam.cm", password_hash="!x", role=role, is_active=True,
    )
    db.add(user)
    db.commit()
    client = TestClient(app)
    client.headers.update(
        {"Authorization": "Bearer %s" % AuthService.create_access_token(data={"sub": user.id})}
    )
    return client


def _cfg(db):
    db.expire_all()
    return db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()


SETTINGS = {
    "enabled": True,
    "host": "smtp.exemple.local",
    "port": 25,
    "auth": True,
    "username": "compte-service",
    "password": "un-secret",
    "encryption": "none",
    "from_address": "sentinel@exemple.com",
    "from_name": "Sentinel",
}


# ------------------------------------------------------------ enregistrement


def test_the_relay_settings_are_stored(db):
    client = _client(db)

    response = client.put("/api/settings/smtp", json=SETTINGS)

    assert response.status_code == 200, response.text
    cfg = _cfg(db)
    assert cfg.smtp_host == "smtp.exemple.local"
    assert cfg.smtp_port == 25
    assert cfg.smtp_from == "sentinel@exemple.com"
    assert cfg.smtp_from_name == "Sentinel"
    assert cfg.smtp_password == "un-secret"


def test_the_password_never_comes_back(db):
    """Une clé rendue par une API finit dans un cache ou un journal de proxy."""
    client = _client(db)
    client.put("/api/settings/smtp", json=SETTINGS)

    body = client.get("/api/settings/smtp").json()

    assert "password" not in body
    assert "un-secret" not in str(body)
    # Seule sa présence est signalée, pour savoir s'il faut le ressaisir.
    assert body["password_set"] is True


def test_saving_without_the_password_keeps_it(db):
    # Le formulaire ne réaffiche pas le mot de passe : sans cette règle,
    # chaque enregistrement l'effacerait.
    client = _client(db)
    client.put("/api/settings/smtp", json=SETTINGS)

    client.put("/api/settings/smtp", json={"host": "autre.local"})

    cfg = _cfg(db)
    assert cfg.smtp_host == "autre.local"
    assert cfg.smtp_password == "un-secret"


def test_an_empty_password_clears_it(db):
    client = _client(db)
    client.put("/api/settings/smtp", json=SETTINGS)

    client.put("/api/settings/smtp", json={"password": ""})

    assert _cfg(db).smtp_password is None


@pytest.mark.parametrize("value", ["tls", "aucun", "SSLv3"])
def test_an_unknown_encryption_is_refused(db, value):
    response = _client(db).put("/api/settings/smtp", json={"encryption": value})
    assert response.status_code == 400


@pytest.mark.parametrize("value", ["none", "starttls", "ssl", "STARTTLS"])
def test_the_supported_encryptions_are_accepted(db, value):
    response = _client(db).put("/api/settings/smtp", json={"encryption": value})
    assert response.status_code == 200
    assert _cfg(db).smtp_encryption == value.lower()


@pytest.mark.parametrize("port", [0, 70000, -1])
def test_a_port_out_of_range_is_refused(db, port):
    assert _client(db).put("/api/settings/smtp", json={"port": port}).status_code == 400


def test_an_operator_cannot_read_the_relay_settings(db):
    assert _client(db, UserRole.OPERATOR).get("/api/settings/smtp").status_code == 403


# ------------------------------------------------------------- exploitabilité


def test_a_disabled_relay_refuses_to_send(db):
    with pytest.raises(email_service.SmtpNotConfigured):
        email_service.send(db, to="x@cbcam.cm", subject="s", body_html="<p>b</p>")


def test_auth_without_credentials_is_refused(db):
    cfg = MessagingConfig(
        id="default", smtp_enabled=True, smtp_host="smtp.local",
        smtp_from="a@b.c", smtp_auth=True,
    )
    db.add(cfg)
    db.commit()

    with pytest.raises(email_service.SmtpNotConfigured) as exc:
        email_service.send(db, to="x@cbcam.cm", subject="s", body_html="<p>b</p>")
    assert "mot de passe" in str(exc.value).lower() or "identifiant" in str(exc.value).lower()


def test_a_relay_without_a_sender_is_refused(db):
    db.add(MessagingConfig(id="default", smtp_enabled=True, smtp_host="smtp.local"))
    db.commit()
    with pytest.raises(email_service.SmtpNotConfigured):
        email_service.send(db, to="x@cbcam.cm", subject="s", body_html="<p>b</p>")


# -------------------------------------------------------------------- envoi


class _FakeServer:
    def __init__(self):
        self.logged_in = None
        self.sent = []
        self.quit_called = False
        self.started_tls = False

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message, to_addrs=None):
        self.sent.append((message, to_addrs))

    def quit(self):
        self.quit_called = True


def _enabled(db, **overrides):
    values = dict(
        id="default", smtp_enabled=True, smtp_host="smtp.local", smtp_port=25,
        smtp_auth=True, smtp_username="u", smtp_password="p",
        smtp_encryption="none", smtp_from="sentinel@cbc.cm", smtp_from_name="Sentinel",
        # Les destinataires sont partages par les deux canaux : sans eux, rien
        # ne part, quel que soit le relais configure.
        recipients='["ops@cbcam.cm"]',
    )
    values.update(overrides)
    cfg = MessagingConfig(**values)
    db.add(cfg)
    db.commit()
    return cfg


def test_a_message_is_sent_with_the_configured_sender(db, monkeypatch):
    _enabled(db)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    assert email_service.send(db, to="ops@cbcam.cm", subject="Sujet", body_html="<p>corps</p>")

    message, to_addrs = fake.sent[0]
    assert to_addrs == ["ops@cbcam.cm"]
    assert message["Subject"] == "Sujet"
    assert "Sentinel" in message["From"]
    assert "sentinel@cbc.cm" in message["From"]
    assert fake.logged_in == ("u", "p")
    assert fake.quit_called


def test_several_recipients_are_all_addressed(db, monkeypatch):
    _enabled(db)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    email_service.send(db, to=["a@cbc.cm", "b@cbc.cm"], subject="s", body_html="<p>b</p>")

    assert fake.sent[0][1] == ["a@cbc.cm", "b@cbc.cm"]


def test_no_login_when_auth_is_off(db, monkeypatch):
    _enabled(db, smtp_auth=False, smtp_username=None, smtp_password=None)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    email_service.send(db, to="a@cbc.cm", subject="s", body_html="<p>b</p>")

    assert fake.logged_in is None


def test_a_refused_authentication_is_reported_plainly(db, monkeypatch):
    import smtplib

    _enabled(db)

    class _Refusing(_FakeServer):
        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(email_service, "_connect", lambda _cfg: _Refusing())

    with pytest.raises(email_service.SmtpSendFailed) as exc:
        email_service.send(db, to="a@cbc.cm", subject="s", body_html="<p>b</p>")
    assert "authentification" in str(exc.value).lower()


def test_an_unreachable_relay_names_the_host(db, monkeypatch):
    _enabled(db)

    def refuse(_cfg):
        raise OSError("connexion refusée")

    monkeypatch.setattr(email_service, "_connect", refuse)

    with pytest.raises(email_service.SmtpSendFailed) as exc:
        email_service.send(db, to="a@cbc.cm", subject="s", body_html="<p>b</p>")
    assert "smtp.local" in str(exc.value)


def test_a_failed_goodbye_does_not_turn_a_success_into_a_failure(db, monkeypatch):
    _enabled(db)

    class _RudeExit(_FakeServer):
        def quit(self):
            raise OSError("connexion coupée")

    monkeypatch.setattr(email_service, "_connect", lambda _cfg: _RudeExit())

    # Le message est parti ; l'adieu raté ne change rien.
    assert email_service.send(db, to="a@cbc.cm", subject="s", body_html="<p>b</p>")


def test_the_body_carries_a_text_alternative(db, monkeypatch):
    # Certains clients bancaires refusent le HTML seul, et un courriel
    # d'alerte illisible ne vaut pas mieux qu'un courriel non envoyé.
    _enabled(db)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    email_service.send(db, to="a@cbc.cm", subject="s", body_html="<p>corps</p>")

    message = fake.sent[0][0]
    assert message.is_multipart()
    assert {part.get_content_type() for part in message.iter_parts()} >= {"text/plain", "text/html"}


# --------------------------------------------------------------------- essai


def test_the_test_route_reports_a_relay_failure(db, monkeypatch):
    _enabled(db)

    def refuse(_cfg):
        raise OSError("refus")

    monkeypatch.setattr(email_service, "_connect", refuse)

    response = _client(db).post("/api/settings/smtp/test", json={})

    assert response.status_code == 502
    assert "smtp.local" in response.json()["detail"]


def test_the_test_route_falls_back_to_the_caller_address(db, monkeypatch):
    _enabled(db)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    response = _client(db).post("/api/settings/smtp/test", json={})

    assert response.status_code == 200
    assert response.json()["to"] == "ops@cbcam.cm"


# ------------------------------------ le relais sert reellement les alertes


def test_an_alert_is_sent_through_smtp_when_the_cbc_api_is_absent(db, monkeypatch):
    """Regression : configurer le SMTP ne changeait rien aux alertes.

    Le chemin d'alerte n'appelait que l'API Mail CBC. Une plateforme n'ayant
    que le relais interne n'envoyait donc aucune notification, alors que
    l'ecran de reglage affichait une configuration valide et qu'un envoi
    d'essai aboutissait.
    """
    from src.messaging_service import MessagingService

    _enabled(db)  # SMTP actif ; aucune API Mail CBC configuree
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    sent = MessagingService.send_alert_notification(
        alert_type="disk_high", severity="critical",
        message="Disque /u01 a 96 %", hostname="web-01",
        value=96, threshold=85, db=db,
    )

    assert sent is True, "l'alerte doit partir par le relais SMTP"
    assert fake.sent, "aucun message n'a atteint le relais"
    message = fake.sent[0][0]
    assert "web-01" in message["Subject"] or "Disque" in message["Subject"]


def test_the_smtp_body_uses_the_per_verification_template(db, monkeypatch):
    # Sinon deux mises en forme concurrentes pour le meme incident selon le
    # canal emprunte.
    from src.mail_templates import seed_defaults
    from src.messaging_service import MessagingService

    seed_defaults(db)
    _enabled(db)
    fake = _FakeServer()
    monkeypatch.setattr(email_service, "_connect", lambda _cfg: fake)

    MessagingService.send_alert_notification(
        alert_type="disk_high", severity="critical", message="Disque plein",
        hostname="web-01", db=db,
    )

    html = [p for p in fake.sent[0][0].iter_parts() if p.get_content_type() == "text/html"][0]
    body = html.get_content()
    assert "web-01" in body


def test_a_broken_relay_does_not_prevent_the_alert_from_existing(db, monkeypatch):
    # La notification est un effet de bord de l'alerte, pas sa condition.
    from src.messaging_service import MessagingService

    _enabled(db)

    def refuse(_cfg):
        raise OSError("relais injoignable")

    monkeypatch.setattr(email_service, "_connect", refuse)

    assert MessagingService.send_alert_notification(
        alert_type="cpu_high", severity="major", message="CPU", hostname="web-01", db=db,
    ) is False


def test_no_channel_at_all_reports_no_delivery(db):
    from src.messaging_service import MessagingService

    assert MessagingService.send_alert_notification(
        alert_type="cpu_high", severity="major", message="CPU", hostname="web-01", db=db,
    ) is False
