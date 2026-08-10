from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from src.database import Base


class UserRole(enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    READ_ONLY = "read_only"


class MachineType(enum.Enum):
    SERVER = "server"
    WORKSTATION = "workstation"


class User(Base):
    """Modèle de données pour un utilisateur du dashboard."""
    
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    
    role = Column(SQLEnum(UserRole), default=UserRole.OPERATOR, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Agent(Base):
    """Modèle de données pour un agent de supervision."""

    __tablename__ = 'agents'

    id = Column(String, primary_key=True)  # Agent ID généré par le serveur
    machine_id = Column(String, unique=True, nullable=False, index=True)  # UUID de la machine
    hostname = Column(String, nullable=False)
    name = Column(String, nullable=True)  # Nom affichable de l'agent
    ip_address = Column(String)
    os = Column(String)  # Windows, Linux, macOS
    os_version = Column(String)
    agent_version = Column(String)
    auth_key = Column(String, unique=True, nullable=False)  # Clé d'authentification
    status = Column(String, default='active')  # active, revoked, deleted
    last_communication = Column(DateTime)
    enrolled_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    location = Column(String, nullable=True)  # Localisation de l'agent
    machine_type = Column(SQLEnum(MachineType), default=MachineType.WORKSTATION, nullable=False)  # Type de machine

    # Seuils personnalisés par agent (None = utiliser les seuils globaux)
    cpu_warning_threshold = Column(Float, nullable=True)
    cpu_critical_threshold = Column(Float, nullable=True)
    ram_warning_threshold = Column(Float, nullable=True)
    ram_critical_threshold = Column(Float, nullable=True)
    disk_warning_threshold = Column(Float, nullable=True)
    disk_critical_threshold = Column(Float, nullable=True)

    heartbeats = relationship("Heartbeat", back_populates="agent", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="agent", cascade="all, delete-orphan")


class Heartbeat(Base):
    """Modèle de données pour un heartbeat envoyé par un agent."""
    
    __tablename__ = 'heartbeats'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    # Métriques CPU
    cpu_percent = Column(Float)
    cpu_cores = Column(Integer)
    
    # Métriques RAM
    ram_percent = Column(Float)
    ram_total_gb = Column(Float)
    ram_used_gb = Column(Float)
    ram_free_gb = Column(Float)
    
    # Métriques Disque
    disk_percent = Column(Float)
    disk_total_gb = Column(Float)
    disk_used_gb = Column(Float)
    disk_free_gb = Column(Float)
    
    # Autres métriques
    uptime_seconds = Column(Integer)
    
    created_at = Column(DateTime, default=func.now())
    
    agent = relationship("Agent", back_populates="heartbeats")


class AlertSeverity(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(enum.Enum):
    AGENT_OFFLINE = "agent_offline"
    CPU_HIGH = "cpu_high"
    RAM_HIGH = "ram_high"
    DISK_HIGH = "disk_high"
    BACK_ONLINE = "back_online"
    SERVICE_DOWN = "service_down"
    FILE_ANOMALY = "file_anomaly"
    NOTIFICATION_CHANNEL_DOWN = "notification_channel_down"


class AlertStatus(enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class Alert(Base):
    """Modèle de données pour une alerte."""
    
    __tablename__ = 'alerts'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    type = Column(SQLEnum(AlertType), nullable=False)
    message = Column(String, nullable=False)
    
    status = Column(SQLEnum(AlertStatus), default=AlertStatus.OPEN, nullable=False)
    
    # Valeurs au moment de l'alerte
    value = Column(Float)  # Valeur qui a déclenché l'alerte
    threshold = Column(Float)  # Seuil qui a été dépassé
    
    started_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)  # User ID
    acknowledged_comment = Column(String, nullable=True)
    
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    agent = relationship("Agent", back_populates="alerts")


class GlobalSettings(Base):
    """Modèle de données pour les paramètres globaux de seuils."""

    __tablename__ = 'global_settings'

    id = Column(String, primary_key=True, default='default')
    cpu_warning_threshold = Column(Float, default=80)
    cpu_critical_threshold = Column(Float, default=90)
    ram_warning_threshold = Column(Float, default=80)
    ram_critical_threshold = Column(Float, default=90)
    disk_warning_threshold = Column(Float, default=85)
    disk_critical_threshold = Column(Float, default=95)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MessagingConfig(Base):
    """Modèle de données pour la configuration des notifications via API de messagerie CBC."""

    __tablename__ = 'messaging_config'

    id = Column(String, primary_key=True, default='default')
    recipients = Column(String, default='[]')  # JSON array of recipient identifiers
    api_endpoint = Column(String)  # URL de l'API de messagerie interne CBC
    api_key = Column(String)  # Clé d'authentification pour l'API CBC
    api_timeout = Column(Integer, default=30)  # Timeout en secondes
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RetentionConfig(Base):
    """Modèle de données pour la configuration de rétention des données."""

    __tablename__ = 'retention_config'

    id = Column(String, primary_key=True, default='default')
    alerts_days = Column(Integer, default=30)
    heartbeats_days = Column(Integer, default=7)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class EnrollmentToken(Base):
    """Modèle de données pour les tokens d'enrôlement des agents."""

    __tablename__ = 'enrollment_tokens'

    id = Column(String, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    status = Column(String, default='active')  # active, expired, consumed
    created_by = Column(String)  # User who created the token


class NotificationChannelStatus(Base):
    """Modèle de données pour le statut du canal de notification."""

    __tablename__ = 'notification_channel_status'

    id = Column(String, primary_key=True, default='default')
    status = Column(String, default='unknown')  # operational, degraded, error, unknown
    last_check = Column(DateTime, default=func.now())
    last_success = Column(DateTime, nullable=True)
    last_error = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ServiceMonitoring(Base):
    """Modèle de données pour la supervision des services système."""

    __tablename__ = 'service_monitoring'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    service_name = Column(String, nullable=False, index=True)
    status = Column(String, default='unknown')  # running, stopped, unknown
    last_check = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class FileMonitoring(Base):
    """Modèle de données pour la supervision des fichiers."""

    __tablename__ = 'file_monitoring'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    exists = Column(Boolean, default=False)
    size_bytes = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    last_check = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class AvailabilityPolicy(Base):
    """Modèle de données pour la politique de disponibilité (fenêtres horaires)."""

    __tablename__ = 'availability_policies'

    id = Column(String, primary_key=True, default='default')  # 'default' ou agent_id
    agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)  # Null pour politique globale
    
    # Configuration des fenêtres horaires par jour (JSON)
    # Format: {"monday": [{"start": "08:00", "end": "12:00"}, {"start": "14:00", "end": "18:00"}], ...}
    time_windows = Column(String, default='{}')
    
    # Seuil offline en secondes (remplace le seuil par défaut si défini)
    offline_threshold_seconds = Column(Integer, nullable=True)
    
    # Activer/désactiver la vérification des fenêtres horaires
    time_windows_enabled = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class ServiceMonitoringConfig(Base):
    """Modèle de données pour la configuration de supervision des services."""

    __tablename__ = 'service_monitoring_config'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)  # Null pour politique globale
    
    service_name = Column(String, nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    expected_status = Column(String, default='running')  # 'running', 'stopped', etc.
    check_interval_seconds = Column(Integer, default=60)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class FileMonitoringConfig(Base):
    """Modèle de données pour la configuration de supervision des fichiers."""

    __tablename__ = 'file_monitoring_config'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)  # Null pour politique globale
    
    file_path = Column(String, nullable=False, index=True)
    enabled = Column(Boolean, default=True)
    max_size_mb = Column(Integer, nullable=True)  # Taille maximale en Mo
    check_interval_seconds = Column(Integer, default=300)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")
