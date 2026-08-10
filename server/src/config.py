import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration du serveur."""
    
    # Base de données (PostgreSQL pour la production)
    database_url: str = "postgresql://cbc_user:cbc_password@localhost:5432/cbc_supervision"
    
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
    heartbeat_timeout_seconds: int = 90  # Timeout de réception des heartbeats côté serveur
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
