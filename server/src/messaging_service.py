"""
Service de messagerie pour les notifications via l'API Mail Service CBC.

Ce service implémente l'interface avec l'API Mail Service CBC officielle
conformément à la documentation version 1.0 - 26/11/2025.
"""

import json
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.config import settings

logger = logging.getLogger(__name__)


class MessagingService:
    """Service d'envoi de notifications via l'API Mail Service CBC."""
    
    @staticmethod
    def _is_configured() -> bool:
        """Vérifie si la configuration de l'API CBC est définie."""
        return bool(settings.messaging_api_endpoint and settings.messaging_api_key)
    
    @staticmethod
    def _send_to_cbc_api(
        to: str | List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[str | List[str]] = None,
        bcc: Optional[str | List[str]] = None
    ) -> bool:
        """
        Envoie un mail via l'API Mail Service CBC.
        
        Documentation API:
        - URL: /mail
        - Méthode: POST
        - Auth: X-API-Key header
        - Content-Type: application/json
        
        Args:
            to: Destinataire(s) (string ou array)
            subject: Sujet du mail
            body: Corps du message
            is_html: true si HTML (défaut: false)
            cc: Destinataire(s) en copie (optionnel)
            bcc: Copie cachée (optionnel)
        
        Returns:
            True si l'envoi a réussi, False sinon
        """
        if not MessagingService._is_configured():
            logger.warning("Configuration API CBC non définie. Notification non envoyée.")
            return False
        
        endpoint = f"{settings.messaging_api_endpoint}/mail"
        
        payload = {
            "to": to,
            "subject": subject,
            "body": body,
            "is_html": is_html
        }
        
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": settings.messaging_api_key
        }
        
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=settings.messaging_api_timeout
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Mail envoyé avec succès via API CBC. Status: {response.status_code}")
                return True
            elif response.status_code == 401:
                logger.error("Échec d'authentification API CBC. Vérifier la clé API.")
                return False
            elif response.status_code == 422:
                logger.error(f"Erreur de validation API CBC: {response.text}")
                return False
            else:
                logger.error(f"Erreur API CBC. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout lors de l'appel à l'API CBC (timeout: {settings.messaging_api_timeout}s)")
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"Erreur de connexion à l'API CBC: {endpoint}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'appel à l'API CBC: {e}")
            return False
    
    @staticmethod
    def send_alert_notification(
        alert_type: str,
        severity: str,
        message: str,
        hostname: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None
    ) -> bool:
        """
        Envoie une notification d'alerte via l'API Mail Service CBC.
        
        Args:
            alert_type: Type de l'alerte (cpu_high, ram_high, service_down, etc.)
            severity: Gravité de l'alerte (info, warning, critical)
            message: Message de l'alerte
            hostname: Nom de la machine concernée
            value: Valeur qui a déclenché l'alerte (optionnel)
            threshold: Seuil qui a été dépassé (optionnel)
        
        Returns:
            True si l'envoi a réussi, False sinon
        """
        if not settings.messaging_enabled:
            logger.info("Service de messagerie désactivé. Notification non envoyée.")
            return False
        
        # Récupérer les destinataires depuis la configuration
        try:
            recipients = json.loads(settings.messaging_recipients)
            if not recipients:
                logger.warning("Aucun destinataire configuré. Notification non envoyée.")
                return False
        except json.JSONDecodeError:
            logger.error("Erreur de décodage des destinataires. Notification non envoyée.")
            return False
        
        # Construire le sujet et le corps du mail
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }.get(severity, "📋")
        
        subject = f"{severity_emoji} [{severity.upper()}] {alert_type} - {hostname}"
        
        body_lines = [
            f"<strong>Alerte {severity.upper()}</strong>",
            f"",
            f"<strong>Type:</strong> {alert_type}",
            f"<strong>Machine:</strong> {hostname}",
            f"<strong>Message:</strong> {message}",
            f"<strong>Horodatage:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]
        
        if value is not None:
            body_lines.append(f"<strong>Valeur actuelle:</strong> {value}")
        if threshold is not None:
            body_lines.append(f"<strong>Seuil:</strong> {threshold}")
        
        body_lines.append("")
        body_lines.append("---")
        body_lines.append("CBC Supervision Platform v1.1")
        body_lines.append("Cet email est généré automatiquement, ne pas répondre.")
        
        body = "<br>".join(body_lines)
        
        return MessagingService._send_to_cbc_api(
            to=recipients,
            subject=subject,
            body=body,
            is_html=True
        )
    
    @staticmethod
    def send_system_notification(
        notification_type: str,
        message: str,
        severity: str = "info"
    ) -> bool:
        """
        Envoie une notification système via l'API Mail Service CBC.
        
        Args:
            notification_type: Type de notification système
            message: Message de la notification
            severity: Gravité de la notification
        
        Returns:
            True si l'envoi a réussi, False sinon
        """
        if not settings.messaging_enabled:
            logger.info("Service de messagerie désactivé. Notification non envoyée.")
            return False
        
        # Récupérer les destinataires depuis la configuration
        try:
            recipients = json.loads(settings.messaging_recipients)
            if not recipients:
                logger.warning("Aucun destinataire configuré. Notification non envoyée.")
                return False
        except json.JSONDecodeError:
            logger.error("Erreur de décodage des destinataires. Notification non envoyée.")
            return False
        
        subject = f"[{notification_type}] {message}"
        
        body_lines = [
            f"<strong>Notification Système</strong>",
            f"",
            f"<strong>Type:</strong> {notification_type}",
            f"<strong>Message:</strong> {message}",
            f"<strong>Horodatage:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"",
            "---",
            "CBC Supervision Platform v1.1"
        ]
        
        body = "<br>".join(body_lines)
        
        return MessagingService._send_to_cbc_api(
            to=recipients,
            subject=subject,
            body=body,
            is_html=True
        )
    
    @staticmethod
    def health_check() -> Dict[str, Any]:
        """
        Effectue un health check du canal de notification via l'endpoint /health.
        
        Documentation API:
        - URL: /health
        - Méthode: GET
        - Auth: Non requise
        
        Réponse attendue:
        {"success":true,"status":"healthy","database":"connected","pending_mails":0}
        
        Returns:
            Dictionnaire contenant l'état du canal de notification
        """
        result = {
            "status": "unknown",
            "configured": MessagingService._is_configured(),
            "enabled": settings.messaging_enabled,
            "last_check": datetime.utcnow().isoformat(),
            "error": None,
            "api_response": None
        }
        
        if not result["configured"]:
            result["status"] = "error"
            result["error"] = "Configuration API CBC non définie"
            return result
        
        if not result["enabled"]:
            result["status"] = "disabled"
            return result
        
        # Appel réel à l'endpoint /health
        endpoint = f"{settings.messaging_api_endpoint}/health"
        
        try:
            response = requests.get(
                endpoint,
                timeout=settings.messaging_api_timeout
            )
            
            if response.status_code == 200:
                api_data = response.json()
                result["api_response"] = api_data
                
                # Analyser la réponse de l'API
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
            result["error"] = f"Timeout lors du health check (timeout: {settings.messaging_api_timeout}s)"
        except requests.exceptions.ConnectionError:
            result["status"] = "error"
            result["error"] = f"Erreur de connexion à l'API CBC: {endpoint}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Erreur inattendue lors du health check: {e}"
        
        return result
