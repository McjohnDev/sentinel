import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import get_db, Base
from src.models import User, Agent, Alert, MachineType
import uuid


# Base de test en mémoire, partagée entre les connexions via StaticPool.
#
# Ce module utilisait auparavant un fichier `./test.db` à la racine du dépôt :
# exécuté après les autres modules, il entrait en contention de verrou SQLite
# sur ce fichier et la suite complète se bloquait indéfiniment (elle passait
# lorsque le fichier était exécuté seul). Une base en mémoire par processus
# supprime la contention et rend la suite reproductible.
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# Mot de passe en clair de l'utilisateur de test, partagé avec auth_token.
TEST_USER_PASSWORD = "testpassword"


@pytest.fixture
def test_user(db):
    """Utilisateur réel, avec un vrai hash.

    La fixture posait auparavant `hashed_password=...`, un nom de colonne
    inexistant (le modèle expose `password_hash`), et une chaîne qui n'était
    pas un hash bcrypt valide. Elle levait donc un TypeError et faisait
    échouer en erreur les six tests qui en dépendent — dont les seuls tests
    d'authentification et de pagination du fichier.
    """
    from src.auth_service import AuthService
    from src.models import UserRole

    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        email="test@example.com",
        password_hash=AuthService.get_password_hash(TEST_USER_PASSWORD),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token(client, test_user):
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": TEST_USER_PASSWORD,
    })
    # Ne plus retourner None en silence : les tests consommateurs passaient
    # alors sans rien vérifier.
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


class TestHealthCheck:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestAuthentication:
    def test_login_success(self, client, test_user):
        response = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpassword"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, client, test_user):
        # Le mot de passe doit respecter la contrainte de longueur du modèle
        # (min 8) pour atteindre la vérification des identifiants : sinon la
        # requête est rejetée en 422 et le test ne prouve rien.
        response = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "mauvais-mot-de-passe",
        })
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, client):
        response = client.get("/api/agents")
        assert response.status_code == 401

    def test_protected_endpoint_with_token(self, client, auth_token):
        if auth_token:
            response = client.get("/api/agents", headers={
                "Authorization": f"Bearer {auth_token}"
            })
            assert response.status_code == 200


class TestAgents:
    def test_list_agents_empty(self, client, auth_token):
        if auth_token:
            response = client.get("/api/agents", headers={
                "Authorization": f"Bearer {auth_token}"
            })
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 0

    def test_enroll_agent(self, client):
        response = client.post("/api/agents/enroll", json={
            "token": "test-token",
            "machine_id": str(uuid.uuid4()),
            "hostname": "test-host",
            "os": "Linux",
            "os_version": "Ubuntu 20.04",
            "agent_version": "1.0.0"
        })
        # Jeton inconnu : 401. Le test acceptait auparavant [400, 404] et
        # échouait donc systématiquement contre le comportement réel.
        assert response.status_code == 401


class TestPresence:
    def test_ping_marks_agent_live(self, client, db):
        from datetime import datetime, timedelta

        agent = Agent(
            id=str(uuid.uuid4()),
            machine_id=f"mid-{uuid.uuid4().hex[:8]}",
            hostname="win-host",
            auth_key=str(uuid.uuid4()),
            status="active",
            os="windows",
            machine_type=MachineType.WORKSTATION,
            last_communication=datetime.utcnow() - timedelta(hours=3),
            enrolled_at=datetime.utcnow() - timedelta(days=1),
        )
        db.add(agent)
        db.commit()
        resp = client.post("/api/agents/ping", headers={"Authorization": agent.auth_key})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["agent_id"] == agent.id
        db.refresh(agent)
        assert (datetime.utcnow() - agent.last_communication).total_seconds() < 5

    def test_detail_status_is_derived_not_db_active(self, client, db, auth_token):
        from datetime import datetime, timedelta

        stale = Agent(
            id=str(uuid.uuid4()),
            machine_id=f"mid-{uuid.uuid4().hex[:8]}",
            hostname="stale-host",
            auth_key=str(uuid.uuid4()),
            status="active",
            os="windows",
            machine_type=MachineType.WORKSTATION,
            last_communication=datetime.utcnow() - timedelta(hours=3),
            enrolled_at=datetime.utcnow() - timedelta(days=1),
        )
        db.add(stale)
        db.commit()
        resp = client.get(
            f"/api/agents/{stale.id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "offline"
        assert data["last_seen_age_seconds"] >= 3 * 3600 - 5

    def test_list_includes_offline_by_default(self, client, db, auth_token):
        from datetime import datetime, timedelta

        stale = Agent(
            id=str(uuid.uuid4()),
            machine_id=f"mid-{uuid.uuid4().hex[:8]}",
            hostname="listed-offline",
            auth_key=str(uuid.uuid4()),
            status="active",
            os="windows",
            machine_type=MachineType.WORKSTATION,
            last_communication=datetime.utcnow() - timedelta(hours=3),
            enrolled_at=datetime.utcnow() - timedelta(days=1),
        )
        db.add(stale)
        db.commit()
        resp = client.get("/api/agents", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200, resp.text
        rows = resp.json().get("data") or []
        match = next((r for r in rows if r["id"] == stale.id), None)
        assert match is not None
        assert match["status"] == "offline"

        hidden = client.get(
            "/api/agents?include_offline=false",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        hidden_rows = hidden.json().get("data") or []
        assert all(r["id"] != stale.id for r in hidden_rows)


class TestAlerts:
    def test_list_alerts_empty(self, client, auth_token):
        if auth_token:
            response = client.get("/api/alerts", headers={
                "Authorization": f"Bearer {auth_token}"
            })
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 0


class TestPagination:
    def test_agents_pagination(self, client, auth_token):
        if auth_token:
            response = client.get("/api/agents?skip=0&limit=10", headers={
                "Authorization": f"Bearer {auth_token}"
            })
            assert response.status_code == 200
            data = response.json()
            assert "pagination" in data
            assert data["pagination"]["skip"] == 0
            assert data["pagination"]["limit"] == 10

    def test_alerts_pagination(self, client, auth_token):
        if auth_token:
            response = client.get("/api/alerts?skip=0&limit=10", headers={
                "Authorization": f"Bearer {auth_token}"
            })
            assert response.status_code == 200
            data = response.json()
            assert "pagination" in data
            assert data["pagination"]["skip"] == 0
            assert data["pagination"]["limit"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
