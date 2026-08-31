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
        status: str = "success",
        target: Optional[str] = None,
    ):
        """Enregistre un événement d'audit.

        Ne doit jamais propager d'exception : les appels se font après le
        `db.commit()` de l'endpoint, donc une erreur de journalisation
        transformerait une écriture déjà validée en réponse HTTP 500.
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "status": status,
            "details": details or {}
        }
        try:
            self.logger.info(json.dumps(log_entry, default=str))
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Écriture du journal d'audit impossible")

        self._persist(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            target=target,
            status=status,
            details=log_entry.get("details"),
        )

    def _persist(
        self,
        event_type: str,
        user_id: Optional[str],
        username: Optional[str],
        ip_address: Optional[str],
        target: Optional[str],
        status: str,
        details: Optional[Dict[str, Any]],
    ) -> None:
        """Écrit la trace en base, dans sa propre session.

        Une session dédiée est volontaire : la trace ne doit pas participer à
        la transaction de l'endpoint, sinon un rollback métier effacerait la
        preuve de la tentative. Toute erreur est absorbée — les appels ont lieu
        après le commit de l'endpoint, une exception ici transformerait une
        écriture réussie en HTTP 500.
        """
        import uuid

        session = None
        try:
            from src.database import SessionLocal
            from src.models import AuditLog

            session = SessionLocal()
            session.add(
                AuditLog(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                    target=target,
                    status=status,
                    details=json.dumps(details or {}, default=str, ensure_ascii=False),
                )
            )
            session.commit()
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Persistance du journal d'audit impossible")
            if session is not None:
                try:
                    session.rollback()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:  # noqa: BLE001
                    pass

    def log_action(
        self,
        user_id: Optional[str] = None,
        action: str = "",
        details: Optional[Any] = None,
        ip_address: Optional[str] = None,
        username: Optional[str] = None,
        status: str = "success",
    ):
        """Action d'administration générique.

        Cette méthode manquait alors que `main.py` l'appelait sur 16 endpoints
        (création de groupe, publication de configuration, fenêtres de
        maintenance, gestion des jetons…). Chaque appel levait donc un
        AttributeError *après* le commit : la donnée était écrite et le client
        recevait une 500, sans aucune trace d'audit.
        """
        self.log_event(
            event_type=action or "ACTION",
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details={"action": action, "details": details} if details is not None else {"action": action},
            status=status,
            target=str(details) if isinstance(details, str) else None,
        )

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
