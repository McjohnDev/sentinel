import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import get_db, Base
from src.models import User, UserRole
from src.auth_service import AuthService

# Base de données de test
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    """Fixture pour la base de données de test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class TestAuth:
    """Tests pour l'authentification."""
    
    def test_register_user(self, db):
        """Test la création d'un utilisateur."""
        user = AuthService.create_user(
            db,
            "Admin",
            "admin@cbc.cm",
            "Admin12",
            UserRole.ADMIN
        )
        assert user.username == "Admin"
        assert user.email == "admin@cbc.cm"
        assert user.role == UserRole.ADMIN
    
    def test_register_duplicate_user(self, db):
        """Test la création d'un utilisateur en double."""
        AuthService.create_user(
            db,
            "testuser",
            "test@example.com",
            "TestPassword123",
            UserRole.OPERATOR
        )
        with pytest.raises(ValueError):
            AuthService.create_user(
                db,
                "testuser",
                "test2@example.com",
                "TestPassword123",
                UserRole.OPERATOR
            )
    
    def test_password_hash(self):
        """Test le hashage des mots de passe."""
        password = "TestPassword123"
        hashed = AuthService.get_password_hash(password)
        assert hashed != password
        assert AuthService.verify_password(password, hashed)
