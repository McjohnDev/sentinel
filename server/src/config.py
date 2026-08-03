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
    app_version: str = "1.0.0"
    
    # Heartbeat
    heartbeat_timeout_seconds: int = 90
    offline_alert_threshold_seconds: int = 90
    
    # Seuils d'alerte par défaut
    cpu_warning_threshold: float = 80.0
    cpu_critical_threshold: float = 95.0
    ram_warning_threshold: float = 80.0
    ram_critical_threshold: float = 95.0
    disk_warning_threshold: float = 85.0
    disk_critical_threshold: float = 95.0
    
    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = ""
    email_to: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
