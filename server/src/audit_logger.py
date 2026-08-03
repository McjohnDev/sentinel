import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.models import User
from src.database import get_db

# Configuration du logging structuré
class AuditLogger:
    """Logger pour les événements d'audit et de sécurité."""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # Handler pour fichier
        file_handler = logging.FileHandler("logs/audit.log")
        file_handler.setLevel(logging.INFO)
        
        # Handler pour console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter JSON
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success"
    ):
        """Enregistre un événement d'audit."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "status": status,
            "details": details or {}
        }
        self.logger.info(json.dumps(log_entry))
    
    def log_login(self, username: str, user_id: str, ip_address: str, success: bool):
        """Enregistre une tentative de login."""
        self.log_event(
            event_type="login",
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            status="success" if success else "failed",
            details={"action": "user_authentication"}
        )
    
    def log_logout(self, username: str, user_id: str, ip_address: str):
        """Enregistre une déconnexion."""
        self.log_event(
            event_type="logout",
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details={"action": "user_logout"}
        )
    
    def log_agent_enrollment(self, agent_id: str, hostname: str, ip_address: str, success: bool):
        """Enregistre un enrôlement d'agent."""
        self.log_event(
            event_type="agent_enrollment",
            ip_address=ip_address,
            status="success" if success else "failed",
            details={
                "agent_id": agent_id,
                "hostname": hostname,
                "action": "agent_enrollment"
            }
        )
    
    def log_alert_created(self, alert_id: str, alert_type: str, agent_id: str, severity: str, user_id: Optional[str] = None):
        """Enregistre la création d'une alerte."""
        self.log_event(
            event_type="alert_created",
            user_id=user_id,
            details={
                "alert_id": alert_id,
                "alert_type": alert_type,
                "agent_id": agent_id,
                "severity": severity,
                "action": "alert_creation"
            }
        )
    
    def log_alert_acknowledged(self, alert_id: str, user_id: str, username: str):
        """Enregistre l'acquittement d'une alerte."""
        self.log_event(
            event_type="alert_acknowledged",
            user_id=user_id,
            username=username,
            details={
                "alert_id": alert_id,
                "action": "alert_acknowledgment"
            }
        )
    
    def log_alert_resolved(self, alert_id: str, user_id: str, username: str):
        """Enregistre la résolution d'une alerte."""
        self.log_event(
            event_type="alert_resolved",
            user_id=user_id,
            username=username,
            details={
                "alert_id": alert_id,
                "action": "alert_resolution"
            }
        )
    
    def log_user_created(self, user_id: str, username: str, role: str, created_by: str):
        """Enregistre la création d'un utilisateur."""
        self.log_event(
            event_type="user_created",
            user_id=created_by,
            details={
                "target_user_id": user_id,
                "target_username": username,
                "role": role,
                "action": "user_creation"
            }
        )
    
    def log_unauthorized_access(self, endpoint: str, ip_address: str, details: Optional[Dict[str, Any]] = None):
        """Enregistre un accès non autorisé."""
        self.log_event(
            event_type="unauthorized_access",
            ip_address=ip_address,
            status="failed",
            details={
                "endpoint": endpoint,
                "action": "unauthorized_access_attempt",
                **(details or {})
            }
        )
    
    def log_rate_limit_exceeded(self, endpoint: str, ip_address: str):
        """Enregistre un dépassement de rate limit."""
        self.log_event(
            event_type="rate_limit_exceeded",
            ip_address=ip_address,
            status="failed",
            details={
                "endpoint": endpoint,
                "action": "rate_limit_exceeded"
            }
        )


# Instance globale du logger d'audit
audit_logger = AuditLogger()
