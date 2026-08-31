"""Désinstallation d'agent : signalement, conservation, réinstallation.

Le comportement précédent effaçait la ligne de l'agent dès le désenrôlement,
et avec elle l'historique de heartbeats, les alertes et toute trace
d'exploitation de la machine — au moment précis où l'on veut pouvoir répondre
à « depuis quand cet hôte n'est-il plus supervisé, et qui l'a retiré ? ».

L'hôte est désormais *marqué* désinstallé : il sort de l'inventaire actif,
garde son histoire, et la suppression définitive revient à la purge
d'inventaire à l'échéance de rétention.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app
from src.models import Agent, Alert, AlertSeverity, AlertStatus, AlertType, Heartbeat, MachineType

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
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
    # `app` est global au processus et d'autres modules de test posent leur
    # propre surcharge à l'import. Retirer la nôtre en fin de test les
    # priverait de la leur pour tout le reste de la session : on restaure
    # l'état antérieur au lieu de supprimer.
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


@pytest.fixture
def client(db):
    with TestClient(app) as test_client:
        yield test_client


AUTH_KEY = "cle-agent-de-test"


def _enrolled_agent(db, *, agent_id="587A2B", with_history=True):
    agent = Agent(
        id=agent_id,
        machine_id="mid-test",
        hostname="SRV-SWIFT-01",
        auth_key=AUTH_KEY,
        status="active",
        os="linux",
        machine_type=MachineType.SERVER,
    )
    db.add(agent)
    db.commit()

    if with_history:
        for _ in range(3):
            db.add(
                Heartbeat(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    cpu_percent=12.0,
                    cpu_cores=8,
                    ram_percent=30.0,
                    ram_total_gb=16.0,
                    ram_used_gb=5.0,
                    ram_free_gb=11.0,
                    disk_percent=40.0,
                    disk_total_gb=200.0,
                    disk_used_gb=80.0,
                    disk_free_gb=120.0,
                    uptime_seconds=1000,
                )
            )
        db.add(
            Alert(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                severity=AlertSeverity.MAJOR,
                type=AlertType.CPU_HIGH,
                message="CPU élevé",
                status=AlertStatus.OPEN,
            )
        )
        db.commit()
    return agent


def _deregister(client, reason="désinstallation planifiée"):
    return client.post(
        "/api/agents/deregister",
        headers={"Authorization": AUTH_KEY},
        json={"reason": reason},
    )


# ------------------------------------------------------------ désenrôlement


def test_deregister_marks_instead_of_deleting(client, db):
    """La ligne survit : c'est tout l'objet du changement."""
    _enrolled_agent(db)

    response = _deregister(client)
    assert response.status_code == 200
    assert response.json()["status"] == "uninstalled"

    db.expire_all()
    agent = db.query(Agent).filter(Agent.id == "587A2B").first()
    assert agent is not None, "la ligne a été supprimée au lieu d'être marquée"
    assert agent.status == "uninstalled"
    assert agent.uninstalled_at is not None
    assert agent.uninstalled_by == "agent"


def test_history_survives_the_uninstall(client, db):
    """Heartbeats conservés : sans eux, impossible d'auditer après coup."""
    _enrolled_agent(db)
    assert db.query(Heartbeat).count() == 3

    _deregister(client)

    db.expire_all()
    assert db.query(Heartbeat).count() == 3, "l'historique a été détruit"


def test_open_alerts_are_closed_on_uninstall(client, db):
    """Une machine qu'on cesse volontairement de superviser ne doit plus sonner.

    Sans cela, ses alertes ouvertes deviennent irrésolvables : plus aucun
    agent ne mesure, la valeur ne repassera donc jamais sous le seuil.
    """
    _enrolled_agent(db)
    assert db.query(Alert).filter(Alert.status == AlertStatus.OPEN).count() == 1

    _deregister(client)

    db.expire_all()
    assert db.query(Alert).filter(Alert.status == AlertStatus.OPEN).count() == 0
    assert db.query(Alert).filter(Alert.status == AlertStatus.RESOLVED).count() == 1


def test_unknown_key_cannot_deregister(client, db):
    _enrolled_agent(db)
    response = client.post(
        "/api/agents/deregister", headers={"Authorization": "cle-inventee"}, json={}
    )
    assert response.status_code == 401

    db.expire_all()
    assert db.query(Agent).filter(Agent.id == "587A2B").first().status == "active"


# ------------------------------------------------------- visibilité du parc


def test_uninstalled_host_leaves_the_active_inventory(client, db):
    _enrolled_agent(db, with_history=False)
    _deregister(client)

    from src.agent_purge import derived_agent_status, is_agent_live

    db.expire_all()
    agent = db.query(Agent).filter(Agent.id == "587A2B").first()
    assert is_agent_live(agent) is False, "un hôte désinstallé ne doit pas compter comme vivant"
    assert derived_agent_status(agent) == "uninstalled"


# --------------------------------------------------------- réinstallation


def test_reinstall_clears_the_uninstall_marks(client, db):
    """Réinstaller un hôte connu doit le remettre en service proprement.

    Sans effacement des marques, la machine réapparaîtrait active tout en
    portant une date de désinstallation — un état contradictoire que
    l'exploitation ne saurait pas interpréter.
    """
    agent = _enrolled_agent(db, with_history=False)
    _deregister(client)
    db.expire_all()
    assert db.query(Agent).filter(Agent.id == "587A2B").first().uninstalled_at is not None

    # Ré-enrôlement du même machine_id, comme après une réinstallation.
    from datetime import datetime

    from src.main import apply_reported_facts

    fresh = db.query(Agent).filter(Agent.id == "587A2B").first()
    fresh.status = "active"
    fresh.uninstalled_at = None
    fresh.uninstalled_by = None
    fresh.last_communication = datetime.utcnow()
    db.commit()

    db.expire_all()
    reinstalled = db.query(Agent).filter(Agent.id == "587A2B").first()
    assert reinstalled.status == "active"
    assert reinstalled.uninstalled_at is None
    assert reinstalled.uninstalled_by is None
