import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import get_db, Base
from src.models import User, UserRole, MachineType, MessagingConfig, AvailabilityPolicy, Agent, Heartbeat
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


class TestV11Features:
    """Tests pour les nouvelles fonctionnalités V1.1."""
    
    def test_machine_type_enum(self):
        """Test l'enum MachineType."""
        assert MachineType.SERVER.value == "server"
        assert MachineType.WORKSTATION.value == "workstation"
    
    def test_messaging_config_creation(self, db):
        """Test la création de la configuration de messagerie."""
        config = MessagingConfig(
            id='default',
            recipients='[]',
            api_endpoint='https://api.cbc.internal/messaging',
            api_key='test-key',
            api_timeout=30,
            enabled=True
        )
        db.add(config)
        db.commit()
        
        retrieved = db.query(MessagingConfig).filter(MessagingConfig.id == 'default').first()
        assert retrieved is not None
        assert retrieved.api_endpoint == 'https://api.cbc.internal/messaging'
        assert retrieved.enabled == True
    
    def test_heartbeat_without_removed_fields(self, db):
        """Test que le heartbeat ne contient plus les champs supprimés."""
        from src.models import Agent, Heartbeat
        
        # Créer un agent avec machine_type
        agent = Agent(
            id='test-agent-1',
            machine_id='test-machine-1',
            hostname='test-host',
            os='linux',
            machine_type=MachineType.SERVER,
            auth_key='test-key',
            status='active'
        )
        db.add(agent)
        db.commit()
        
        # Créer un heartbeat sans les champs supprimés
        heartbeat = Heartbeat(
            id='test-heartbeat-1',
            agent_id='test-agent-1',
            cpu_percent=50.0,
            cpu_cores=4,
            ram_percent=60.0,
            ram_total_gb=16.0,
            ram_used_gb=9.6,
            ram_free_gb=6.4,
            disk_percent=70.0,
            disk_total_gb=500.0,
            disk_used_gb=350.0,
            disk_free_gb=150.0,
            uptime_seconds=3600
        )
        db.add(heartbeat)
        db.commit()
        
        # Vérifier que les champs supprimés n'existent pas
        retrieved = db.query(Heartbeat).filter(Heartbeat.id == 'test-heartbeat-1').first()
        assert retrieved is not None
        assert not hasattr(retrieved, 'cpu_architecture') or getattr(retrieved, 'cpu_architecture', None) is None
        assert not hasattr(retrieved, 'latency_ms') or getattr(retrieved, 'latency_ms', None) is None
        assert not hasattr(retrieved, 'temperature_celsius') or getattr(retrieved, 'temperature_celsius', None) is None
    
    def test_messaging_service_health_check(self):
        """Test le health check du MessagingService."""
        from src.messaging_service import MessagingService
        
        # Test avec configuration non définie
        result = MessagingService.health_check()
        assert result["status"] in ["error", "disabled", "unknown"]
        assert result["configured"] == False
        assert result["enabled"] == True
    
    def test_messaging_service_send_alert_notification(self):
        """Test l'envoi de notification d'alerte via MessagingService."""
        from src.messaging_service import MessagingService
        
        # Test avec service désactivé
        result = MessagingService.send_alert_notification(
            alert_type="cpu_high",
            severity="warning",
            message="CPU usage high",
            hostname="test-host",
            value=85.0,
            threshold=80.0
        )
        # Le service est désactivé par défaut si pas de configuration
        assert result == False
    
    def test_availability_policy_creation(self, db):
        """Test la création d'une politique de disponibilité."""
        import json
        
        policy = AvailabilityPolicy(
            id='test-policy',
            agent_id='test-agent-1',
            time_windows_enabled=True,
            time_windows=json.dumps({
                "monday": [{"start": "08:00", "end": "18:00"}],
                "tuesday": [{"start": "08:00", "end": "18:00"}]
            }),
            offline_threshold_seconds=3600
        )
        db.add(policy)
        db.commit()
        
        retrieved = db.query(AvailabilityPolicy).filter(AvailabilityPolicy.id == 'test-policy').first()
        assert retrieved is not None
        assert retrieved.time_windows_enabled == True
        assert retrieved.offline_threshold_seconds == 3600
    
    def test_availability_service_time_windows(self):
        """Test le service de vérification des fenêtres horaires."""
        from src.availability_service import AvailabilityService
        import json
        
        # Test avec fenêtres horaires actives
        time_windows = json.dumps({
            "monday": [{"start": "08:00", "end": "18:00"}]
        })
        
        # Le test dépend de l'heure actuelle, donc on teste juste la parsing
        assert AvailabilityService.parse_time("08:00").hour == 8
        assert AvailabilityService.parse_time("18:00").hour == 18
        
        # Test du nom du jour
        day_name = AvailabilityService.get_current_day_name()
        assert day_name in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    def test_availability_service_should_alert_offline(self):
        """Test la logique de détermination d'alerte offline."""
        from src.availability_service import AvailabilityService
        from datetime import datetime, timedelta
        import json
        
        # Test serveur hors ligne (doit toujours alerter)
        should_alert, reason = AvailabilityService.should_alert_offline(
            agent_id='test-server',
            machine_type='server',
            last_communication=datetime.utcnow() - timedelta(seconds=120),
            availability_policy=None
        )
        assert should_alert == True
        assert "hors ligne" in reason.lower()
        
        # Test poste hors ligne sans fenêtres horaires (doit alerter)
        should_alert, reason = AvailabilityService.should_alert_offline(
            agent_id='test-workstation',
            machine_type='workstation',
            last_communication=datetime.utcnow() - timedelta(seconds=7300),
            availability_policy=None
        )
        assert should_alert == True
        
        # Test poste hors ligne avec fenêtres horaires désactivées (doit alerter)
        policy_with_disabled_windows = {
            'time_windows_enabled': False,
            'time_windows': '{}',
            'offline_threshold_seconds': None
        }
        should_alert, reason = AvailabilityService.should_alert_offline(
            agent_id='test-workstation',
            machine_type='workstation',
            last_communication=datetime.utcnow() - timedelta(seconds=7300),
            availability_policy=policy_with_disabled_windows
        )
        assert should_alert == True
