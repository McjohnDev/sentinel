"""Réception du plan de supervision (point 6, côté agent).

La plateforme décide quoi surveiller ; le plan descend dans la réponse au
battement. Deux obligations, et rien ne marche si l'une manque : le conserver
sur l'hôte, et l'acquitter. Sans accusé, la plateforme le republie à chaque
battement indéfiniment.
"""

from __future__ import annotations

import json

import pytest
import requests

import plan as plan_module
from config import AgentConfig
from enrollment import Credentials

CONFIG = AgentConfig(
    server_url="https://plateforme.cbc:8443",
    enrollment_token="",
    tls_verify=True,
    machine_type="server",
    timeout_seconds=5,
)
CREDS = Credentials(agent_id="A3F09C", auth_key="cle-secrete")

PAYLOAD = {
    "monitoring": {
        "cpu": {"warning": 80, "critical": 90},
        "ram": {"warning": 80, "critical": 90},
        "disk": {"partitions": [{"mount": "/u01", "warning": 85, "critical": 95}]},
        "services": [{"name": "swift-alliance", "expected_state": "running"}],
        "files": [{"path": "/var/lock/cbc.flag", "condition": "must_not_exist"}],
    }
}


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


class _Session:
    def __init__(self, status=200, raises=None):
        self.status = status
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.raises:
            raise self.raises
        return _Response(self.status)


# --------------------------------------------------------------- stockage


def test_a_plan_survives_a_restart():
    # C'est quand la liaison est rompue qu'il faut continuer à surveiller ce
    # qui a été demandé.
    plan_module.write_plan(7, PAYLOAD)
    stored = plan_module.read_plan()
    assert stored.version == 7
    assert stored.payload == PAYLOAD


def test_no_plan_yet_reads_as_absent():
    assert plan_module.read_plan() is None
    assert plan_module.current_version() is None


def test_a_corrupted_plan_reads_as_absent(isolated_state):
    path = isolated_state / "monitoring-plan.json"
    path.write_text("{ceci n'est pas du JSON", encoding="utf-8")
    assert plan_module.read_plan(path) is None


def test_a_plan_missing_its_version_is_refused(isolated_state):
    path = isolated_state / "monitoring-plan.json"
    path.write_text(json.dumps({"payload": PAYLOAD}), encoding="utf-8")
    assert plan_module.read_plan(path) is None


def test_writing_leaves_no_temporary_file_behind(isolated_state):
    plan_module.write_plan(3, PAYLOAD)
    assert not (isolated_state / "monitoring-plan.tmp").exists()


# ------------------------------------------------------------- acquittement


def test_applying_a_plan_stores_it_then_acknowledges():
    session = _Session()

    applied = plan_module.apply_offered(CONFIG, CREDS, {"version": 4, "payload": PAYLOAD}, session=session)

    assert applied == 4
    assert plan_module.current_version() == 4
    call = session.calls[0]
    assert call["url"] == "https://plateforme.cbc:8443/api/agents/config/ack"
    assert call["json"] == {"version": 4}
    assert call["headers"]["Authorization"] == "cle-secrete"


def test_the_plan_is_written_before_it_is_acknowledged():
    """Acquitter une version non rangée la ferait disparaître.

    La plateforme cesserait de la pousser alors que l'hôte ne l'a jamais
    reçue, et l'écart ne se découvrirait qu'au prochain incident.
    """
    seen = {}

    class _Checking(_Session):
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            seen["version_on_disk"] = plan_module.current_version()
            return super().post(url, json=json, headers=headers)

    plan_module.apply_offered(CONFIG, CREDS, {"version": 9, "payload": PAYLOAD}, session=_Checking())

    assert seen["version_on_disk"] == 9


def test_a_lost_acknowledgement_does_not_lose_the_plan():
    # Un accusé perdu n'est pas grave : la plateforme repoussera. Faire
    # échouer le cycle priverait l'hôte de sa présence, ce qui l'est.
    session = _Session(raises=requests.exceptions.ConnectionError("coupure"))

    applied = plan_module.apply_offered(CONFIG, CREDS, {"version": 5, "payload": PAYLOAD}, session=session)

    assert applied == 5
    assert plan_module.current_version() == 5


def test_a_refused_acknowledgement_does_not_lose_the_plan():
    applied = plan_module.apply_offered(
        CONFIG, CREDS, {"version": 5, "payload": PAYLOAD}, session=_Session(status=500)
    )
    assert applied == 5
    assert plan_module.current_version() == 5


def test_an_already_applied_version_is_not_rewritten_but_is_re_acknowledged():
    plan_module.write_plan(6, PAYLOAD)
    session = _Session()

    applied = plan_module.apply_offered(
        CONFIG, CREDS, {"version": 6, "payload": {"autre": True}}, session=session
    )

    assert applied == 6
    # Le contenu n'a pas bougé : la version fait foi.
    assert plan_module.read_plan().payload == PAYLOAD
    # Mais on ré-acquitte, au cas où le précédent accusé se soit perdu.
    assert session.calls[0]["json"] == {"version": 6}


def test_an_older_version_never_overwrites_a_newer_one():
    plan_module.write_plan(10, PAYLOAD)
    plan_module.apply_offered(CONFIG, CREDS, {"version": 2, "payload": {}}, session=_Session())
    assert plan_module.current_version() == 10


@pytest.mark.parametrize(
    "offered",
    [None, {}, [], {"payload": {}}, {"version": "sept", "payload": {}}, {"version": 3}],
)
def test_a_malformed_offer_is_ignored_without_crashing(offered):
    # Le battement a réussi : c'est ce qui compte pour la présence. Une forme
    # inattendue ne doit pas rompre la boucle.
    session = _Session()
    assert plan_module.apply_offered(CONFIG, CREDS, offered, session=session) is None
    assert session.calls == []
