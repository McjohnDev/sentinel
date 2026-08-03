import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from src.config import settings


class EmailService:
    """Service d'envoi d'emails pour les alertes."""
    
    @staticmethod
    def send_alert_email(
        recipient_email: str,
        alert_type: str,
        severity: str,
        message: str,
        hostname: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None
    ) -> bool:
        """Envoie un email d'alerte."""
        
        # Vérifier si la configuration SMTP est définie
        if not settings.smtp_host or not settings.smtp_username:
            print("Configuration SMTP non définie. Email non envoyé.")
            return False
        
        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[CBC Supervision] {severity.upper()} - {alert_type} sur {hostname}"
            msg['From'] = settings.email_from
            msg['To'] = recipient_email
            
            # Corps du message en HTML
            html_content = f"""
            <html>
            <body>
                <h2 style="color: red;">Alerte {severity.upper()}</h2>
                <p><strong>Type:</strong> {alert_type}</p>
                <p><strong>Machine:</strong> {hostname}</p>
                <p><strong>Message:</strong> {message}</p>
                {'<p><strong>Valeur:</strong> ' + str(value) + '</p>' if value is not None else ''}
                {'<p><strong>Seuil:</strong> ' + str(threshold) + '</p>' if threshold is not None else ''}
                <hr>
                <p style="color: gray; font-size: 12px;">
                    Ceci est un email automatique de CBC Supervision Platform.<br>
                    Veuillez ne pas répondre à cet email.
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # Connexion au serveur SMTP
            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            
            # Authentification
            server.login(settings.smtp_username, settings.smtp_password)
            
            # Envoi de l'email
            server.send_message(msg)
            server.quit()
            
            print(f"Email envoyé à {recipient_email}")
            return True
            
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email: {e}")
            return False
    
    @staticmethod
    def send_alert_email_to_admin(alert_data: dict) -> bool:
        """Envoie un email d'alerte à l'administrateur configuré."""
        
        if not settings.email_to:
            print("Aucun destinataire email configuré.")
            return False
        
        return EmailService.send_alert_email(
            recipient_email=settings.email_to,
            alert_type=alert_data.get('type', 'unknown'),
            severity=alert_data.get('severity', 'unknown'),
            message=alert_data.get('message', ''),
            hostname=alert_data.get('hostname', 'Unknown'),
            value=alert_data.get('value'),
            threshold=alert_data.get('threshold')
        )
