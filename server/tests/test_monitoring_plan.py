"""Plan de supervision par hôte : paramétrage, évaluation, alertes (points 6-7).

Ce qui existait avant ce lot : rien de fonctionnel. `check_service_alerts`
comparait à `critical_services = []` et `check_file_alerts` à
`monitored_files = []` — deux listes vides codées en dur avec un `TODO`.
Aucune alerte de service ou de fichier n'a jamais pu être levée, et les
endpoints de configuration renvoyaient la requête en écho sans rien
persister pendant que l'interface affichait « mise à jour avec succès ».
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src import monitoring_plan  # noqa: E402
from src.alert_service import AlertService  # noqa: E402
from src.database import Base  # noqa: E402
from src.models import (  # noqa: E402
    Agent,
    Alert,
    AlertStatus,
    AlertType,
    FileCondition,
    MachineType,
    MonitoredFile,
    MonitoredService,
    ServiceState,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def agent(db):
    row = Agent(
        id="A3F09C",
        machine_id=f"mid-{uuid.uuid4().hex[:8]}",
        hostname="SRV-SWIFT-01",
        auth_key=str(uuid.uuid4()),
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
    )
    db.add(row)
    db.commit()
    return row


def _open_alerts(db, alert_type):
    return (
        db.query(Alert)
        .filter(Alert.type == alert_type, Alert.status == AlertStatus.OPEN)
        .all()
    )


# ---------------------------------------------------------- plan persistant


def test_plan_is_actually_persisted(db, agent):
    """Le paramétrage doit survivre — c'est précisément ce qui manquait."""
    monitoring_plan.replace_plan(
        db,
        agent,
        {
            "cpu": {"warning": 70, "critical": 85},
            "services": [{"name": "swift-gateway", "expected_state": "running"}],
            "files": [{"path": "/var/run/swift.lock", "condition": "must_exist"}],
        },
    )

    stored = monitoring_plan.get_plan(db, agent)
    assert stored["cpu"]["warning"] == 70
    assert [s["name"] for s in stored["services"]] == ["swift-gateway"]
    assert [f["path"] for f in stored["files"]] == ["/var/run/swift.lock"]


def test_empty_service_list_is_a_valid_plan(db, agent):
    """« La liste des services peut être nulle » — cas explicitement demandé."""
    monitoring_plan.replace_plan(db, agent, {"services": [{"name": "nginx"}]})
    assert len(monitoring_plan.get_plan(db, agent)["services"]) == 1

    monitoring_plan.replace_plan(db, agent, {"services": []})
    assert monitoring_plan.get_plan(db, agent)["services"] == []


def test_absent_section_leaves_the_rest_untouched(db, agent):
    """Régler les services ne doit pas effacer les seuils déjà posés."""
    monitoring_plan.replace_plan(db, agent, {"cpu": {"warning": 60, "critical": 80}})
    monitoring_plan.replace_plan(db, agent, {"services": [{"name": "cron"}]})

    plan = monitoring_plan.get_plan(db, agent)
    assert plan["cpu"]["warning"] == 60
    assert len(plan["services"]) == 1


def test_each_change_bumps_the_version(db, agent):
    """La version pilote le push : sans incrément, l'agent ne saurait rien."""
    assert monitoring_plan.get_plan(db, agent)["version"] == 0
    monitoring_plan.replace_plan(db, agent, {"services": []})
    assert monitoring_plan.get_plan(db, agent)["version"] == 1
    monitoring_plan.replace_plan(db, agent, {"files": []})
    assert monitoring_plan.get_plan(db, agent)["version"] == 2


def test_unacked_plan_is_pending_then_settles(db, agent):
    assert monitoring_plan.pending_for_agent(db, agent) is None

    monitoring_plan.replace_plan(db, agent, {"services": [{"name": "sshd"}]})
    pending = monitoring_plan.pending_for_agent(db, agent)
    assert pending is not None
    assert pending["payload"]["services_monitoring"]["services"] == ["sshd"]

    monitoring_plan.ack(db, agent, pending["version"])
    assert monitoring_plan.pending_for_agent(db, agent) is None


