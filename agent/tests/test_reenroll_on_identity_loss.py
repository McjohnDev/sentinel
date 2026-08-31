"""L'agent doit repartir sur un enrôlement quand la plateforme ne le connaît plus.

Régression : après une purge d'inventaire côté serveur, l'agent tournait
toujours mais rejouait indéfiniment une clé d'authentification morte. Il
restait invisible du parc alors que le processus était bien vivant, en
accumulant des heartbeats sur disque.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent as agent_module  # noqa: E402
from agent import CBCAgent  # noqa: E402


class _FakeResponse:
    """Réponse HTTP minimale : statut, en-têtes, corps JSON."""

    def __init__(self, status_code: int, headers: dict | None = None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body
        self.text = "" if body is None else str(body)

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture
def agent(monkeypatch, tmp_path):
    """Agent instancié sans toucher au réseau ni au disque du poste."""
    inst = CBCAgent.__new__(CBCAgent)
    inst.server_url = "http://server:8000"
    inst.auth_key = "clé-obsolète"
    inst.agent_id = "agt-fantôme"
    inst.tls_verify = False
    inst.retries = 0
    inst.logger = SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )
    return inst


def _post_returning(monkeypatch, response):
    monkeypatch.setattr(agent_module.requests, "post", lambda *a, **k: response)


@pytest.mark.parametrize("status_code", [401, 403, 404, 410])
def test_identity_loss_statuses_map_to_auth(agent, monkeypatch, status_code):
    """404/410 comptent aussi : la ligne a disparu, réessayer ne sert à rien."""
    _post_returning(monkeypatch, _FakeResponse(status_code))
    _resp, outcome, _err = agent._post("/api/agents/ping", {})
    assert outcome == "auth"


def test_reenroll_header_forces_auth_outcome(agent, monkeypatch):
    """La plateforme peut réclamer un ré-enrôlement sur n'importe quel statut."""
    _post_returning(monkeypatch, _FakeResponse(503, headers={"X-CBC-Reenroll": "1"}))
    _resp, outcome, _err = agent._post("/api/agents/heartbeat", {})
    assert outcome == "auth"


def test_reenroll_code_in_body_forces_auth_outcome(agent, monkeypatch):
    body = {"detail": {"detail": "Authentification invalide", "code": "agent_unknown"}}
    _post_returning(monkeypatch, _FakeResponse(500, body=body))
    _resp, outcome, _err = agent._post("/api/agents/ping", {})
    assert outcome == "auth"


def test_plain_server_error_stays_retryable(agent, monkeypatch):
    """Un 500 sans signal reste une panne passagère : on ne jette pas l'identité."""
    _post_returning(monkeypatch, _FakeResponse(500, body={"detail": "boom"}))
    _resp, outcome, _err = agent._post("/api/agents/heartbeat", {})
    assert outcome == "fail"


def test_ping_rejection_clears_identity(agent, monkeypatch):
    """Après un rejet, plus de clé NI d'agent_id : la boucle ré-enrôle."""
    _post_returning(monkeypatch, _FakeResponse(401, headers={"X-CBC-Reenroll": "1"}))
    monkeypatch.setattr(agent, "_persist_session", lambda **kwargs: None)

    assert agent.send_ping() == "auth"
    assert agent.auth_key is None
    assert agent.agent_id is None, "un agent_id périmé étiquetterait les métriques bufferisées"
