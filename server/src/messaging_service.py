"""
Service de messagerie pour les notifications via l'API Mail Service CBC.

Reads runtime config from MessagingConfig (Settings UI) with env fallback.
Renders HTML from MailTemplate (global or per-agent).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from src.config import settings

logger = logging.getLogger(__name__)


class MessagingService:
    """Service d'envoi de notifications via l'API Mail Service CBC."""

    @staticmethod
    def _runtime_config(db: Optional[Session] = None) -> Dict[str, Any]:
        """DB MessagingConfig wins when present; blanks fall back to env."""
        endpoint = (settings.messaging_api_endpoint or "").rstrip("/")
        api_key = settings.messaging_api_key or ""
        timeout = int(settings.messaging_api_timeout or 30)
        enabled = bool(settings.messaging_enabled)
        recipients: List[str] = []
        try:
            recipients = json.loads(settings.messaging_recipients or "[]")
            if not isinstance(recipients, list):
                recipients = []
        except json.JSONDecodeError:
            recipients = []

        if db is not None:
            try:
                from src.models import MessagingConfig

                row = db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()
            except Exception:
                row = None
            if row:
                enabled = bool(row.enabled)
                if row.api_endpoint:
                    endpoint = str(row.api_endpoint).rstrip("/")
                if row.api_key:
                    api_key = str(row.api_key)
                if row.api_timeout:
                    timeout = int(row.api_timeout)
                try:
                    db_recips = json.loads(row.recipients or "[]")
                    if isinstance(db_recips, list) and db_recips:
                        recipients = db_recips
                except json.JSONDecodeError:
                    pass

        return {
            "endpoint": endpoint,
            "api_key": api_key,
            "timeout": timeout,
            "enabled": enabled,
            "recipients": recipients,
            "configured": bool(endpoint and api_key),
        }

    @staticmethod
    def _is_configured(db: Optional[Session] = None) -> bool:
        return bool(MessagingService._runtime_config(db)["configured"])

    @staticmethod
    def _send_to_cbc_api(
        to: str | List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[str | List[str]] = None,
        bcc: Optional[str | List[str]] = None,
        db: Optional[Session] = None,
    ) -> bool:
        cfg = MessagingService._runtime_config(db)
        if not cfg["configured"]:
            logger.warning("Configuration API CBC non définie. Notification non envoyée.")
            return False
        if not cfg["enabled"]:
            logger.info("Service de messagerie désactivé. Notification non envoyée.")
            return False

        endpoint = f"{cfg['endpoint']}/mail"
        payload: Dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body": body,
            "is_html": is_html,
        }
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": cfg["api_key"],
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=cfg["timeout"],
            )
            if response.status_code in (200, 201):
                logger.info("Mail envoyé via API CBC. Status: %s", response.status_code)
                return True
            if response.status_code == 401:
                logger.error("Échec d'authentification API CBC. Vérifier la clé API.")
                return False
            logger.error("Erreur API CBC. Status: %s, Response: %s", response.status_code, response.text)
            return False
        except requests.exceptions.Timeout:
            logger.error("Timeout API CBC (%ss)", cfg["timeout"])
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Erreur de connexion à l'API CBC: %s", endpoint)
            return False
        except Exception as exc:
            logger.error("Erreur inattendue API CBC: %s", exc)
            return False

    @staticmethod
    def _context_from_agent(agent: Any) -> Dict[str, Any]:
        if agent is None:
            return {
                "hostname": "unknown",
                "agent_name": "unknown",
                "ip_address": "",
                "location": "",
                "agent_id": "",
            }
        return {
            "hostname": getattr(agent, "hostname", "") or "unknown",
            "agent_name": getattr(agent, "name", None) or getattr(agent, "hostname", "") or "unknown",
            "ip_address": getattr(agent, "ip_address", None) or "",
            "location": getattr(agent, "location", None) or "",
            "agent_id": getattr(agent, "id", "") or "",
        }

    @staticmethod
    def send_simple_mail(
        *,
        to: str | List[str],
        subject: str,
        body: str,
        is_html: bool = True,
        cc: Optional[str | List[str]] = None,
        db: Optional[Session] = None,
        require_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Send a plain/HTML mail via CBC Mail API. Used for tests and future owner routing."""
        cfg = MessagingService._runtime_config(db)
        if not cfg["configured"]:
            return {
                "ok": False,
                "error": "API CBC non configurée (endpoint + clé). Paramètres → Messagerie.",
            }
        if require_enabled and not cfg["enabled"]:
            return {"ok": False, "error": "Messagerie désactivée. Cochez « Activer les notifications »."}
        recipients = to if isinstance(to, list) else [to]
        recipients = [r.strip() for r in recipients if r and str(r).strip()]
        if not recipients:
            return {"ok": False, "error": "Aucun destinataire."}
        ok = MessagingService._send_to_cbc_api(
            to=recipients if len(recipients) > 1 else recipients[0],
            subject=subject,
            body=body,
            is_html=is_html,
            cc=cc,
            db=db,
        )
        return {
            "ok": ok,
            "to": recipients,
            "cc": cc,
            "endpoint": f"{cfg['endpoint']}/mail",
            "error": None if ok else "Échec d'envoi (voir logs serveur / health API CBC).",
        }

    @staticmethod
    def resolve_recipients_for_agent(db: Optional[Session], agent: Any = None) -> Dict[str, List[str]]:
        """Return {to, cc} for an alert.

        Today: global MessagingConfig recipients in ``to``.
        Later: host owner in ``to``, management hierarchy in ``cc``.
        """
        cfg = MessagingService._runtime_config(db)
        to_list = list(cfg["recipients"] or [])
        cc_list: List[str] = []
        if db is not None and agent is not None:
            owner_id = getattr(agent, "owner_user_id", None)
            if owner_id:
                from src.models import User

                owner = db.query(User).filter(User.id == owner_id).first()
                if owner and owner.email:
                    to_list = [owner.email]
                    # Walk manager chain (cap 8) for CC
                    seen = {owner.id}
                    mid = getattr(owner, "manager_id", None)
                    depth = 0
                    while mid and depth < 8:
                        mgr = db.query(User).filter(User.id == mid).first()
                        if not mgr or mgr.id in seen:
                            break
                        if mgr.email and mgr.email not in to_list and mgr.email not in cc_list:
                            cc_list.append(mgr.email)
                        seen.add(mgr.id)
                        mid = getattr(mgr, "manager_id", None)
                        depth += 1
        return {"to": to_list, "cc": cc_list}

    @staticmethod
    def send_alert_notification(
        alert_type: str,
        severity: str,
        message: str,
        hostname: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None,
        db: Optional[Session] = None,
        agent: Any = None,
        mount: Optional[str] = None,
    ) -> bool:
        cfg = MessagingService._runtime_config(db)
        if not cfg["enabled"]:
            logger.info("Service de messagerie désactivé. Notification non envoyée.")
            return False

        routed = MessagingService.resolve_recipients_for_agent(db, agent)
        to_list = routed["to"] or list(cfg["recipients"] or [])
        cc_list = routed["cc"] or None
        if not to_list:
            logger.warning("Aucun destinataire configuré. Notification non envoyée.")
            return False

        from src.mail_templates import render, resolve

        ctx = MessagingService._context_from_agent(agent)
        if hostname:
            ctx["hostname"] = hostname
        ctx.update(
            {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "value": "" if value is None else value,
                "threshold": "" if threshold is None else threshold,
                "mount": mount or "",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
        subject_tpl, body_tpl = resolve(db, "alert", alert_type, ctx.get("agent_id") or None)
        subject, body = render(subject_tpl, body_tpl, ctx)
        return MessagingService._send_to_cbc_api(
            to=to_list if len(to_list) > 1 else to_list[0],
            subject=subject,
            body=body,
            is_html=True,
            cc=cc_list if cc_list else None,
            db=db,
        )

    @staticmethod
    def send_task_notification(
        plugin: str,
        status: str,
        message: str,
        db: Optional[Session] = None,
        agent: Any = None,
        task_id: str = "",
        dry_run: bool = False,
        requested_by: str = "",
    ) -> bool:
        cfg = MessagingService._runtime_config(db)
        if not cfg["enabled"] or not cfg["recipients"]:
            return False

        from src.mail_templates import render, resolve

        ctx = MessagingService._context_from_agent(agent)
        ctx.update(
            {
                "plugin": plugin,
                "status": status,
                "message": message,
                "task_id": task_id,
                "dry_run": "oui" if dry_run else "non",
                "requested_by": requested_by or "",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
        event_key = f"{plugin}:{status}"
        subject_tpl, body_tpl = resolve(db, "task", event_key, ctx.get("agent_id") or None)
        subject, body = render(subject_tpl, body_tpl, ctx)
        return MessagingService._send_to_cbc_api(
            to=cfg["recipients"],
            subject=subject,
            body=body,
            is_html=True,
            db=db,
        )

    @staticmethod
    def send_system_notification(
        notification_type: str,
        message: str,
        severity: str = "info",
        db: Optional[Session] = None,
    ) -> bool:
        cfg = MessagingService._runtime_config(db)
        if not cfg["enabled"] or not cfg["recipients"]:
            return False
        subject = f"[{notification_type}] {message}"
        body = (
            f"<strong>Notification Système</strong><br><br>"
            f"<strong>Type:</strong> {notification_type}<br>"
            f"<strong>Message:</strong> {message}<br>"
            f"<strong>Horodatage:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        return MessagingService._send_to_cbc_api(
            to=cfg["recipients"],
            subject=subject,
            body=body,
            is_html=True,
            db=db,
        )

    @staticmethod
    def health_check(db: Optional[Session] = None) -> Dict[str, Any]:
        cfg = MessagingService._runtime_config(db)
        result: Dict[str, Any] = {
            "status": "unknown",
            "configured": cfg["configured"],
            "enabled": cfg["enabled"],
            "recipients_count": len(cfg["recipients"]),
            "last_check": datetime.utcnow().isoformat(),
            "error": None,
            "api_response": None,
        }
        if not cfg["configured"]:
            result["status"] = "error"
            result["error"] = "Configuration API CBC non définie (endpoint + clé). Enregistrez-les dans Paramètres → Messagerie."
            return result
        if not cfg["enabled"]:
            result["status"] = "disabled"
            return result

        endpoint = f"{cfg['endpoint']}/health"
        try:
            response = requests.get(endpoint, timeout=cfg["timeout"])
            if response.status_code == 200:
                api_data = response.json()
                result["api_response"] = api_data
                if api_data.get("success") and api_data.get("status") == "healthy":
                    result["status"] = "operational"
                    result["database"] = api_data.get("database", "unknown")
                    result["pending_mails"] = api_data.get("pending_mails", 0)
                else:
                    result["status"] = "degraded"
                    result["error"] = f"API signale un état dégradé: {api_data.get('status', 'unknown')}"
            else:
                result["status"] = "error"
                result["error"] = f"Erreur HTTP lors du health check: {response.status_code}"
        except requests.exceptions.Timeout:
            result["status"] = "error"
            result["error"] = f"Timeout lors du health check (timeout: {cfg['timeout']}s)"
        except requests.exceptions.ConnectionError:
            result["status"] = "error"
            result["error"] = f"Erreur de connexion à l'API CBC: {endpoint}"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = f"Erreur inattendue lors du health check: {exc}"
        return result