def test_agent_payload_only_says_what_to_look_at(db, agent):
    """L'agent observe et rapporte ; il ne connaît pas l'état attendu.

    L'évaluation reste côté plateforme, où vivent le plan et l'historique.
    """
    monitoring_plan.replace_plan(
        db,
        agent,
        {"services": [{"name": "nginx", "expected_state": "stopped"}]},
    )
    payload = monitoring_plan.agent_config_payload(db, agent)
    assert payload["services_monitoring"]["services"] == ["nginx"]
    assert "expected_state" not in str(payload["services_monitoring"])


# ------------------------------------------------------------------ services


def test_service_stopped_when_expected_running_raises_an_alert(db, agent):
    monitoring_plan.replace_plan(
        db, agent, {"services": [{"name": "swift-gateway", "expected_state": "running"}]}
    )
    AlertService.check_service_alerts(
        db, agent.id, [{"name": "swift-gateway", "status": "stopped"}]
    )
    alerts = _open_alerts(db, AlertType.SERVICE_DOWN)
    assert len(alerts) == 1
    assert alerts[0].target == "swift-gateway"


def test_service_running_when_expected_stopped_also_raises(db, agent):
    """Le sens inverse — un service de test rallumé en production.

    Ce cas n'existait nulle part : seul « arrêté » était envisagé.
    """
    monitoring_plan.replace_plan(
        db, agent, {"services": [{"name": "debug-agent", "expected_state": "stopped"}]}
    )
    AlertService.check_service_alerts(
        db, agent.id, [{"name": "debug-agent", "status": "running"}]
    )
    alerts = _open_alerts(db, AlertType.SERVICE_DOWN)
    assert len(alerts) == 1
    assert "attendu stopped" in alerts[0].message


def test_two_failing_services_produce_two_alerts(db, agent):
    """Régression : la déduplication portait sur le type, pas sur le service.

    Le deuxième service tombé était donc silencieusement absorbé par le
    premier — on croyait un seul incident là où il y en avait deux.
    """
    monitoring_plan.replace_plan(
        db, agent, {"services": [{"name": "svc-a"}, {"name": "svc-b"}]}
    )
    AlertService.check_service_alerts(
        db,
        agent.id,
        [{"name": "svc-a", "status": "stopped"}, {"name": "svc-b", "status": "stopped"}],
    )
    assert {a.target for a in _open_alerts(db, AlertType.SERVICE_DOWN)} == {"svc-a", "svc-b"}


def test_service_alert_closes_when_it_comes_back(db, agent):
    monitoring_plan.replace_plan(db, agent, {"services": [{"name": "svc-a"}]})
    AlertService.check_service_alerts(db, agent.id, [{"name": "svc-a", "status": "stopped"}])
    assert len(_open_alerts(db, AlertType.SERVICE_DOWN)) == 1

    AlertService.check_service_alerts(db, agent.id, [{"name": "svc-a", "status": "running"}])
    assert _open_alerts(db, AlertType.SERVICE_DOWN) == []


def test_unknown_service_state_is_not_an_alert(db, agent):
    """Interroger le gestionnaire a échoué : on ne sait rien, on n'alerte pas."""
    monitoring_plan.replace_plan(db, agent, {"services": [{"name": "svc-a"}]})
    AlertService.check_service_alerts(db, agent.id, [{"name": "svc-a", "status": "unknown"}])
    assert _open_alerts(db, AlertType.SERVICE_DOWN) == []


def test_unmonitored_service_is_recorded_but_never_alerts(db, agent):
    """L'inventaire recense tout ; la surveillance ne porte que sur le plan."""
    AlertService.check_service_alerts(db, agent.id, [{"name": "cups", "status": "stopped"}])
    assert _open_alerts(db, AlertType.SERVICE_DOWN) == []


