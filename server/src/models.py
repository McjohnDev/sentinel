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
    cpu_architecture = Column(String)
    
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
    latency_ms = Column(Float)
    temperature_celsius = Column(Float, nullable=True)
    
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


class EmailConfig(Base):
    """Modèle de données pour la configuration des notifications email."""

    __tablename__ = 'email_config'

    id = Column(String, primary_key=True, default='default')
    recipients = Column(String, default='[]')  # JSON array of email addresses
    smtp_host = Column(String)
    smtp_port = Column(Integer, default=587)
    smtp_secure = Column(Boolean, default=True)
    smtp_user = Column(String)
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
