from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime


class Heartbeat:
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
