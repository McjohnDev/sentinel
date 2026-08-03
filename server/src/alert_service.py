from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from src.models import Agent, Heartbeat, Alert, AlertSeverity, AlertType, AlertStatus
from src.config import settings
from src.email_service import EmailService


class AlertService:
    """Service de gestion des alertes."""
    
    @staticmethod
    def check_cpu_alert(db: Session, agent_id: str, cpu_percent: float) -> Optional[Alert]:
        """Vérifie si une alerte CPU doit être générée."""
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        critical_threshold = agent.cpu_critical_threshold if agent and agent.cpu_critical_threshold else settings.cpu_critical_threshold
        warning_threshold = agent.cpu_warning_threshold if agent and agent.cpu_warning_threshold else settings.cpu_warning_threshold
        
        if cpu_percent >= critical_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.CRITICAL, AlertType.CPU_HIGH,
                f"CPU critique: {cpu_percent}%", cpu_percent, critical_threshold
            )
        elif cpu_percent >= warning_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.WARNING, AlertType.CPU_HIGH,
                f"CPU élevé: {cpu_percent}%", cpu_percent, warning_threshold
            )
        return None
    
    @staticmethod
    def check_ram_alert(db: Session, agent_id: str, ram_percent: float) -> Optional[Alert]:
        """Vérifie si une alerte RAM doit être générée."""
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        critical_threshold = agent.ram_critical_threshold if agent and agent.ram_critical_threshold else settings.ram_critical_threshold
        warning_threshold = agent.ram_warning_threshold if agent and agent.ram_warning_threshold else settings.ram_warning_threshold
        
        if ram_percent >= critical_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.CRITICAL, AlertType.RAM_HIGH,
                f"RAM critique: {ram_percent}%", ram_percent, critical_threshold
            )
        elif ram_percent >= warning_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.WARNING, AlertType.RAM_HIGH,
                f"RAM élevée: {ram_percent}%", ram_percent, warning_threshold
            )
        return None
    
    @staticmethod
    def check_disk_alert(db: Session, agent_id: str, disk_percent: float) -> Optional[Alert]:
        """Vérifie si une alerte disque doit être générée."""
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        critical_threshold = agent.disk_critical_threshold if agent and agent.disk_critical_threshold else settings.disk_critical_threshold
        warning_threshold = agent.disk_warning_threshold if agent and agent.disk_warning_threshold else settings.disk_warning_threshold
        
        if disk_percent >= critical_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.CRITICAL, AlertType.DISK_HIGH,
                f"Disque critique: {disk_percent}%", disk_percent, critical_threshold
            )
        elif disk_percent >= warning_threshold:
            return AlertService._create_alert(
                db, agent_id, AlertSeverity.WARNING, AlertType.DISK_HIGH,
                f"Disque élevé: {disk_percent}%", disk_percent, warning_threshold
            )
        return None
    
    @staticmethod
    def _create_alert(
        db: Session,
        agent_id: str,
        severity: AlertSeverity,
        alert_type: AlertType,
        message: str,
        value: float,
        threshold: float
    ) -> Alert:
        """Crée une alerte si elle n'existe pas déjà."""
        import uuid
        
        # Vérifier si une alerte similaire est déjà ouverte
        existing_alert = db.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.type == alert_type,
            Alert.status == AlertStatus.OPEN
        ).first()
        
        if existing_alert:
            # Mettre à jour l'alerte existante si la gravité a changé
            if existing_alert.severity != severity:
                existing_alert.severity = severity
                existing_alert.message = message
                existing_alert.value = value
                existing_alert.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_alert)
            return existing_alert
        
        # Créer une nouvelle alerte
        alert = Alert(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            severity=severity,
            type=alert_type,
            message=message,
            value=value,
            threshold=threshold,
            status=AlertStatus.OPEN
        )
        
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        # Envoyer un email si l'alerte est critique
        if severity == AlertSeverity.CRITICAL:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                EmailService.send_alert_email_to_admin({
                    'type': alert_type.value,
                    'severity': severity.value,
                    'message': message,
                    'hostname': agent.hostname,
                    'value': value,
                    'threshold': threshold
                })
        
        return alert
    
    @staticmethod
    def resolve_alerts_below_threshold(
        db: Session,
        agent_id: str,
        alert_type: AlertType,
        current_value: float
    ):
        """Résout les alertes si la valeur est revenue sous le seuil warning."""
        # Récupérer les alertes ouvertes de ce type
        alerts = db.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.type == alert_type,
            Alert.status == AlertStatus.OPEN
        ).all()
        
        threshold = AlertService._get_warning_threshold(alert_type)
        
        if current_value < threshold:
            for alert in alerts:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.updated_at = datetime.utcnow()
            
            db.commit()
    
    @staticmethod
    def _get_warning_threshold(alert_type: AlertType) -> float:
        """Retourne le seuil warning pour un type d'alerte."""
        if alert_type == AlertType.CPU_HIGH:
            return settings.cpu_warning_threshold
        elif alert_type == AlertType.RAM_HIGH:
            return settings.ram_warning_threshold
        elif alert_type == AlertType.DISK_HIGH:
            return settings.disk_warning_threshold
        return 0
    
    @staticmethod
    def check_offline_agents(db: Session):
        """Vérifie les agents hors ligne et génère des alertes."""
        import uuid
        
        threshold = datetime.utcnow() - timedelta(seconds=settings.offline_alert_threshold_seconds)
        
        # Récupérer les agents actifs sans heartbeat récent
        offline_agents = db.query(Agent).filter(
            Agent.status == "active",
            Agent.last_communication < threshold
        ).all()
        
        for agent in offline_agents:
            # Vérifier si une alerte hors ligne existe déjà
            existing_alert = db.query(Alert).filter(
                Alert.agent_id == agent.id,
                Alert.type == AlertType.AGENT_OFFLINE,
                Alert.status == AlertStatus.OPEN
            ).first()
            
            if not existing_alert:
                # Créer une alerte hors ligne
                alert = Alert(
                    id=str(uuid.uuid4()),
                    agent_id=agent.id,
                    severity=AlertSeverity.CRITICAL,
                    type=AlertType.AGENT_OFFLINE,
                    message=f"Agent hors ligne depuis {agent.last_communication}",
                    status=AlertStatus.OPEN
                )
                db.add(alert)
        
        db.commit()
    
    @staticmethod
    def check_back_online(db: Session, agent_id: str):
        """Vérifie si un agent est revenu en ligne et génère une alerte info."""
        import uuid
        
        # Vérifier si une alerte hors ligne existe
        offline_alert = db.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.type == AlertType.AGENT_OFFLINE,
            Alert.status == AlertStatus.OPEN
        ).first()
        
        if offline_alert:
            # Résoudre l'alerte hors ligne
            offline_alert.status = AlertStatus.RESOLVED
            offline_alert.resolved_at = datetime.utcnow()
            offline_alert.updated_at = datetime.utcnow()
            
            # Créer une alerte de retour en ligne
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            back_online_alert = Alert(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                severity=AlertSeverity.INFO,
                type=AlertType.BACK_ONLINE,
                message=f"Agent revenu en ligne: {agent.hostname}",
                status=AlertStatus.RESOLVED,  # Auto-résolue
                started_at=datetime.utcnow(),
                resolved_at=datetime.utcnow()
            )
            db.add(back_online_alert)
            
            db.commit()
