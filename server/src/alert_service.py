from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from src.models import (
    Agent, Heartbeat, Alert, AlertSeverity, AlertType, AlertStatus,
    MachineType, ServiceMonitoring, FileMonitoring, AvailabilityPolicy
)
from src.config import settings
from src.messaging_service import MessagingService
from src.availability_service import AvailabilityService


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
        
        # Envoyer une notification via l'API CBC si l'alerte est critique
        if severity == AlertSeverity.CRITICAL:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            if agent:
                MessagingService.send_alert_notification(
                    alert_type=alert_type.value,
                    severity=severity.value,
                    message=message,
                    hostname=agent.hostname,
                    value=value,
                    threshold=threshold
                )
        
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
        """Vérifie les agents hors ligne et génère des alertes en fonction du type de machine et des fenêtres horaires."""
        import uuid
        import json
        
        for agent in db.query(Agent).filter(Agent.status == "active").all():
            # Récupérer la politique de disponibilité (spécifique à l'agent ou globale)
            availability_policy = db.query(AvailabilityPolicy).filter(
                AvailabilityPolicy.agent_id == agent.id
            ).first()
            
            if not availability_policy:
                # Utiliser la politique globale
                availability_policy = db.query(AvailabilityPolicy).filter(
                    AvailabilityPolicy.id == 'default'
                ).first()
            
            # Construire le dictionnaire de politique pour AvailabilityService
            policy_dict = None
            if availability_policy:
                policy_dict = {
                    'time_windows_enabled': availability_policy.time_windows_enabled,
                    'time_windows': availability_policy.time_windows,
                    'offline_threshold_seconds': availability_policy.offline_threshold_seconds
                }
            
            # Déterminer si une alerte doit être générée
            if agent.last_communication:
                should_alert, reason = AvailabilityService.should_alert_offline(
                    agent_id=agent.id,
                    machine_type=agent.machine_type.value,
                    last_communication=agent.last_communication,
                    availability_policy=policy_dict
                )
                
                if should_alert:
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
                            severity=AlertSeverity.CRITICAL if agent.machine_type == MachineType.SERVER else AlertSeverity.WARNING,
                            type=AlertType.AGENT_OFFLINE,
                            message=f"Agent hors ligne - {reason}",
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
    
    @staticmethod
    def check_service_alerts(db: Session, agent_id: str, services_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """
        Vérifie l'état des services et génère des alertes si nécessaire.
        
        NOTE: Cette méthode nécessite la liste des services à superviser.
        Pour l'instant, elle est préparée pour accepter les données de services.
        
        Args:
            db: Session de base de données
            agent_id: ID de l'agent
            services_data: Liste des services avec leur état (ex: [{"name": "SWIFT AutoClient", "status": "running"}])
        
        Returns:
            Alert si une alerte a été créée, None sinon
        """
        import uuid
        
        # TODO: Définir la liste officielle des services à superviser
        # Pour l'instant, on accepte tous les services fournis
        critical_services = []  # À DÉFINIR - liste des services critiques
        
        for service in services_data:
            service_name = service.get("name")
            service_status = service.get("status")
            
            if not service_name:
                continue
            
            # Mettre à jour ou créer l'enregistrement de supervision
            existing = db.query(ServiceMonitoring).filter(
                ServiceMonitoring.agent_id == agent_id,
                ServiceMonitoring.service_name == service_name
            ).first()
            
            if existing:
                existing.status = service_status
                existing.last_check = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
            else:
                new_monitoring = ServiceMonitoring(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    service_name=service_name,
                    status=service_status
                )
                db.add(new_monitoring)
            
            # Générer une alerte si un service critique est arrêté
            if service_name in critical_services and service_status == "stopped":
                existing_alert = db.query(Alert).filter(
                    Alert.agent_id == agent_id,
                    Alert.type == AlertType.SERVICE_DOWN,
                    Alert.status == AlertStatus.OPEN
                ).first()
                
                if not existing_alert:
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        severity=AlertSeverity.CRITICAL,
                        type=AlertType.SERVICE_DOWN,
                        message=f"Service critique arrêté: {service_name}",
                        status=AlertStatus.OPEN
                    )
                    db.add(alert)
                    
                    # Envoyer notification
                    agent = db.query(Agent).filter(Agent.id == agent_id).first()
                    if agent:
                        MessagingService.send_alert_notification(
                            alert_type="service_down",
                            severity="critical",
                            message=f"Service critique arrêté: {service_name}",
                            hostname=agent.hostname
                        )
        
        db.commit()
        return None
    
    @staticmethod
    def check_file_alerts(db: Session, agent_id: str, files_data: List[Dict[str, Any]]) -> Optional[Alert]:
        """
        Vérifie l'état des fichiers et génère des alertes si nécessaire.
        
        NOTE: Cette méthode nécessite la liste des fichiers à superviser et les critères d'anomalie.
        Pour l'instant, elle est préparée pour accepter les données de fichiers.
        
        Args:
            db: Session de base de données
            agent_id: ID de l'agent
            files_data: Liste des fichiers avec leur état (ex: [{"path": "/var/log/swift.log", "exists": true, "size": 1024}])
        
        Returns:
            Alert si une alerte a été créée, None sinon
        """
        import uuid
        
        # TODO: Définir la liste officielle des fichiers à superviser et les critères d'anomalie
        # Pour l'instant, on accepte tous les fichiers fournis
        monitored_files = []  # À DÉFINIR - liste des fichiers à superviser
        
        for file_info in files_data:
            file_path = file_info.get("path")
            exists = file_info.get("exists", False)
            size_bytes = file_info.get("size_bytes")
            last_modified = file_info.get("last_modified")
            
            if not file_path:
                continue
            
            # Mettre à jour ou créer l'enregistrement de supervision
            existing = db.query(FileMonitoring).filter(
                FileMonitoring.agent_id == agent_id,
                FileMonitoring.file_path == file_path
            ).first()
            
            if existing:
                existing.exists = exists
                existing.size_bytes = size_bytes
                existing.last_modified = last_modified
                existing.last_check = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
            else:
                new_monitoring = FileMonitoring(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    file_path=file_path,
                    exists=exists,
                    size_bytes=size_bytes,
                    last_modified=last_modified
                )
                db.add(new_monitoring)
            
            # Générer une alerte si un fichier surveillé n'existe pas
            if file_path in monitored_files and not exists:
                existing_alert = db.query(Alert).filter(
                    Alert.agent_id == agent_id,
                    Alert.type == AlertType.FILE_ANOMALY,
                    Alert.status == AlertStatus.OPEN
                ).first()
                
                if not existing_alert:
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        severity=AlertSeverity.WARNING,
                        type=AlertType.FILE_ANOMALY,
                        message=f"Fichier surveillé manquant: {file_path}",
                        status=AlertStatus.OPEN
                    )
                    db.add(alert)
                    
                    # Envoyer notification
                    agent = db.query(Agent).filter(Agent.id == agent_id).first()
                    if agent:
                        MessagingService.send_alert_notification(
                            alert_type="file_anomaly",
                            severity="warning",
                            message=f"Fichier surveillé manquant: {file_path}",
                            hostname=agent.hostname
                        )
        
        db.commit()
        return None
