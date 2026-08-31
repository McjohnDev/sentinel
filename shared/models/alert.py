from sqlalchemy import Column, String, DateTime, Float, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum


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


class Alert:
    """Modèle de données pour une alerte."""
    
    __tablename__ = 'alerts'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    
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
