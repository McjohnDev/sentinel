import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration du serveur."""
    
    # Base de données (PostgreSQL pour la production)
    database_url: str = "postgresql://cbc_user:cbc_password@localhost:5432/cbc_supervision"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Self-hosted TSDB (VictoriaMetrics) — no cloud account
    victoria_metrics_url: str = "http://localhost:8428"
    loki_url: str = "http://localhost:3100"
    
    # SSL/TLS
    ssl_certfile: str = "ssl/cert.pem"
    ssl_keyfile: str = "ssl/key.pem"
    
    # Sécurité
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Application
    app_name: str = "CBC Supervision Platform"
    app_version: str = "1.1.0"
    
    # === FRÉQUENCES CONFIGURABLES (VALEURS PAR DÉFAUT TECHNIQUES) ===
    
    # Heartbeat
    heartbeat_interval_seconds: int = 30  # Intervalle d'envoi des heartbeats par l'agent
    #: Silence au-delà duquel un hôte est déclaré hors ligne.
    #:
    #: Porté de 90 s à 180 s : à 90 s, la cadence la plus lente encore sûre
    #: était de 60 s, ce qui interdisait d'espacer les battements sur un
    #: parc étendu. Contrepartie assumée : une panne réelle met désormais
    #: jusqu'à trois minutes à devenir visible.
    heartbeat_timeout_seconds: int = 180
    
    # Vérification offline
    offline_check_interval_seconds: int = 60  # Fréquence de vérification des agents offline
    
    # Supervision des services
    services_check_interval_seconds: int = 60  # Intervalle de vérification des services (VALEUR PAR DÉFAUT)
    
    # Supervision des fichiers
    files_check_interval_seconds: int = 300  # Intervalle de vérification des fichiers (VALEUR PAR DÉFAUT)
    
    # Health check du canal de notification
    notification_channel_health_check_interval_seconds: int = 60  # Fréquence du health check
    
    # === SEUILS OFFLINE PAR TYPE DE MACHINE (VALEURS PAR DÉFAUT TECHNIQUES) ===
    
    # Serveur : disponibilité 24/7 attendue
    server_offline_alert_threshold_seconds: int = 90  # À DÉFINIR PAR CBC - seuil pour les serveurs
    
    # Poste de travail : peut être éteint en dehors des heures de travail
    workstation_offline_alert_threshold_seconds: int = 7200  # À DÉFINIR PAR CBC - seuil pour les postes (2h par défaut)

    # Purge inventaire : agent sans heartbeat = considéré désinstallé / abandonné
    # (les postes éteints restent en base jusqu'à ce délai, mais n'apparaissent plus dans le parc "live")
    agent_stale_purge_after_seconds: int = 604800  # 7 jours
    agent_server_stale_purge_after_seconds: int = 86400  # 24h pour les serveurs

    # La purge ne s'exécute pas tant que la plateforme n'est pas restée en
    # ligne ce délai : au redémarrage, TOUS les agents paraissent silencieux
    # (c'est le serveur qui était absent, pas eux). Sans ce sas, une coupure
    # plateforme d'une nuit suffisait à effacer l'inventaire complet.
    agent_purge_startup_grace_seconds: int = 900  # 15 min

    # Un agent silencieux est d'abord « retiré » (ligne conservée, clé d'auth
    # conservée : s'il revient il se ré-active seul, sans nouveau jeton), et
    # n'est réellement supprimé qu'après ce second délai.
    agent_retired_delete_after_seconds: int = 2592000  # 30 jours
    
    # === SEUILS D'ALERTE PAR DÉFAUT (VALEURS PAR DÉFAUT TECHNIQUES) ===
    
    cpu_warning_threshold: float = 80.0
    cpu_critical_threshold: float = 95.0
    ram_warning_threshold: float = 80.0
    ram_critical_threshold: float = 95.0
    disk_warning_threshold: float = 85.0
    disk_critical_threshold: float = 95.0
    
    # === API DE MESSAGERIE INTERNE CBC (Mail Service) ===
    
    # URL de base : http://lumen-mail-service.test (local) ou http://172.16.8.113 (réseau interne)
    messaging_api_endpoint: str = "http://lumen-mail-service.test"  # CBC_MAIL_API_ENDPOINT
    messaging_api_key: str = ""  # CBC_MAIL_API_KEY (sécurisé)
    messaging_api_timeout: int = 30
    messaging_enabled: bool = True
    messaging_recipients: str = "[]"  # JSON array des destinataires
    
    # === SUPERVISION DES SERVICES SYSTÈME (PARAMÉTRABLE) ===
    
    services_monitoring_enabled: bool = False  # À ACTIVER par CBC si nécessaire
    services_monitoring_list: str = "[]"  # JSON array des services à superviser (ex: ["SWIFT AutoClient", "SQL Server"])
    services_monitoring_interval: int = 60  # Intervalle de vérification en secondes
    
    # === SUPERVISION DES FICHIERS (PARAMÉTRABLE) ===
    
    files_monitoring_enabled: bool = False  # À ACTIVER par CBC si nécessaire
    files_monitoring_list: str = "[]"  # JSON array des fichiers à superviser (ex: [{"path": "/var/log/swift.log", "max_size_mb": 100}])
    files_monitoring_interval: int = 300  # Intervalle de vérification en secondes

    # FS7 — load / hardening toggles (never enable in production unless intentional)
    rate_limit_disabled: bool = False
    allow_load_sim: bool = False

    # === ANNUAIRE D'ENTREPRISE — LDAP / ACTIVE DIRECTORY (API-003) ===

    ldap_enabled: bool = False
    # ldaps://dc01.cbcam.cm:636 en production ; ldap://… + START TLS accepté.
    ldap_server_uri: str = ""
    # Compte de service en lecture seule utilisé pour rechercher les comptes
    # avant le bind d'authentification.
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_user_search_base: str = ""
    # {username} est remplacé par la saisie, échappée selon la RFC 4515.
    # Active Directory : (&(objectClass=user)(sAMAccountName={username}))
    ldap_user_filter: str = "(&(objectClass=person)(uid={username}))"
    # Le formulaire accepte un nom de connexion OU une adresse email. Quand
    # l'identifiant saisi ressemble à une adresse et que le filtre principal ne
    # trouve rien, on retente sur l'attribut mail plutôt que de refuser.
    ldap_allow_email_login: bool = True
    #: {username} = identifiant saisi, {email_attr} = `ldap_attr_email`.
    ldap_user_email_filter: str = "(&(objectClass=person)({email_attr}={username}))"
    ldap_attr_username: str = "uid"
    ldap_attr_email: str = "mail"
    ldap_attr_display_name: str = "cn"
    ldap_attr_member_of: str = "memberOf"
    # Attributs d'annuaire complémentaires, repris dans l'inventaire des
    # comptes (matricule, service, agence…). Laisser vide pour ignorer.
    ldap_attr_employee_id: str = "employeeID"
    ldap_attr_department: str = "department"
    ldap_attr_phone: str = "telephoneNumber"
    ldap_attr_office: str = "physicalDeliveryOfficeName"
    ldap_attr_title: str = "title"
    # Active Directory renvoie des référencements (referrals) que le client
    # suit par défaut ; ils échouent alors sur un bind anonyme et font
    # apparaître la recherche comme infructueuse. Tous les clients AD les
    # désactivent — d'où la valeur par défaut.
    ldap_follow_referrals: bool = False
    # Taille de page pour les recherches renvoyant plusieurs entrées.
    ldap_page_size: int = 250
    # JSON {"CN=SOC,OU=Groupes,DC=cbc,DC=cm": "operator"} — le premier groupe
    # correspondant l'emporte, mettre les rôles privilégiés en tête.
    ldap_role_mapping: str = "{}"
    # Rôle attribué quand aucun groupe ne correspond. Volontairement le moins
    # privilégié : un compte d'annuaire ne doit pas obtenir de droits par défaut.
    ldap_default_role: str = "read_only"
    ldap_use_ssl: bool = True
    ldap_start_tls: bool = False
    ldap_tls_verify: bool = True
    ldap_ca_cert_file: str = ""
    ldap_timeout_seconds: int = 5
    # Conserver l'authentification locale en secours : sans cela, une panne
    # d'annuaire ferme l'accès à la plateforme, y compris à l'administrateur.
    ldap_allow_local_fallback: bool = True

    # === ORDONNANCEUR DE TÂCHES PÉRIODIQUES ===

    # Porte la détection hors ligne, l'escalade, la santé plateforme et la
    # purge d'inventaire. Ne désactiver que pour les tests unitaires, qui
    # n'ont ni Redis, ni TSDB, ni Loki joignables.
    scheduler_enabled: bool = True

    # === ENRÔLEMENT DES AGENTS (SEC-001 / AGT-004) ===

    # Jeton d'amorçage optionnel, réservé aux laboratoires. Non défini par
    # défaut : en production les jetons sont émis en base par un
    # administrateur (table enrollment_tokens) et sont à usage unique.
    bootstrap_enrollment_token: Optional[str] = None
    # N'autoriser la réutilisation du jeton d'amorçage qu'explicitement, pour
    # les démos où plusieurs agents s'enrôlent avec le même jeton.
    bootstrap_token_reusable: bool = False
    # Durée de validité par défaut d'un jeton émis par l'API d'administration.
    enrollment_token_ttl_hours: int = 24
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