# ------------------------------------------------------------------ fichiers


def test_missing_required_file_raises(db, agent):
    monitoring_plan.replace_plan(
        db, agent, {"files": [{"path": "/var/log/swift.log", "condition": "must_exist"}]}
    )
    AlertService.check_file_alerts(db, agent.id, [{"path": "/var/log/swift.log", "exists": False}])
    alerts = _open_alerts(db, AlertType.FILE_ANOMALY)
    assert len(alerts) == 1
    assert "manquant" in alerts[0].message


def test_forbidden_file_present_raises(db, agent):
    """« Si il existe / si il n'existe pas faire une alerte » — le second sens.

    Un drapeau d'erreur ou un fichier de blocage dont l'apparition *est*
    l'incident. Aucune notion de ce genre n'existait auparavant.
    """
    monitoring_plan.replace_plan(
        db, agent, {"files": [{"path": "/var/run/BLOCKED", "condition": "must_not_exist"}]}
    )
    AlertService.check_file_alerts(db, agent.id, [{"path": "/var/run/BLOCKED", "exists": True}])
    alerts = _open_alerts(db, AlertType.FILE_ANOMALY)
    assert len(alerts) == 1
    assert "interdit" in alerts[0].message


def test_satisfied_condition_raises_nothing(db, agent):
    monitoring_plan.replace_plan(
        db,
        agent,
        {
            "files": [
                {"path": "/var/log/swift.log", "condition": "must_exist"},
                {"path": "/var/run/BLOCKED", "condition": "must_not_exist"},
            ]
        },
    )
    AlertService.check_file_alerts(
        db,
        agent.id,
        [
            {"path": "/var/log/swift.log", "exists": True},
            {"path": "/var/run/BLOCKED", "exists": False},
        ],
    )
    assert _open_alerts(db, AlertType.FILE_ANOMALY) == []


def test_undecidable_state_neither_opens_nor_closes(db, agent):
    """Droits insuffisants : le dernier verdict connu doit tenir.

    Traiter l'indécidable comme une absence éteindrait à tort une alerte
    « fichier interdit » — le fichier serait peut-être toujours là.
    """
    monitoring_plan.replace_plan(
        db, agent, {"files": [{"path": "/var/run/BLOCKED", "condition": "must_not_exist"}]}
    )
    AlertService.check_file_alerts(db, agent.id, [{"path": "/var/run/BLOCKED", "exists": True}])
    assert len(_open_alerts(db, AlertType.FILE_ANOMALY)) == 1

    AlertService.check_file_alerts(db, agent.id, [{"path": "/var/run/BLOCKED", "exists": None}])
    assert len(_open_alerts(db, AlertType.FILE_ANOMALY)) == 1, "l'alerte a été éteinte à tort"


def test_two_files_produce_two_alerts(db, agent):
    monitoring_plan.replace_plan(
        db, agent, {"files": [{"path": "/a.log"}, {"path": "/b.log"}]}
    )
    AlertService.check_file_alerts(
        db, agent.id, [{"path": "/a.log", "exists": False}, {"path": "/b.log", "exists": False}]
    )
    assert {a.target for a in _open_alerts(db, AlertType.FILE_ANOMALY)} == {"/a.log", "/b.log"}


def test_oversize_file_raises_with_measured_value(db, agent):
    monitoring_plan.replace_plan(
        db, agent, {"files": [{"path": "/var/log/big.log", "max_size_mb": 10}]}
    )
    AlertService.check_file_alerts(
        db,
        agent.id,
        [{"path": "/var/log/big.log", "exists": True, "size_bytes": 25 * 1024 * 1024}],
    )
    alerts = _open_alerts(db, AlertType.FILE_ANOMALY)
    assert len(alerts) == 1
    assert alerts[0].value == pytest.approx(25.0, abs=0.1)
    assert alerts[0].threshold == 10.0
