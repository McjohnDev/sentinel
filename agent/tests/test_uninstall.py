"""Désinstallation et signalement du désenrôlement (point 4).

Le signalement est ce qui distingue un retrait *voulu* d'une *panne*. Sans
lui, une machine désinstallée reste « hors ligne » au parc et continue de
déclencher des alertes pour une absence décidée — bruit d'exploitation
indistinguable d'un vrai incident.

D'où la règle appliquée ici : les jetons ne sont pas effacés tant que la
plateforme n'a pas été prévenue, sauf demande explicite.
"""

from __future__ import annotations

import pytest
import requests

from config import AgentConfig
from enrollment import (
    Credentials,
    DeregistrationError,
    clear_credentials,
    deregister,
    is_enrolled,
    read_credentials,
    write_credentials,
)
from identity import load_or_create_machine_id, read_machine_id

CONFIG = AgentConfig(
    server_url="https://plateforme.cbc:8443",
    enrollment_token="",
    tls_verify=True,
    machine_type="server",
    timeout_seconds=5,
)

CREDS = Credentials(agent_id="A3F09C", auth_key="cle-secrete")


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload


class _Session:
    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "verify": verify})
        if self.raises:
            raise self.raises
        return self.response


def test_deregistration_authenticates_with_the_agent_key():
    session = _Session(_Response(200, {"message": "ok"}))

    deregister(CONFIG, CREDS, session=session)

    call = session.calls[0]
    assert call["url"] == "https://plateforme.cbc:8443/api/agents/deregister"
    # La route agent attend la cle brute, pas un « Bearer » : verify_agent
    # compare Authorization a Agent.auth_key tel quel.
    assert call["headers"]["Authorization"] == "cle-secrete"


def test_a_reason_reaches_the_platform():
    session = _Session(_Response(200, {"message": "ok"}))
    deregister(CONFIG, CREDS, reason="poste réformé", session=session)
    assert session.calls[0]["json"] == {"reason": "poste réformé"}


def test_no_reason_sends_an_empty_body():
    session = _Session(_Response(200, {"message": "ok"}))
    deregister(CONFIG, CREDS, session=session)
    assert session.calls[0]["json"] == {}


def test_an_unreachable_platform_is_reported_not_swallowed():
    session = _Session(raises=requests.exceptions.ConnectionError("refus"))
    with pytest.raises(DeregistrationError) as exc:
        deregister(CONFIG, CREDS, session=session)
    assert "plateforme.cbc" in str(exc.value)


def test_a_refusal_is_reported():
    session = _Session(_Response(404, {"detail": "Agent non trouvé"}))
    with pytest.raises(DeregistrationError) as exc:
        deregister(CONFIG, CREDS, session=session)
    assert "non trouv" in str(exc.value)


def test_clearing_credentials_keeps_the_machine_identity():
    # Le point central du point 4 : la plateforme reconnait un hote par son
    # identite machine. L'effacer ferait d'une reinstallation un second hote,
    # avec un historique coupe en deux.
    machine = load_or_create_machine_id()
    write_credentials(CREDS)
    assert is_enrolled()

    clear_credentials()

    assert not is_enrolled()
    assert read_machine_id() == machine


def test_clearing_twice_is_not_an_error():
    clear_credentials()
    clear_credentials()
    assert read_credentials() is None
