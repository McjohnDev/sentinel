from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
import json
import logging
from sqlalchemy.orm import Session
from src.models import (
    Agent, Heartbeat, Alert, AlertSeverity, AlertType, AlertStatus,
    MachineType, ServiceMonitoring, FileMonitoring, AvailabilityPolicy,
    GlobalSettings, MessagingConfig, MaintenanceWindow, AlertEvent,
    FileCondition, MonitoredFile, MonitoredService,
)
from src.config import settings
from src.messaging_service import MessagingService
from src.availability_service import AvailabilityService
from src import webhook_service

logger = logging.getLogger(__name__)


def _as_datetime(value: Any) -> Optional[datetime]:
    """Convertit une date reçue d'un agent en `datetime`, ou None.

    JSON ne transporte pas de date : l'agent envoie une chaîne ISO 8601. Elle
    était jusqu'ici affectée telle quelle à une colonne `DateTime`, ce que le
    pilote refuse — toute observation de fichier portant une date de
    modification faisait donc échouer le battement entier. Une date illisible
    est ramenée à None : perdre l'horodatage est sans gravité, perdre le
    battement de l'hôte ne l'est pas.
    """
    if value is None or isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        logger.warning("Date de modification illisible ignorée : %r", value)
        return None
    # Colonnes naïves côté plateforme : on ramène en UTC sans fuseau pour ne
    # pas mélanger deux conventions dans la même colonne.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class AlertService:
    """Service de gestion des alertes (FS4 / ALR-001–007)."""

    @staticmethod
    def serialize_severity(severity: AlertSeverity | str) -> str:
        value = severity.value if isinstance(severity, AlertSeverity) else str(severity)
        if value == AlertSeverity.WARNING.value:
            return AlertSeverity.MAJOR.value
        return value

    @staticmethod
    def _global_settings(db: Session) -> GlobalSettings:
        row = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
        if not row:
            row = GlobalSettings(id="default")
            db.add(row)
            db.flush()
        return row

    @staticmethod
    def _duration_seconds(db: Session, agent: Optional[Agent]) -> int:
        gs = AlertService._global_settings(db)
        value = gs.threshold_duration_seconds
        return int(value if value is not None else 300)

    @staticmethod
    def _thresholds_for(agent: Optional[Agent], gs: GlobalSettings, kind: str) -> Tuple[float, float]:
        mapping = {
            "cpu": ("cpu_warning_threshold", "cpu_critical_threshold", gs.cpu_warning_threshold, gs.cpu_critical_threshold),
            "ram": ("ram_warning_threshold", "ram_critical_threshold", gs.ram_warning_threshold, gs.ram_critical_threshold),
            "disk": ("disk_warning_threshold", "disk_critical_threshold", gs.disk_warning_threshold, gs.disk_critical_threshold),
        }
        warn_attr, crit_attr, warn_default, crit_default = mapping[kind]
        warn = getattr(agent, warn_attr, None) if agent else None
        crit = getattr(agent, crit_attr, None) if agent else None
        return float(warn if warn is not None else warn_default or 80), float(
            crit if crit is not None else crit_default or 90
        )

    @staticmethod
    def _normalize_mount(mount: str) -> str:
        m = (mount or "").strip()
        if len(m) >= 2 and m[1] == ":":
            return m.rstrip("\\").upper() + "\\"
        return m.rstrip("/") or "/"

    @staticmethod
    def parse_disk_mount_rules(raw: Any) -> List[Dict[str, Any]]:
        if not raw:
            return []
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in data or []:
            if not isinstance(item, dict):
                continue
            mount = AlertService._normalize_mount(str(item.get("mount") or ""))
            if not mount or mount in seen:
                continue
            try:
                warning = float(item.get("warning", 85))
                critical = float(item.get("critical", 95))
            except (TypeError, ValueError):
                continue
            seen.add(mount)
            out.append({"mount": mount, "warning": warning, "critical": critical})
        return out

    @staticmethod
    def _disk_mount_rule_map(gs: GlobalSettings) -> Dict[str, Tuple[float, float]]:
        rules = AlertService.parse_disk_mount_rules(getattr(gs, "disk_mount_rules", None))
        return {r["mount"]: (float(r["warning"]), float(r["critical"])) for r in rules}

    @staticmethod
    def _disk_mount_rule_map_for_agent(agent: Optional[Agent], gs: GlobalSettings) -> Dict[str, Tuple[float, float]]:
        """Agent partition ceilings override global ones for the same mount."""
        merged = dict(AlertService._disk_mount_rule_map(gs))
        if agent is not None:
            for rule in AlertService.parse_disk_mount_rules(getattr(agent, "disk_mount_rules", None)):
                merged[rule["mount"]] = (float(rule["warning"]), float(rule["critical"]))
        return merged

    @staticmethod
    def _disk_thresholds_for(agent: Optional[Agent], gs: GlobalSettings, mount: str) -> Tuple[float, float]:
        rules = AlertService._disk_mount_rule_map_for_agent(agent, gs)
        key = AlertService._normalize_mount(mount) if mount else ""
        if key and key in rules:
            return rules[key]
        return AlertService._thresholds_for(agent, gs, "disk")

    @staticmethod
    def in_maintenance(db: Session, agent_id: str, when: Optional[datetime] = None) -> Optional[MaintenanceWindow]:
        now = when or datetime.utcnow()
        return (
            db.query(MaintenanceWindow)
            .filter(
                MaintenanceWindow.starts_at <= now,
                MaintenanceWindow.ends_at >= now,
                (MaintenanceWindow.agent_id == agent_id) | (MaintenanceWindow.agent_id.is_(None)),
            )
            .first()
        )

    @staticmethod
    def _record_event(
        db: Session,
        action: str,
        *,
        alert_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        actor: Optional[str] = None,
        comment: Optional[str] = None,
        commit: bool = False,
    ) -> None:
        import uuid

        db.add(
            AlertEvent(
                id=str(uuid.uuid4()),
                alert_id=alert_id,
                agent_id=agent_id,
                action=action,
                actor=actor,
                comment=comment,
            )
        )
        if commit:
            db.commit()

    @staticmethod
    def _sustained_above(db: Session, agent_id: str, attr: str, threshold: float, duration_seconds: int) -> bool:
        """ALR-001: every sample in the window must be >= threshold, covering N minutes."""
        if duration_seconds <= 0:
            return True
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=duration_seconds)
        rows = (
            db.query(Heartbeat)
            .filter(Heartbeat.agent_id == agent_id, Heartbeat.timestamp >= window_start - timedelta(seconds=15))
            .order_by(Heartbeat.timestamp.asc())
            .all()
        )
        if not rows:
            return False
        oldest = rows[0].timestamp
        if oldest.replace(tzinfo=None) > window_start + timedelta(seconds=max(20, int(duration_seconds * 0.25))):
            return False
        values = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
        if not values:
            return False
        return all(float(v) >= threshold for v in values)

    @staticmethod
    def _check_metric_alert(
        db: Session,
        agent_id: str,
        alert_type: AlertType,
        hb_attr: str,
        current: float,
        label: str,
        kind: str,
    ) -> Optional[Alert]:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        gs = AlertService._global_settings(db)
        warn, crit = AlertService._thresholds_for(agent, gs, kind)
        duration = AlertService._duration_seconds(db, agent)

        if current < warn:
            AlertService.resolve_alerts_below_threshold(db, agent_id, alert_type, current)
            return None

        severity = AlertSeverity.CRITICAL if current >= crit else AlertSeverity.MAJOR
        threshold = crit if severity == AlertSeverity.CRITICAL else warn
        need = crit if severity == AlertSeverity.CRITICAL else warn
        if not AlertService._sustained_above(db, agent_id, hb_attr, need, duration):
            return None

        window = AlertService.in_maintenance(db, agent_id)
        if window:
            AlertService._record_event(
                db,
                "suppressed",
                agent_id=agent_id,
                comment=f"{alert_type.value} during maintenance: {window.reason}",
                commit=True,
            )
            return None

        return AlertService._create_alert(
            db,
            agent_id,
            severity,
            alert_type,
            f"{label} {severity.value}: {current}% pendant {duration}s (seuil {threshold}%)",
            current,
            threshold,
        )

    @staticmethod
    def check_cpu_alert(db: Session, agent_id: str, cpu_percent: float) -> Optional[Alert]:
        return AlertService._check_metric_alert(
            db, agent_id, AlertType.CPU_HIGH, "cpu_percent", cpu_percent, "CPU", "cpu"
        )

    @staticmethod
    def check_ram_alert(db: Session, agent_id: str, ram_percent: float) -> Optional[Alert]:
        return AlertService._check_metric_alert(
            db, agent_id, AlertType.RAM_HIGH, "ram_percent", ram_percent, "RAM", "ram"
        )

    @staticmethod
    def _sustained_mount_above(
        db: Session, agent_id: str, mount: str, threshold: float, duration_seconds: int
    ) -> bool:
        """Every heartbeat in the window must report mount usage >= threshold."""
        if duration_seconds <= 0:
            return True
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=duration_seconds)
        rows = (
            db.query(Heartbeat)
            .filter(Heartbeat.agent_id == agent_id, Heartbeat.timestamp >= window_start - timedelta(seconds=15))
            .order_by(Heartbeat.timestamp.asc())
            .all()
        )
        if not rows:
            return False
        oldest = rows[0].timestamp
        if oldest.replace(tzinfo=None) > window_start + timedelta(seconds=max(20, int(duration_seconds * 0.25))):
            return False
        values: List[float] = []
        for row in rows:
            pct = AlertService._disk_percent_from_heartbeat(row, mount)
            if pct is not None:
                values.append(float(pct))
        if not values or len(values) < len(rows):
            return False
        return all(v >= threshold for v in values)

    @staticmethod
    def _disk_percent_from_heartbeat(hb: Heartbeat, mount: str) -> Optional[float]:
        if hb.disks_json:
            try:
                disks = json.loads(hb.disks_json)
                for d in disks:
                    if AlertService._normalize_mount(str(d.get("mount") or "")) == AlertService._normalize_mount(mount):
                        return float(d.get("percent"))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        if mount and hb.disk_mount and AlertService._normalize_mount(str(hb.disk_mount)) == AlertService._normalize_mount(mount):
            return float(hb.disk_percent) if hb.disk_percent is not None else None
        if not mount or mount in ("/", "C:\\"):
            return float(hb.disk_percent) if hb.disk_percent is not None else None
        return None

    @staticmethod
    def _check_disk_mount_alert(
        db: Session,
        agent_id: str,
        mount: str,
        current: float,
    ) -> Optional[Alert]:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        gs = AlertService._global_settings(db)
        warn, crit = AlertService._disk_thresholds_for(agent, gs, mount or "")
        duration = AlertService._duration_seconds(db, agent)

        if current < warn:
            AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.DISK_HIGH, current, mount=mount)
            return None

        severity = AlertSeverity.CRITICAL if current >= crit else AlertSeverity.MAJOR
        threshold = crit if severity == AlertSeverity.CRITICAL else warn
        need = crit if severity == AlertSeverity.CRITICAL else warn
        if not AlertService._sustained_mount_above(db, agent_id, mount, need, duration):
            return None

        window = AlertService.in_maintenance(db, agent_id)
        if window:
            AlertService._record_event(
                db,
                "suppressed",
                agent_id=agent_id,
                comment=f"disk_high:{mount} during maintenance: {window.reason}",
                commit=True,
            )
            return None

        label = f"Disque {mount}" if mount else "Disque"
        return AlertService._create_alert(
            db,
            agent_id,
            severity,
            AlertType.DISK_HIGH,
            f"{label} {severity.value}: {current}% pendant {duration}s (seuil {threshold}%)",
            current,
            threshold,
            mount=mount or None,
        )

    @staticmethod
    def check_disk_alert(db: Session, agent_id: str, disk_percent: float, mount: Optional[str] = None) -> Optional[Alert]:
        return AlertService._check_disk_mount_alert(db, agent_id, mount or "", disk_percent)

    @staticmethod
    def check_disk_alerts(db: Session, agent_id: str, disks: Optional[List[Dict[str, Any]]], fallback_percent: float, fallback_mount: Optional[str] = None) -> None:
        """Evaluate disk alerts per mount (alert flag and/or explicit partition ceilings)."""
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        gs = AlertService._global_settings(db)
        rule_mounts = set(AlertService._disk_mount_rule_map_for_agent(agent, gs).keys())
        checked_mounts: set[str] = set()
        for row in disks or []:
            mount = AlertService._normalize_mount(str(row.get("mount") or ""))
            if not mount or mount in checked_mounts:
                continue
            if not (row.get("alert") or mount in rule_mounts):
                continue
            checked_mounts.add(mount)
            try:
                pct = float(row.get("percent"))
            except (TypeError, ValueError):
                continue
            AlertService.check_disk_alert(db, agent_id, pct, mount=mount)

        if not checked_mounts:
            AlertService.check_disk_alert(db, agent_id, fallback_percent, mount=fallback_mount or "")
    
    @staticmethod
    def _create_alert(
        db: Session,
        agent_id: str,
        severity: AlertSeverity,
        alert_type: AlertType,
        message: str,
        value: float = 0.0,
        threshold: float = 0.0,
        mount: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Alert:
        """Crée une alerte si elle n'existe pas déjà.

        `target` distingue plusieurs alertes du même type sur un même hôte —
        un service, un chemin de fichier. Sans lui, deux services tombés se
        confondaient en une seule alerte et le second passait inaperçu.
        """
        import uuid
        
        # Vérifier si une alerte similaire est déjà ouverte
        query = db.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.type == alert_type,
            Alert.status == AlertStatus.OPEN,
        )
        if alert_type == AlertType.DISK_HIGH:
            if mount:
                query = query.filter(Alert.mount == mount)
            else:
                query = query.filter((Alert.mount.is_(None)) | (Alert.mount == ""))
        if target is not None:
            query = query.filter(Alert.target == target)
        existing_alert = query.first()
        
        if existing_alert:
            # Mettre à jour l'alerte existante si la gravité a changé
            if existing_alert.severity != severity:
                existing_alert.severity = severity
                existing_alert.message = message
                existing_alert.value = value
                existing_alert.updated_at = datetime.utcnow()
                AlertService._record_event(
                    db, "severity_changed", alert_id=existing_alert.id, agent_id=agent_id, comment=message
                )
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
            status=AlertStatus.OPEN,
            mount=mount,
            target=target,
        )
        
        db.add(alert)
        db.flush()
        AlertService._record_event(db, "opened", alert_id=alert.id, agent_id=agent_id, comment=message)
        db.commit()
        db.refresh(alert)

        AlertService._notify(db, alert)
        return alert

    @staticmethod
    def _notify(db: Session, alert: Alert) -> None:
        # FS7-02 — detect→notify latency (wall clock from alert creation)
        try:
            from datetime import datetime, timezone
            from src.latency_slo import latency_slo

            created = getattr(alert, "created_at", None) or getattr(alert, "timestamp", None)
            if created is not None:
                if getattr(created, "tzinfo", None) is None:
                    created = created.replace(tzinfo=timezone.utc)
                latency_slo.record_detect_to_notify(
                    (datetime.now(timezone.utc) - created).total_seconds()
                )
        except Exception:
            pass
        agent = db.query(Agent).filter(Agent.id == alert.agent_id).first()
        hostname = agent.hostname if agent else "unknown"
        sev = AlertService.serialize_severity(alert.severity)
        notify = sev in (AlertSeverity.MAJOR.value, AlertSeverity.CRITICAL.value, AlertSeverity.MINOR.value)
        if not notify:
            alert.mail_status = "skipped"
            alert.webhook_status = "skipped"
            db.commit()
            return

        mail_ok = False
        try:
            mail_ok = MessagingService.send_alert_notification(
                alert_type=alert.type.value,
                severity=sev,
                message=alert.message,
                hostname=hostname,
                value=alert.value,
                threshold=alert.threshold,
                db=db,
                agent=agent,
                mount=getattr(alert, "mount", None),
            )
        except Exception:
            mail_ok = False
        alert.mail_status = "sent" if mail_ok else "failed"
        AlertService._record_event(
            db, "notified_mail", alert_id=alert.id, agent_id=alert.agent_id, comment=alert.mail_status
        )

        cfg = db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()
        webhook_ok = False
        if cfg and cfg.webhook_enabled and cfg.webhook_url and cfg.webhook_secret:
            payload = {
                "alert_id": alert.id,
                "agent_id": alert.agent_id,
                "hostname": hostname,
                "type": alert.type.value,
                "severity": sev,
                "message": alert.message,
                "value": alert.value,
                "threshold": alert.threshold,
                "started_at": str(alert.started_at),
            }
            webhook_ok = webhook_service.post_signed(cfg.webhook_url, cfg.webhook_secret, payload)
            alert.webhook_status = "sent" if webhook_ok else "failed"
        else:
            alert.webhook_status = "skipped"
        AlertService._record_event(
            db, "notified_webhook", alert_id=alert.id, agent_id=alert.agent_id, comment=alert.webhook_status
        )
        db.commit()
    
    @staticmethod
    def resolve_disk_alerts(
        db: Session,
        agent_id: str,
        disks: Optional[List[Dict[str, Any]]],
        fallback_percent: float,
        fallback_mount: Optional[str] = None,
    ) -> None:
        """Auto-resolve per-mount disk alerts when usage drops below warning."""
        open_alerts = (
            db.query(Alert)
            .filter(
                Alert.agent_id == agent_id,
                Alert.type == AlertType.DISK_HIGH,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
            .all()
        )
        disk_map = {str(d.get("mount") or ""): float(d.get("percent")) for d in (disks or []) if d.get("mount") is not None}
        for alert in open_alerts:
            mount = alert.mount or ""
            if mount and mount in disk_map:
                AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.DISK_HIGH, disk_map[mount], mount=mount)
            elif not mount:
                AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.DISK_HIGH, fallback_percent, mount="")

    @staticmethod
    def resolve_open_alerts_for_agent(
        db: Session,
        agent_id: str,
        reason: str = "agent_uninstalled",
    ) -> int:
        """Clôt toutes les alertes encore ouvertes d'un hôte retiré du parc.

        Une machine qu'on a délibérément cessé de superviser ne doit plus
        sonner : sans cela, un poste désinstallé laisse derrière lui des
        alertes que personne ne peut plus résoudre — la métrique ne
        redescendra jamais sous le seuil, faute d'agent pour la mesurer.
        """
        open_alerts = (
            db.query(Alert)
            .filter(
                Alert.agent_id == agent_id,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
            .all()
        )
        now = datetime.utcnow()
        for alert in open_alerts:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = now
            AlertService._record_event(
                db,
                "auto_resolved",
                alert_id=alert.id,
                agent_id=agent_id,
                actor="system",
                comment=reason,
            )
        if open_alerts:
            db.commit()
            logger.info(
                "%d alerte(s) clôturée(s) pour l'agent %s (%s)",
                len(open_alerts),
                agent_id,
                reason,
            )
        return len(open_alerts)

    @staticmethod
    def resolve_alerts_below_threshold(
        db: Session,
        agent_id: str,
        alert_type: AlertType,
        current_value: float,
        mount: Optional[str] = None,
    ):
        """Résout les alertes si la valeur est revenue sous le seuil warning."""
        query = db.query(Alert).filter(
            Alert.agent_id == agent_id,
            Alert.type == alert_type,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
        if alert_type == AlertType.DISK_HIGH and mount is not None:
            query = query.filter(Alert.mount == mount)
        elif alert_type == AlertType.DISK_HIGH:
            query = query.filter((Alert.mount.is_(None)) | (Alert.mount == ""))
        alerts = query.all()
        
        gs = AlertService._global_settings(db)
        kind = {
            AlertType.CPU_HIGH: "cpu",
            AlertType.RAM_HIGH: "ram",
            AlertType.DISK_HIGH: "disk",
        }.get(alert_type)
        if kind:
            agent = db.query(Agent).filter(Agent.id == agent_id).first()
            threshold, _ = AlertService._thresholds_for(agent, gs, kind)
        else:
            threshold = AlertService._get_warning_threshold(alert_type)
        
        if current_value < threshold:
            for alert in alerts:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.updated_at = datetime.utcnow()
                AlertService._record_event(db, "auto_resolved", alert_id=alert.id, agent_id=agent_id)
            
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
                if AlertService.in_maintenance(db, agent.id):
                    continue
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
                            severity=AlertSeverity.CRITICAL if agent.machine_type == MachineType.SERVER else AlertSeverity.MAJOR,
                            type=AlertType.AGENT_OFFLINE,
                            message=f"Agent hors ligne - {reason}",
                            status=AlertStatus.OPEN
                        )
                        db.add(alert)
                        AlertService._record_event(db, "opened", alert_id=alert.id, agent_id=agent.id, comment=reason)
                        db.flush()
                        AlertService._notify(db, alert)
        
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
    def _resolve_targeted_alert(
        db: Session, agent_id: str, alert_type: AlertType, target: str, reason: str
    ) -> None:
        """Clôt l'alerte d'un sujet précis revenu à l'état attendu."""
        open_alerts = (
            db.query(Alert)
            .filter(
                Alert.agent_id == agent_id,
                Alert.type == alert_type,
                Alert.target == target,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
            .all()
        )
        now = datetime.utcnow()
        for alert in open_alerts:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = now
            AlertService._record_event(
                db,
                "auto_resolved",
                alert_id=alert.id,
                agent_id=agent_id,
                actor="system",
                comment=reason,
            )

    @staticmethod
    def check_service_alerts(
        db: Session, agent_id: str, services_data: List[Dict[str, Any]]
    ) -> Optional[Alert]:
        """Compare l'état observé de chaque service à son état attendu (point 6).

        Réécriture complète. L'implémentation précédente comparait à
        `critical_services = []` — une liste vide codée en dur avec un TODO :
        aucune alerte de service n'a jamais pu être levée. Elle dédupliquait
        de surcroît sur le seul type d'alerte, si bien qu'un deuxième service
        tombé aurait de toute façon été absorbé par le premier.

        L'état attendu se règle par service : on alerte aussi bien sur un
        service critique arrêté que sur un service qui devrait rester à
        l'arrêt et qui tourne.
        """
        import uuid

        plan = {
            row.service_name: row
            for row in db.query(MonitoredService)
            .filter(MonitoredService.agent_id == agent_id, MonitoredService.enabled.is_(True))
            .all()
        }

        for service in services_data or []:
            service_name = service.get("name")
            observed = (service.get("status") or "unknown").lower()
            if not service_name:
                continue

            # État observé : conservé pour tous les services remontés, même
            # non supervisés — c'est l'inventaire, pas la surveillance.
            existing = (
                db.query(ServiceMonitoring)
                .filter(
                    ServiceMonitoring.agent_id == agent_id,
                    ServiceMonitoring.service_name == service_name,
                )
                .first()
            )
            if existing:
                existing.status = observed
                existing.last_check = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
            else:
                db.add(
                    ServiceMonitoring(
                        id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        service_name=service_name,
                        status=observed,
                    )
                )

            rule = plan.get(service_name)
            if rule is None:
                continue

            expected = rule.expected_state.value
            # « unknown » n'est pas un écart : l'interrogation du gestionnaire
            # de services a échoué, on ne sait rien. Alerter là-dessus
            # produirait du bruit à chaque redémarrage du gestionnaire.
            if observed == "unknown":
                continue

            if observed == expected:
                AlertService._resolve_targeted_alert(
                    db,
                    agent_id,
                    AlertType.SERVICE_DOWN,
                    service_name,
                    f"service revenu à l'état attendu ({expected})",
                )
                continue

            message = (
                f"Service {service_name} : état {observed}, attendu {expected}"
            )
            AlertService._create_alert(
                db,
                agent_id=agent_id,
                alert_type=AlertType.SERVICE_DOWN,
                severity=rule.severity,
                message=message,
                target=service_name,
            )

        db.commit()
        return None

    @staticmethod
    def check_file_alerts(
        db: Session, agent_id: str, files_data: List[Dict[str, Any]]
    ) -> Optional[Alert]:
        """Confronte l'état de chaque fichier à la condition attendue (point 6).

        Réécriture complète, pour la même raison que les services :
        `monitored_files = []` était codé en dur, donc le contrôle
        « fichier manquant » ne pouvait jamais se déclencher.

        Deux conditions désormais, au lieu d'une :

        * `must_exist` — le fichier doit être là (journal applicatif, verrou) ;
        * `must_not_exist` — son **apparition** est l'anomalie (drapeau
          d'erreur, fichier de blocage, cœur applicatif). Ce sens-là
          n'existait nulle part.
        """
        import uuid

        plan = {
            row.path: row
            for row in db.query(MonitoredFile)
            .filter(MonitoredFile.agent_id == agent_id, MonitoredFile.enabled.is_(True))
            .all()
        }

        for file_info in files_data or []:
            file_path = file_info.get("path")
            # `None` = l'agent n'a pas pu conclure (droits, chemin réseau).
            # À distinguer de `False` : traiter l'indécidable comme une
            # absence lèverait une fausse alerte « fichier manquant », et
            # surtout **éteindrait** à tort une alerte « fichier interdit ».
            raw_exists = file_info.get("exists")
            exists = None if raw_exists is None else bool(raw_exists)
            size_bytes = file_info.get("size_bytes")
            last_modified = _as_datetime(file_info.get("last_modified"))
            if not file_path:
                continue

            existing = (
                db.query(FileMonitoring)
                .filter(
                    FileMonitoring.agent_id == agent_id,
                    FileMonitoring.file_path == file_path,
                )
                .first()
            )
            if existing:
                existing.exists = bool(exists)
                existing.size_bytes = size_bytes
                existing.last_modified = last_modified
                existing.last_check = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
            else:
                db.add(
                    FileMonitoring(
                        id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        file_path=file_path,
                        exists=bool(exists),
                        size_bytes=size_bytes,
                        last_modified=last_modified,
                    )
                )

            rule = plan.get(file_path)
            if rule is None:
                continue

            if exists is None:
                # État indécidable : on ne crée ni ne clôt d'alerte. Le
                # dernier verdict connu reste en place jusqu'à ce que l'agent
                # puisse à nouveau conclure.
                logger.debug(
                    "État indécidable pour %s sur %s — évaluation reportée",
                    file_path,
                    agent_id,
                )
                continue

            must_exist = rule.condition == FileCondition.MUST_EXIST
            breached = (must_exist and not exists) or (not must_exist and exists)

            if breached:
                message = (
                    f"Fichier surveillé manquant : {file_path}"
                    if must_exist
                    else f"Fichier interdit présent : {file_path}"
                )
                AlertService._create_alert(
                    db,
                    agent_id=agent_id,
                    alert_type=AlertType.FILE_ANOMALY,
                    severity=rule.severity,
                    message=message,
                    target=file_path,
                )
                continue

            # Condition respectée : contrôle de taille éventuel, puis clôture
            # de l'alerte s'il y en avait une.
            oversize = (
                rule.max_size_mb is not None
                and size_bytes is not None
                and float(size_bytes) > float(rule.max_size_mb) * 1024 * 1024
            )
            if oversize:
                size_mb = float(size_bytes) / (1024 * 1024)
                AlertService._create_alert(
                    db,
                    agent_id=agent_id,
                    alert_type=AlertType.FILE_ANOMALY,
                    severity=rule.severity,
                    message=(
                        f"Fichier {file_path} : {size_mb:.1f} Mo, "
                        f"plafond {rule.max_size_mb} Mo"
                    ),
                    value=round(size_mb, 2),
                    threshold=float(rule.max_size_mb),
                    target=file_path,
                )
            else:
                AlertService._resolve_targeted_alert(
                    db,
                    agent_id,
                    AlertType.FILE_ANOMALY,
                    file_path,
                    "fichier conforme à la condition attendue",
                )

        db.commit()
        return None

    @staticmethod
    def check_log_pattern_alerts(db: Session, agent_id: str, pattern_alerts: List[Dict[str, Any]]) -> int:
        """ALR-003 / FS3-08: matching log lines become immediate events."""
        created = 0
        if AlertService.in_maintenance(db, agent_id):
            AlertService._record_event(
                db, "suppressed", agent_id=agent_id, comment="log pattern during maintenance", commit=True
            )
            return 0
        for ev in pattern_alerts or []:
            msg = str(ev.get("message") or ev.get("raw") or "log pattern")
            AlertService._create_alert(
                db,
                agent_id,
                AlertSeverity.MAJOR,
                AlertType.LOG_PATTERN,
                f"Motif journal: {msg[:300]}",
                0.0,
                0.0,
            )
            created += 1
        return created

    @staticmethod
    def check_rate_limit_alert(db: Session, agent_id: str, dropped: int) -> Optional[Alert]:
        if dropped <= 0:
            return None
        return AlertService._create_alert(
            db,
            agent_id,
            AlertSeverity.MINOR,
            AlertType.RATE_LIMIT,
            f"Collecte journaux limitée (AGT-038), dropped={dropped}",
            float(dropped),
            0.0,
        )

    @staticmethod
    def escalate_unacked(db: Session) -> int:
        """ALR-006: re-notify and raise severity after N minutes still OPEN."""
        gs = AlertService._global_settings(db)
        minutes = int(gs.escalate_after_minutes or 15)
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        alerts = (
            db.query(Alert)
            .filter(
                Alert.status == AlertStatus.OPEN,
                Alert.escalated_at.is_(None),
                Alert.started_at <= cutoff,
            )
            .all()
        )
        n = 0
        for alert in alerts:
            if AlertService.in_maintenance(db, alert.agent_id):
                continue
            if alert.severity != AlertSeverity.CRITICAL:
                alert.severity = AlertSeverity.CRITICAL
            alert.escalated_at = datetime.utcnow()
            AlertService._record_event(db, "escalated", alert_id=alert.id, agent_id=alert.agent_id)
            db.commit()
            AlertService._notify(db, alert)
            n += 1
        return n

    @staticmethod
    def check_footprint_alert(
        db: Session,
        agent_id: str,
        cpu_percent: Optional[float],
        ram_mb: Optional[float],
    ) -> Optional[Alert]:
        """AGT-007 — alert when agent self-reported footprint exceeds budget."""
        gs = AlertService._global_settings(db)
        cpu_max = float(gs.agent_cpu_max_percent if gs.agent_cpu_max_percent is not None else 2.0)
        ram_max = float(gs.agent_ram_max_mb if gs.agent_ram_max_mb is not None else 300.0)
        over_cpu = cpu_percent is not None and float(cpu_percent) > cpu_max
        over_ram = ram_mb is not None and float(ram_mb) > ram_max
        if not over_cpu and not over_ram:
            AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.AGENT_FOOTPRINT, 0)
            # resolve helper uses warning threshold — force resolve open footprint alerts
            open_fp = db.query(Alert).filter(
                Alert.agent_id == agent_id,
                Alert.type == AlertType.AGENT_FOOTPRINT,
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            ).all()
            for a in open_fp:
                a.status = AlertStatus.RESOLVED
                a.resolved_at = datetime.utcnow()
                AlertService._record_event(db, "auto_resolved", alert_id=a.id, agent_id=agent_id)
            if open_fp:
                db.commit()
            return None
        parts = []
        if over_cpu:
            parts.append(f"CPU agent {cpu_percent:.2f}% > {cpu_max}%")
        if over_ram:
            parts.append(f"RAM agent {ram_mb:.1f} MB > {ram_max} MB")
        return AlertService._create_alert(
            db,
            agent_id,
            AlertSeverity.MINOR,
            AlertType.AGENT_FOOTPRINT,
            "Empreinte agent hors budget (AGT-007): " + "; ".join(parts),
            float(cpu_percent or ram_mb or 0),
            float(cpu_max if over_cpu else ram_max),
        )
