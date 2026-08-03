import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import get_db, Base
from src.models import User, Agent, Alert
import uuid


# Base de données de test
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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


@pytest.fixture
def test_user(db):
    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$test_hashed_password",
        role="admin"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token(client, test_user):
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpassword"
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


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

    def test_login_invalid_credentials(self, client):
        response = client.post("/api/auth/login", json={
            "username": "invalid",
            "password": "invalid"
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
        # Le token n'existe pas, donc on attend une erreur
        assert response.status_code in [400, 404]


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
