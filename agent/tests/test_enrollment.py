"""Enrôlement (point 1).

Les cas couverts sont ceux qui coûtent cher sur site : un jeton absent, une
plateforme injoignable, un certificat refusé, un refus de la plateforme, et
surtout le double enrôlement — qui consommerait un second jeton et créerait un
doublon dans l'inventaire pour la même machine.
"""

from __future__ import annotations

import json

import pytest
import requests

from config import AgentConfig
from enrollment import (
    Credentials,
    EnrollmentError,
    build_payload,
    enroll,
    is_enrolled,
    read_credentials,
    write_credentials,
)
from facts import HostFacts

CONFIG = AgentConfig(
    server_url="https://plateforme.cbc:8443",
    enrollment_token="jeton-a-usage-unique",
    tls_verify=True,
    machine_type="server",
    timeout_seconds=5,
)

HOST = HostFacts(
    hostname="web-01.prod",
    os="Linux",
    os_version="5.15.0",
    ip_address="10.0.0.12",
    cpu_cores=4,
    ram_total_gb=15.5,
    disk_total_gb=200.0,
    runtime={"executable": "/usr/bin/python3", "frozen": False, "agent_version": "2.0.0-dev"},
)

MACHINE = "550e8400-e29b-41d4-a716-446655440000"


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload


class _Session:
    """Session HTTP factice : enregistre l'appel, rend la réponse posée."""

    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, timeout=None, verify=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "verify": verify})
        if self.raises:
            raise self.raises
        return self.response


def _ok():
    return _Session(_Response(200, {"agent_id": "A3F09C", "auth_key": "cle-secrete", "message": "ok"}))


def test_payload_matches_the_platform_contract():
    payload = build_payload(CONFIG, MACHINE, HOST)
    for required in ("token", "machine_id", "hostname", "os", "agent_version", "machine_type"):
        assert payload[required], "champ requis manquant : %s" % required
    assert payload["machine_type"] in ("server", "workstation")
    assert payload["cpu_cores"] == 4


def test_unmeasured_hardware_is_omitted_not_zeroed():
    bare = HostFacts(
        hostname="poste-01", os="Windows", os_version="10", ip_address=None,
        cpu_cores=None, ram_total_gb=None, disk_total_gb=None, runtime={},
    )
    payload = build_payload(CONFIG, MACHINE, bare)
    # La plateforme contraint les chaînes optionnelles : envoyer None sur
    # ip_address la ferait échouer en 422. Absent veut dire non mesuré.
    for absent in ("ip_address", "cpu_cores", "ram_total_gb", "disk_total_gb", "runtime"):
        assert absent not in payload


def test_successful_enrolment_keeps_the_assigned_identifier():
    session = _ok()
    creds = enroll(CONFIG, MACHINE, HOST, session=session)

    assert creds.agent_id == "A3F09C"
    assert session.calls[0]["url"] == "https://plateforme.cbc:8443/api/agents/enroll"
    assert session.calls[0]["verify"] is True
    # Relu depuis le disque : c'est ce qui rend le heartbeat possible au
    # prochain démarrage.
    assert read_credentials() == Credentials("A3F09C", "cle-secrete")
    assert is_enrolled()


def test_enrolment_without_a_token_is_refused_before_any_request():
    session = _ok()
    naked = AgentConfig(
        server_url=CONFIG.server_url, enrollment_token="", tls_verify=True,
        machine_type="server", timeout_seconds=5,
    )
    with pytest.raises(EnrollmentError) as exc:
        enroll(naked, MACHINE, HOST, session=session)

    assert "jeton" in str(exc.value).lower()
    assert session.calls == [], "aucun appel ne doit partir sans jeton"


def test_platform_refusal_is_reported_verbatim():
    session = _Session(_Response(401, {"detail": "Jeton d'enrôlement invalide ou déjà utilisé"}))
    with pytest.raises(EnrollmentError) as exc:
        enroll(CONFIG, MACHINE, HOST, session=session)
    assert "déjà utilisé" in str(exc.value)
    assert not is_enrolled(), "un refus ne doit rien écrire sur le disque"


def test_validation_error_names_the_offending_field():
    session = _Session(_Response(422, {"detail": [{"loc": ["body", "hostname"], "msg": "Hostname invalide"}]}))
    with pytest.raises(EnrollmentError) as exc:
        enroll(CONFIG, MACHINE, HOST, session=session)
    assert "hostname" in str(exc.value)


def test_unreachable_platform_names_the_address():
    session = _Session(raises=requests.exceptions.ConnectionError("refus de connexion"))
    with pytest.raises(EnrollmentError) as exc:
        enroll(CONFIG, MACHINE, HOST, session=session)
    assert "plateforme.cbc" in str(exc.value)
    assert not is_enrolled()


def test_rejected_certificate_points_at_the_certificate_authority():
    session = _Session(raises=requests.exceptions.SSLError("certificat auto-signé"))
    with pytest.raises(EnrollmentError) as exc:
        enroll(CONFIG, MACHINE, HOST, session=session)
    assert "certificat" in str(exc.value).lower()


def test_unparseable_response_does_not_pass_for_success():
    session = _Session(_Response(200, {"message": "ok"}))  # ni agent_id ni auth_key
    with pytest.raises(EnrollmentError):
        enroll(CONFIG, MACHINE, HOST, session=session)
    assert not is_enrolled()


def test_credentials_round_trip(isolated_state):
    path = isolated_state / "credentials.json"
    write_credentials(Credentials("A3F09C", "cle"), path)
    assert read_credentials(path) == Credentials("A3F09C", "cle")


def test_truncated_credentials_read_as_absent(isolated_state):
    path = isolated_state / "credentials.json"
    path.write_text(json.dumps({"agent_id": "A3F09C"}), encoding="utf-8")
    # Une clé manquante rend le fichier inutilisable : mieux vaut réenrôler
    # que partir avec une authentification qui échouera à chaque appel.
    assert read_credentials(path) is None
