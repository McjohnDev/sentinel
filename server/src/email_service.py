"""Envoi de courriel par un relais SMTP interne.

Second canal, indépendant de l'API Mail CBC. Les deux coexistent
délibérément : un relais SMTP interne reste joignable quand l'API est en
panne, et inversement. Une plateforme de supervision qui perd sa seule voie
de notification devient muette au moment précis où elle doit parler.

**Réécriture complète.** L'implémentation précédente lisait
`settings.smtp_host` — un attribut qui n'existe pas dans `Settings` : le
premier appel réel aurait levé `AttributeError`. Elle n'était appelée nulle
part, ce qui explique que personne ne s'en soit aperçu. Elle composait en
outre son propre HTML, court-circuitant les gabarits par vérification : deux
mises en forme concurrentes pour le même incident selon le canal emprunté.

La configuration vit désormais en base, réglable depuis l'interface : un
relais SMTP change d'adresse ou de mot de passe sans qu'on redéploie le
produit pour autant.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.models import MessagingConfig

logger = logging.getLogger(__name__)

#: Au-delà, on renonce : un relais qui ne répond pas ne doit pas retenir le
#: traitement d'alerte derrière lui.
SMTP_TIMEOUT = 20

ENCRYPTION_NONE = "none"
ENCRYPTION_STARTTLS = "starttls"
ENCRYPTION_SSL = "ssl"


class SmtpNotConfigured(RuntimeError):
    """Le relais SMTP n'est pas exploitable en l'état."""


class SmtpSendFailed(RuntimeError):
    """L'envoi a échoué — message destiné à l'exploitant."""


def load_config(db: Session) -> Optional[MessagingConfig]:
    return db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()


def describe(cfg: Optional[MessagingConfig]) -> Dict[str, Any]:
    """Configuration telle qu'elle peut être rendue à l'interface.

    Le mot de passe n'en fait **jamais** partie : une clé qui repart vers le
    navigateur finit dans un cache, un journal de proxy ou une capture
    d'écran. Seule sa présence est signalée, pour que l'exploitant sache s'il
    doit le ressaisir.
    """
    if cfg is None:
        return {
            "enabled": False, "host": None, "port": 25, "auth": False,
            "username": None, "password_set": False, "encryption": ENCRYPTION_NONE,
            "from_address": None, "from_name": None, "verify_cert": True,
        }
    return {
        "enabled": bool(cfg.smtp_enabled),
        "host": cfg.smtp_host,
        "port": cfg.smtp_port or 25,
        "auth": bool(cfg.smtp_auth),
        "username": cfg.smtp_username,
        "password_set": bool(cfg.smtp_password),
        "encryption": cfg.smtp_encryption or ENCRYPTION_NONE,
        "from_address": cfg.smtp_from,
        "from_name": cfg.smtp_from_name,
        "verify_cert": bool(getattr(cfg, "smtp_verify_cert", True)),
    }


def _require_usable(cfg: Optional[MessagingConfig]) -> MessagingConfig:
    if cfg is None or not cfg.smtp_enabled:
        raise SmtpNotConfigured("Le relais SMTP n'est pas activé.")
    if not cfg.smtp_host:
        raise SmtpNotConfigured("Aucun serveur SMTP renseigné.")
    if not cfg.smtp_from:
        raise SmtpNotConfigured("Aucune adresse d'expéditeur renseignée.")
    if cfg.smtp_auth and not (cfg.smtp_username and cfg.smtp_password):
        raise SmtpNotConfigured(
            "Authentification demandée mais identifiant ou mot de passe manquant."
        )
    return cfg


def _tls_context(cfg: MessagingConfig) -> ssl.SSLContext:
    """Contexte TLS, selon que le certificat du relais est vérifié ou non."""
    context = ssl.create_default_context()
    if getattr(cfg, "smtp_verify_cert", True) is False:
        # Choix explicite de l'exploitant. Le trafic reste chiffré — le mot de
        # passe ne circule plus en clair — mais l'identité du relais n'est plus
        # attestée. Acceptable sur un lien interne maîtrisé, jamais au-delà.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.warning(
            "Certificat du relais SMTP non vérifié (réglage explicite) : le "
            "trafic est chiffré mais l'identité du serveur n'est pas attestée."
        )
    return context


def _connect(cfg: MessagingConfig):
    encryption = (cfg.smtp_encryption or ENCRYPTION_NONE).lower()
    host, port = cfg.smtp_host, int(cfg.smtp_port or 25)

    if encryption == ENCRYPTION_SSL:
        return smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT, context=_tls_context(cfg))

    server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)
    if encryption == ENCRYPTION_STARTTLS:
        server.starttls(context=_tls_context(cfg))
    return server


def send(
    db: Session,
    *,
    to: Any,
    subject: str,
    body_html: str,
    cfg: Optional[MessagingConfig] = None,
) -> bool:
    """Envoie un courriel par le relais SMTP configuré.

    `to` accepte une adresse ou une liste : toujours normalisé en liste, comme
    pour l'API Mail — faire varier le type d'un champ avec le nombre de
    destinataires oblige à supporter les deux formes partout.
    """
    settings = _require_usable(cfg if cfg is not None else load_config(db))

    recipients = [to] if isinstance(to, str) else list(to or [])
    recipients = [r for r in recipients if r]
    if not recipients:
        raise SmtpSendFailed("Aucun destinataire.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_from_name or "", settings.smtp_from))
    message["To"] = ", ".join(recipients)
    # Une version texte accompagne le HTML : certains clients de messagerie
    # bancaires refusent le HTML seul, et un courriel d'alerte illisible ne
    # vaut pas mieux qu'un courriel non envoyé.
    message.set_content("Alerte CBC Supervision. Ce message requiert un lecteur HTML.")
    message.add_alternative(body_html, subtype="html")

    try:
        server = _connect(settings)
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpSendFailed("Relais %s injoignable : %s" % (settings.smtp_host, exc))

    try:
        if settings.smtp_auth:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message, to_addrs=recipients)
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpSendFailed("Authentification refusée par le relais : %s" % exc)
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpSendFailed("Envoi refusé par le relais : %s" % exc)
    finally:
        try:
            server.quit()
        except Exception:
            # Le message est parti ; un adieu raté ne doit pas transformer un
            # succès en échec.
            pass

    logger.info("Courriel SMTP envoyé à %d destinataire(s).", len(recipients))
    return True
