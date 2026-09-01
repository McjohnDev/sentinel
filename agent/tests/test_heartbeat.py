"""Battement, écho et reprise de contact (point 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import requests

import heartbeat as hb
from config import AgentConfig
from enrollment import Credentials
from facts import HostFacts
from metrics import SystemSample

CONFIG = AgentConfig(
    server_url="https://plateforme.cbc:8443",
    enrollment_token="",
    tls_verify=True,
    machine_type="server",
    timeout_seconds=5,
)

CREDS = Credentials(agent_id="A3F09C", auth_key="cle-secrete")

HOST = HostFacts(
    hostname="web-01.prod",
    os="Linux",
    os_version="5.15.0",
    ip_address="10.0.0.12",
    cpu_cores=4,
    ram_total_gb=15.5,
    disk_total_gb=200.0,
    runtime={"frozen": False},
)

SAMPLE = SystemSample(
    cpu_percent=12.5,
    cpu_cores=4,
    ram_percent=41.0,
    ram_total_gb=15.5,
    ram_used_gb=6.4,
    ram_free_gb=9.1,
    disk_percent=63.0,
    disk_total_gb=200.0,
    disk_used_gb=126.0,
    disk_free_gb=74.0,
    uptime_seconds=98765,
)

NOW = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload


class _Session:
    def __init__(self, *responses, raises=None):
        self.responses = list(responses)
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.raises:
            raise self.raises
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def _ok(**echo):
    base = {"agent_id": "A3F09C", "server_time": "2026-09-01T10:00:00Z"}
    base.update(echo)
    return _Response(200, {"status": "success", "tasks": [], "config": None, "echo": base})


# ------------------------------------------------------------------ payload


def test_payload_carries_every_required_field():
    payload = hb.build_payload(SAMPLE, HOST, taken_at=NOW)
    required = [
        "timestamp", "cpu_percent", "cpu_cores", "ram_percent", "ram_total_gb",
        "ram_used_gb", "ram_free_gb", "disk_percent", "disk_total_gb",
        "disk_used_gb", "disk_free_gb", "uptime_seconds",
    ]
    for field in required:
        assert field in payload, "champ obligatoire manquant : %s" % field


def test_timestamp_is_the_measurement_time_and_carries_a_timezone():
    payload = hb.build_payload(SAMPLE, HOST, taken_at=NOW)
    # La plateforme stocke cette date telle quelle comme date d'échantillon.
    assert payload["timestamp"].startswith("2026-09-01T10:00:00")
    assert payload["timestamp"].endswith("+00:00")


def test_a_naive_timestamp_is_refused():
    # Deux conventions d'horloge dans un même agent avaient déjà fait vieillir
    # des enregistrements du décalage UTC local.
    with pytest.raises(ValueError):
        hb.build_payload(SAMPLE, HOST, taken_at=NOW.replace(tzinfo=None))


def test_host_facts_ride_on_every_beat():
    # Sinon une montée de version d'OS ou d'agent reste invisible dans
    # l'inventaire jusqu'à un réenrôlement, qui n'arrive jamais.
    payload = hb.build_payload(SAMPLE, HOST, taken_at=NOW)
    assert payload["hostname"] == "web-01.prod"
    assert payload["os"] == "Linux"
    assert payload["agent_version"]


def test_config_version_is_omitted_when_unknown():
    assert "config_version" not in hb.build_payload(SAMPLE, HOST, taken_at=NOW)
    assert hb.build_payload(SAMPLE, HOST, taken_at=NOW, config_version=3)["config_version"] == 3


# ------------------------------------------------------------------- envoi


def test_beat_authenticates_with_the_raw_key():
    session = _Session(_ok())
    hb.send(CONFIG, CREDS, hb.build_payload(SAMPLE, HOST, taken_at=NOW), session=session)
    call = session.calls[0]
    assert call["url"] == "https://plateforme.cbc:8443/api/agents/heartbeat"
    assert call["headers"]["Authorization"] == "cle-secrete"


def test_unreachable_platform_is_a_refusal_not_a_crash():
    session = _Session(raises=requests.exceptions.ConnectionError("coupure"))
    with pytest.raises(hb.HeartbeatRefused):
        hb.send(CONFIG, CREDS, {}, session=session)


def test_a_401_is_identity_lost():
    session = _Session(_Response(401, {"detail": "Agent inconnu"}))
    with pytest.raises(hb.IdentityLost):
        hb.send(CONFIG, CREDS, {}, session=session)


@pytest.mark.parametrize("status", [403, 404])
def test_403_and_404_are_not_identity_loss(status):
    # 403 = hôte révoqué par un administrateur : s'en servir pour se
    # réenrôler ferait rentrer par la fenêtre une machine qu'on vient de
    # sortir du parc. 404 = URL de base fautive, qui deviendrait une boucle
    # de réenrôlement perpétuelle.
    session = _Session(_Response(status, {"detail": "non"}))
    with pytest.raises(hb.HeartbeatRefused) as exc:
        hb.send(CONFIG, CREDS, {}, session=session)
    assert not isinstance(exc.value, hb.IdentityLost)


def test_a_validation_error_names_the_field():
    session = _Session(
        _Response(422, {"detail": [{"loc": ["body", "cpu_percent"], "msg": "0..100"}]})
    )
    with pytest.raises(hb.HeartbeatRefused) as exc:
        hb.send(CONFIG, CREDS, {}, session=session)
    assert "cpu_percent" in str(exc.value)


def test_a_missing_echo_does_not_break_the_beat():
    session = _Session(_Response(200, {"status": "success"}))
    result = hb.send(CONFIG, CREDS, {}, session=session)
    assert result.echo.agent_id is None
    assert result.config is None
    assert result.tasks == []


# -------------------------------------------------------------------- écho


def test_resume_after_outage_is_surfaced():
    session = _Session(_ok(resumed_after_outage=True, previous_gap_seconds=740))
    result = hb.send(CONFIG, CREDS, {}, session=session)
    assert result.echo.resumed_after_outage is True
    assert result.echo.previous_gap_seconds == 740


def test_clock_skew_is_read_as_int_or_float():
    # Un test `isinstance(skew, int)` laissait passer un flottant en silence.
    for value in (150, 150.5):
        result = hb.send(CONFIG, CREDS, {}, session=_Session(_ok(clock_skew_seconds=value)))
        assert result.echo.clock_skew_seconds == pytest.approx(float(value))


def test_a_diverging_identifier_is_adopted():
    # Garder un identifiant périmé ferait désigner à chaque envoi une ligne
    # qui n'existe plus côté plateforme.
    result = hb.send(CONFIG, CREDS, {}, session=_Session(_ok(agent_id="B7C120")))
    adopted = hb.interpret(result, CREDS)
    assert adopted.agent_id == "B7C120"
    assert adopted.auth_key == CREDS.auth_key


def test_a_matching_identifier_changes_nothing():
    result = hb.send(CONFIG, CREDS, {}, session=_Session(_ok()))
    assert hb.interpret(result, CREDS) == CREDS


def test_offered_config_version_is_read_defensively():
    session = _Session(
        _Response(200, {"echo": {}, "config": {"version": 7, "payload": {"a": 1}}})
    )
    assert hb.send(CONFIG, CREDS, {}, session=session).offered_config_version == 7

    # Une forme inattendue ne doit pas faire lever une exception dans la
    # boucle : le battement a réussi, c'est ce qui compte pour la présence.
    for shape in (None, [], {"payload": {}}, {"version": "sept"}):
        s = _Session(_Response(200, {"echo": {}, "config": shape}))
        assert hb.send(CONFIG, CREDS, {}, session=s).offered_config_version is None


def test_skew_warning_threshold_is_honoured(caplog):
    result = hb.send(CONFIG, CREDS, {}, session=_Session(_ok(clock_skew_seconds=300)))
    with caplog.at_level("WARNING"):
        hb.interpret(result, CREDS)
    assert any("Horloge" in r.message for r in caplog.records)


def test_a_small_skew_is_not_reported(caplog):
    result = hb.send(CONFIG, CREDS, {}, session=_Session(_ok(clock_skew_seconds=3)))
    with caplog.at_level("WARNING"):
        hb.interpret(result, CREDS)
    assert not any("Horloge" in r.message for r in caplog.records)


def test_gap_seconds_survives_a_long_outage():
    gap = int(timedelta(hours=6).total_seconds())
    result = hb.send(
        CONFIG, CREDS, {}, session=_Session(_ok(resumed_after_outage=True, previous_gap_seconds=gap))
    )
    assert result.echo.previous_gap_seconds == gap
