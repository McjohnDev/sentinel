from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from datetime import datetime


class Agent:
    """Modèle de données pour un agent de supervision."""
    
    __tablename__ = 'agents'
    
    id = Column(String, primary_key=True)  # Agent ID généré par le serveur
    machine_id = Column(String, unique=True, nullable=False, index=True)  # UUID de la machine
    hostname = Column(String, nullable=False)
    ip_address = Column(String)
    os = Column(String)  # Windows, Linux, macOS
    os_version = Column(String)
    agent_version = Column(String)
    status = Column(String, default='active')  # active, revoked, deleted
    last_communication = Column(DateTime)
    enrolled_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
