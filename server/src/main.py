from fastapi import FastAPI, HTTPException, Depends, Header, status, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, validator, EmailStr, constr
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import uuid
import re
import logging
import json
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, generate_latest

from src.database import get_db, engine, Base
from src.models import (
    Agent, Heartbeat, Alert, AlertType, User, GlobalSettings, 
    MessagingConfig, RetentionConfig, EnrollmentToken, MachineType,
    NotificationChannelStatus, ServiceMonitoring, FileMonitoring
)
from src.config import settings
from src.alert_service import AlertService
from src.auth_service import AuthService
from src.permissions import require_auth, require_admin, require_operator_or_admin
from src.audit_logger import audit_logger
from src.websocket_manager import manager
from src.cache_service import cache_service
from src.messaging_service import MessagingService

# Configuration du logging structuré
class JSONFormatter(logging.Formatter):
    """Formatter pour les logs en format JSON."""
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

# Configuration du logger principal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Handler pour fichier avec format JSON
file_handler = logging.FileHandler("logs/application.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(JSONFormatter())

# Handler pour console avec format JSON
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(JSONFormatter())

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Métriques Prometheus
http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
http_request_duration_seconds = Histogram('http_request_duration_seconds', 'HTTP request duration')
active_agents = Gauge('active_agents', 'Number of active agents')
total_alerts = Gauge('total_alerts', 'Total number of alerts', ['severity'])
websocket_connections = Gauge('websocket_connections', 'Number of active WebSocket connections')

# Créer les tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CBC Supervision Platform API",
    description="API pour la plateforme de supervision CBC - Gestion des agents, alertes et métriques système",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# Pydantic models pour les requêtes
class EnrollRequest(BaseModel):
    token: constr(min_length=10, max_length=100)
    machine_id: constr(min_length=1, max_length=255)
    hostname: constr(min_length=1, max_length=255)
    os: constr(min_length=1, max_length=50)
    os_version: Optional[constr(max_length=50)] = None
    agent_version: constr(min_length=1, max_length=50)
    machine_type: constr(min_length=1, max_length=20) = "workstation"  # "server" ou "workstation"
    availability_config: Optional[Dict[str, Any]] = None  # Configuration des fenêtres horaires
    
    @validator('token')
    def validate_token(cls, v):
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError('Token invalide')
        return v
    
    @validator('machine_id')
    def validate_machine_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError('Machine ID invalide')
        return v
    
    @validator('hostname')
    def validate_hostname(cls, v):
        if not re.match(r'^[a-zA-Z0-9\-_\.]+$', v):
            raise ValueError('Hostname invalide')
        return v
    
    @validator('machine_type')
    def validate_machine_type(cls, v):
        if v.lower() not in ['server', 'workstation']:
            raise ValueError('machine_type doit être "server" ou "workstation"')
        return v.lower()


class EnrollResponse(BaseModel):
    agent_id: str
    auth_key: str
    message: str


class HeartbeatRequest(BaseModel):
    timestamp: datetime
    cpu_percent: float
    cpu_cores: int
    ram_percent: float
    ram_total_gb: float
    ram_used_gb: float
    ram_free_gb: float
    disk_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    uptime_seconds: int
    services: Optional[list] = []  # Liste des services supervisés
    files: Optional[list] = []  # Liste des fichiers supervisés
    
    @validator('cpu_percent', 'ram_percent', 'disk_percent')
    def validate_percent(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Le pourcentage doit être entre 0 et 100')
        return v
    
    @validator('cpu_cores')
    def validate_cpu_cores(cls, v):
        if v < 1:
            raise ValueError('Le nombre de cœurs doit être au moins 1')
        return v
    
    @validator('uptime_seconds')
    def validate_uptime(cls, v):
        if v < 0:
            raise ValueError('L\'uptime ne peut pas être négatif')
        return v


class LoginRequest(BaseModel):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8, max_length=128)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Username invalide')
        return v


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: str
    username: str
    role: str


class CreateUserRequest(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    role: Optional[constr(min_length=1, max_length=20)] = "operator"
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Username invalide')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['admin', 'operator', 'read_only']
        if v.lower() not in valid_roles:
            raise ValueError(f'Rôle invalide. Rôles valides: {", ".join(valid_roles)}')
        return v.lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class AcknowledgeAlertRequest(BaseModel):
    comment: Optional[str] = None


class ResolveAlertRequest(BaseModel):
    comment: Optional[str] = None


class UpdateAgentThresholdsRequest(BaseModel):
    cpu_warning_threshold: Optional[float] = None
    cpu_critical_threshold: Optional[float] = None
    ram_warning_threshold: Optional[float] = None
    ram_critical_threshold: Optional[float] = None
    disk_warning_threshold: Optional[float] = None
    disk_critical_threshold: Optional[float] = None

    @validator('cpu_warning_threshold', 'cpu_critical_threshold', 'ram_warning_threshold', 'ram_critical_threshold', 'disk_warning_threshold', 'disk_critical_threshold')
    def validate_threshold(cls, v):
        if v is not None and not 0 <= v <= 100:
            raise ValueError('Le seuil doit être entre 0 et 100')
        return v


# New Pydantic models for settings endpoints
class GlobalThresholdsRequest(BaseModel):
    cpu_warning: float
    cpu_critical: float
    ram_warning: float
    ram_critical: float
    disk_warning: float
    disk_critical: float

    @validator('cpu_warning', 'cpu_critical', 'ram_warning', 'ram_critical', 'disk_warning', 'disk_critical')
    def validate_threshold(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Le seuil doit être entre 0 et 100')
        return v


class MessagingConfigRequest(BaseModel):
    recipients: list
    api_endpoint: str
    api_key: str
    api_timeout: int = 30
    enabled: bool = True


class RetentionConfigRequest(BaseModel):
    alerts_days: int
    heartbeats_days: int

    @validator('alerts_days', 'heartbeats_days')
    def validate_days(cls, v):
        if v < 1:
            raise ValueError('Le nombre de jours doit être au moins 1')
        return v


class ServicesMonitoringConfigRequest(BaseModel):
    enabled: bool
    services: list
    interval: int = 60

    @validator('interval')
    def validate_interval(cls, v):
        if v < 10:
            raise ValueError('L\'intervalle doit être au moins 10 secondes')
        return v


class FilesMonitoringConfigRequest(BaseModel):
    enabled: bool
    files: list
    interval: int = 300

    @validator('interval')
    def validate_interval(cls, v):
        if v < 10:
            raise ValueError('L\'intervalle doit être au moins 10 secondes')
        return v


class UpdateAgentLocationRequest(BaseModel):
    location: str


class UpdateAgentNameRequest(BaseModel):
    name: str


# Stockage simple des tokens (en production, utiliser une base de données avec expiration)
enrollment_tokens = {
    "demo-token-123": {"used": False, "expires_at": None}
}


def verify_agent(authorization: str = Header(...), db: Session = Depends(get_db)):
    """Vérifie l'authentification de l'agent."""
    agent = db.query(Agent).filter(Agent.auth_key == authorization).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Authentification invalide")
    return agent.id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Récupère l'utilisateur actuel à partir du token JWT."""
    user_id = AuthService.verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = AuthService.get_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@app.get("/")
def root():
    """Endpoint racine pour vérifier que le serveur fonctionne."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Endpoint de health check pour les sondes de santé."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    """Endpoint de health check pour la base de données."""
    try:
        # Exécuter une requête simple pour vérifier la connexion
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@app.get("/metrics")
def metrics():
    """Endpoint pour les métriques Prometheus."""
    return generate_latest()


@app.post("/api/agents/enroll", response_model=EnrollResponse)
@limiter.limit("20/minute")  # Limite à 20 enrôlements par minute
def enroll_agent(request: Request, enroll_request: EnrollRequest, db: Session = Depends(get_db)):
    """
    Enrôle un nouvel agent.
    
    L'agent fournit un jeton d'enrôlement, son machine_id et ses informations.
    Le serveur valide le jeton et crée l'agent dans la base de données.
    """
    # Récupérer l'adresse IP du client
    client_ip = request.client.host if request.client else "unknown"
    
    # Vérifier si le token est valide
    if enroll_request.token not in enrollment_tokens:
        audit_logger.log_agent_enrollment("unknown", enroll_request.hostname, client_ip, success=False)
        raise HTTPException(status_code=401, detail="Token d'enrôlement invalide")
    
    token_info = enrollment_tokens[enroll_request.token]
    if token_info["used"]:
        audit_logger.log_agent_enrollment("unknown", enroll_request.hostname, client_ip, success=False)
        raise HTTPException(status_code=400, detail="Token déjà utilisé")
    
    # Vérifier si l'agent existe déjà
    existing_agent = db.query(Agent).filter(Agent.machine_id == enroll_request.machine_id).first()
    if existing_agent:
        # Mettre à jour l'agent existant
        existing_agent.hostname = enroll_request.hostname
        existing_agent.os = enroll_request.os
        existing_agent.os_version = enroll_request.os_version
        existing_agent.agent_version = enroll_request.agent_version
        existing_agent.machine_type = enroll_request.machine_type
        existing_agent.status = "active"
        existing_agent.last_communication = datetime.utcnow()
        db.commit()
        
        audit_logger.log_agent_enrollment(existing_agent.id, enroll_request.hostname, client_ip, success=True)
        return EnrollResponse(
            agent_id=existing_agent.id,
            auth_key=existing_agent.auth_key,
            message="Agent mis à jour avec succès"
        )
    
    # Créer un nouvel agent
    auth_key = str(uuid.uuid4())
    agent = Agent(
        id=str(uuid.uuid4()),
        machine_id=enroll_request.machine_id,
        hostname=enroll_request.hostname,
        ip_address="",  # Sera rempli lors du premier heartbeat
        os=enroll_request.os,
        os_version=enroll_request.os_version,
        agent_version=enroll_request.agent_version,
        machine_type=enroll_request.machine_type,
        auth_key=auth_key,
        status="active",
        enrolled_at=datetime.utcnow(),
        last_communication=datetime.utcnow()
    )
    
    db.add(agent)
    db.commit()
    
    # Créer la politique de disponibilité si fournie
    if enroll_request.availability_config:
        availability_policy = AvailabilityPolicy(
            id=agent.id,  # Utiliser l'agent_id comme ID pour la politique spécifique
            agent_id=agent.id,
            time_windows_enabled=enroll_request.availability_config.get('enabled', False),
            time_windows=json.dumps(enroll_request.availability_config.get('time_windows', {})),
            offline_threshold_seconds=enroll_request.availability_config.get('offline_threshold_seconds')
        )
        db.add(availability_policy)
        db.commit()
    
    # Invalider le cache des agents
    cache_service.delete_pattern("agents:*")
    
    # Marquer le token comme utilisé
    token_info["used"] = True
    
    audit_logger.log_agent_enrollment(agent.id, enroll_request.hostname, client_ip, success=True)
    return EnrollResponse(
        agent_id=agent.id,
        auth_key=auth_key,
        message="Agent enregistré avec succès"
    )


@app.post("/api/agents/heartbeat")
def receive_heartbeat(
    heartbeat: HeartbeatRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """
    Reçoit un heartbeat d'un agent.
    
    L'agent envoie ses métriques système. Le serveur les stocke et met à jour
    la dernière communication de l'agent, puis vérifie les alertes.
    """
    # Récupérer l'agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    
    if agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent n'est pas actif")
    
    # Créer le heartbeat
    heartbeat_record = Heartbeat(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        timestamp=heartbeat.timestamp,
        cpu_percent=heartbeat.cpu_percent,
        cpu_cores=heartbeat.cpu_cores,
        ram_percent=heartbeat.ram_percent,
        ram_total_gb=heartbeat.ram_total_gb,
        ram_used_gb=heartbeat.ram_used_gb,
        ram_free_gb=heartbeat.ram_free_gb,
        disk_percent=heartbeat.disk_percent,
        disk_total_gb=heartbeat.disk_total_gb,
        disk_used_gb=heartbeat.disk_used_gb,
        disk_free_gb=heartbeat.disk_free_gb,
        uptime_seconds=heartbeat.uptime_seconds
    )
    
    db.add(heartbeat_record)
    
    # Mettre à jour la dernière communication de l'agent
    agent.last_communication = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Vérifier les alertes de services et fichiers si des données sont fournies
    if heartbeat.services:
        AlertService.check_service_alerts(db, agent_id, heartbeat.services)
    
    if heartbeat.files:
        AlertService.check_file_alerts(db, agent_id, heartbeat.files)
    
    # Invalider le cache des agents (la dernière communication a changé)
    cache_service.delete_pattern("agents:*")
    
    # Vérifier si l'agent est revenu en ligne
    AlertService.check_back_online(db, agent_id)
    
    # Vérifier les alertes CPU
    AlertService.check_cpu_alert(db, agent_id, heartbeat.cpu_percent)
    
    # Vérifier les alertes RAM
    AlertService.check_ram_alert(db, agent_id, heartbeat.ram_percent)
    
    # Vérifier les alertes Disque
    AlertService.check_disk_alert(db, agent_id, heartbeat.disk_percent)
    
    # Résoudre les alertes si les valeurs sont revenues sous le seuil
    AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.CPU_HIGH, heartbeat.cpu_percent)
    AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.RAM_HIGH, heartbeat.ram_percent)
    AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.DISK_HIGH, heartbeat.disk_percent)
    
    return {"status": "success", "message": "Heartbeat reçu"}


@app.get("/api/agents")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def list_agents(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """Liste tous les agents (nécessite authentification) avec pagination et cache."""
    if limit > 1000:
        limit = 1000  # Limite maximale pour éviter les requêtes trop lourdes
    
    # Clé de cache
    cache_key = f"agents:{skip}:{limit}"
    
    # Essayer de récupérer depuis le cache
    cached_data = cache_service.get(cache_key)
    if cached_data:
        return cached_data
    
    # Sinon, interroger la base de données
    agents = db.query(Agent).order_by(Agent.enrolled_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Agent).count()
    
    result = {
        "data": [
            {
                "id": agent.id,
                "machine_id": agent.machine_id,
                "hostname": agent.hostname,
                "os": agent.os,
                "status": agent.status,
                "last_communication": agent.last_communication,
                "enrolled_at": agent.enrolled_at
            }
            for agent in agents
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "has_more": skip + limit < total
        }
    }
    
    # Stocker dans le cache (TTL: 30 secondes)
    cache_service.set(cache_key, result, ttl=30)
    
    return result


@app.get("/api/agents/{agent_id}")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def get_agent(request: Request, agent_id: str, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    """Récupère les détails d'un agent (nécessite authentification)."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    
    # Récupérer le dernier heartbeat
    last_heartbeat = db.query(Heartbeat).filter(
        Heartbeat.agent_id == agent_id
    ).order_by(Heartbeat.timestamp.desc()).first()
    
    return {
        "id": agent.id,
        "machine_id": agent.machine_id,
        "hostname": agent.hostname,
        "ip_address": agent.ip_address,
        "os": agent.os,
        "os_version": agent.os_version,
        "agent_version": agent.agent_version,
        "status": agent.status,
        "last_communication": agent.last_communication,
        "enrolled_at": agent.enrolled_at,
        "last_heartbeat": {
            "timestamp": last_heartbeat.timestamp if last_heartbeat else None,
            "cpu_percent": last_heartbeat.cpu_percent if last_heartbeat else None,
            "cpu_cores": last_heartbeat.cpu_cores if last_heartbeat else None,
            "cpu_architecture": last_heartbeat.cpu_architecture if last_heartbeat else None,
            "ram_percent": last_heartbeat.ram_percent if last_heartbeat else None,
            "ram_total_gb": last_heartbeat.ram_total_gb if last_heartbeat else None,
            "ram_used_gb": last_heartbeat.ram_used_gb if last_heartbeat else None,
            "ram_free_gb": last_heartbeat.ram_free_gb if last_heartbeat else None,
            "disk_percent": last_heartbeat.disk_percent if last_heartbeat else None,
            "disk_total_gb": last_heartbeat.disk_total_gb if last_heartbeat else None,
            "disk_used_gb": last_heartbeat.disk_used_gb if last_heartbeat else None,
            "disk_free_gb": last_heartbeat.disk_free_gb if last_heartbeat else None,
            "uptime_seconds": last_heartbeat.uptime_seconds if last_heartbeat else None,
            "latency_ms": last_heartbeat.latency_ms if last_heartbeat else None,
            "temperature_celsius": last_heartbeat.temperature_celsius if last_heartbeat else None,
        } if last_heartbeat else None
    }


@app.put("/api/agents/{agent_id}/thresholds")
@limiter.limit("50/minute")  # Limite à 50 mises à jour par minute
def update_agent_thresholds(
    request: Request,
    agent_id: str,
    thresholds: UpdateAgentThresholdsRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db)
):
    """Met à jour les seuils d'alerte d'un agent (nécessite rôle operator ou admin)."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    
    # Mettre à jour uniquement les seuils fournis
    if thresholds.cpu_warning_threshold is not None:
        agent.cpu_warning_threshold = thresholds.cpu_warning_threshold
    if thresholds.cpu_critical_threshold is not None:
        agent.cpu_critical_threshold = thresholds.cpu_critical_threshold
    if thresholds.ram_warning_threshold is not None:
        agent.ram_warning_threshold = thresholds.ram_warning_threshold
    if thresholds.ram_critical_threshold is not None:
        agent.ram_critical_threshold = thresholds.ram_critical_threshold
    if thresholds.disk_warning_threshold is not None:
        agent.disk_warning_threshold = thresholds.disk_warning_threshold
    if thresholds.disk_critical_threshold is not None:
        agent.disk_critical_threshold = thresholds.disk_critical_threshold
    
    agent.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "id": agent.id,
        "cpu_warning_threshold": agent.cpu_warning_threshold,
        "cpu_critical_threshold": agent.cpu_critical_threshold,
        "ram_warning_threshold": agent.ram_warning_threshold,
        "ram_critical_threshold": agent.ram_critical_threshold,
        "disk_warning_threshold": agent.disk_warning_threshold,
        "disk_critical_threshold": agent.disk_critical_threshold,
        "message": "Seuils mis à jour avec succès"
    }


@app.get("/api/agents/{agent_id}/heartbeats")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def get_agent_heartbeats(
    request: Request,
    agent_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    """Récupère l'historique des heartbeats d'un agent (nécessite authentification)."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    
    # Limiter le nombre de résultats pour éviter les surcharges
    limit = min(limit, 1000)
    
    heartbeats = db.query(Heartbeat).filter(
        Heartbeat.agent_id == agent_id
    ).order_by(Heartbeat.timestamp.desc()).offset(offset).limit(limit).all()
    
    return [
        {
            "timestamp": hb.timestamp,
            "cpu_percent": hb.cpu_percent,
            "cpu_cores": hb.cpu_cores,
            "cpu_architecture": hb.cpu_architecture,
            "ram_percent": hb.ram_percent,
            "ram_total_gb": hb.ram_total_gb,
            "ram_used_gb": hb.ram_used_gb,
            "ram_free_gb": hb.ram_free_gb,
            "disk_percent": hb.disk_percent,
            "disk_total_gb": hb.disk_total_gb,
            "disk_used_gb": hb.disk_used_gb,
            "disk_free_gb": hb.disk_free_gb,
            "uptime_seconds": hb.uptime_seconds,
            "latency_ms": hb.latency_ms,
            "temperature_celsius": hb.temperature_celsius
        }
        for hb in heartbeats
    ]


@app.get("/api/alerts")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def list_alerts(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """Liste toutes les alertes (nécessite authentification) avec pagination et cache."""
    if limit > 1000:
        limit = 1000  # Limite maximale pour éviter les requêtes trop lourdes
    
    # Clé de cache
    cache_key = f"alerts:{skip}:{limit}"
    
    # Essayer de récupérer depuis le cache
    cached_data = cache_service.get(cache_key)
    if cached_data:
        return cached_data
    
    # Sinon, interroger la base de données
    alerts = db.query(Alert).order_by(Alert.started_at.desc()).offset(skip).limit(limit).all()
    total = db.query(Alert).count()
    
    result = {
        "data": [
            {
                "id": alert.id,
                "agent_id": alert.agent_id,
                "severity": alert.severity.value,
                "type": alert.type.value,
                "message": alert.message,
                "status": alert.status.value,
                "value": alert.value,
                "threshold": alert.threshold,
                "started_at": alert.started_at,
                "resolved_at": alert.resolved_at,
                "acknowledged_at": alert.acknowledged_at,
                "acknowledged_by": alert.acknowledged_by
            }
            for alert in alerts
        ],
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "has_more": skip + limit < total
        }
    }
    
    # Stocker dans le cache (TTL: 30 secondes)
    cache_service.set(cache_key, result, ttl=30)
    
    return result


@app.get("/api/alerts/{alert_id}")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def get_alert(request: Request, alert_id: str, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    """Récupère les détails d'une alerte (nécessite authentification)."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    
    return {
        "id": alert.id,
        "agent_id": alert.agent_id,
        "severity": alert.severity.value,
        "type": alert.type.value,
        "message": alert.message,
        "status": alert.status.value,
        "value": alert.value,
        "threshold": alert.threshold,
        "started_at": alert.started_at,
        "resolved_at": alert.resolved_at,
        "acknowledged_at": alert.acknowledged_at,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_comment": alert.acknowledged_comment
    }


@app.post("/api/alerts/{alert_id}/acknowledge")
@limiter.limit("50/minute")  # Limite à 50 acquittements par minute
def acknowledge_alert(
    request: Request,
    alert_id: str,
    ack_request: AcknowledgeAlertRequest,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """Acquitte une alerte (nécessite authentification)."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    
    if alert.status.value != "active":
        raise HTTPException(status_code=400, detail="Seules les alertes actives peuvent être acquittées")
    
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.username
    alert.acknowledged_comment = ack_request.comment
    
    db.commit()
    
    # Log d'audit
    audit_logger.log_alert_acknowledged(alert_id, str(current_user.id), current_user.username)
    
    return {
        "id": alert.id,
        "status": alert.status.value,
        "acknowledged_at": alert.acknowledged_at,
        "acknowledged_by": alert.acknowledged_by,
        "message": "Alerte acquittée avec succès"
    }


@app.post("/api/alerts/{alert_id}/resolve")
@limiter.limit("50/minute")  # Limite à 50 résolutions par minute
def resolve_alert(
    request: Request,
    alert_id: str,
    resolve_request: ResolveAlertRequest,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """Résout une alerte (nécessite authentification)."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    
    if alert.status.value == "resolved":
        raise HTTPException(status_code=400, detail="Alerte déjà résolue")
    
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    alert.acknowledged_by = current_user.username
    alert.acknowledged_comment = resolve_request.comment
    
    db.commit()
    
    # Log d'audit
    audit_logger.log_alert_resolved(alert_id, str(current_user.id), current_user.username)
    
    return {
        "id": alert.id,
        "status": alert.status.value,
        "resolved_at": alert.resolved_at,
        "resolved_by": alert.acknowledged_by,
        "message": "Alerte résolue avec succès"
    }


# Endpoints d'authentification
@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # Limite à 5 tentatives par minute par IP
def login(request: Request, login_request: LoginRequest, db: Session = Depends(get_db)):
    """Authentifie un utilisateur et retourne un token JWT."""
    print(f"Login request received: username={login_request.username}")
    user = AuthService.authenticate_user(db, login_request.username, login_request.password)
    
    # Récupérer l'adresse IP du client
    client_ip = request.client.host if request.client else "unknown"
    
    if not user:
        print(f"Authentication failed for username={login_request.username}")
        audit_logger.log_login(login_request.username, "unknown", client_ip, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"Authentication successful for username={login_request.username}")
    audit_logger.log_login(login_request.username, str(user.id), client_ip, success=True)
    access_token = AuthService.create_access_token(data={"sub": user.id})
    refresh_token = AuthService.create_refresh_token(data={"sub": user.id})
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role.value
    )


@app.post("/api/auth/register")
@limiter.limit("10/minute")  # Limite à 10 créations par minute
def register(request: Request, register_request: CreateUserRequest, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Crée un nouvel utilisateur (nécessite authentification admin)."""
    try:
        from src.models import UserRole
        role = UserRole(register_request.role) if register_request.role else UserRole.OPERATOR
        user = AuthService.create_user(
            db,
            register_request.username,
            register_request.email,
            register_request.password,
            role
        )
        
        # Log de création d'utilisateur
        audit_logger.log_user_created(
            user_id=str(user.id),
            username=user.username,
            role=user.role.value,
            created_by=current_user.username
        )
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "message": "Utilisateur créé avec succès"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/refresh", response_model=RefreshTokenResponse)
@limiter.limit("20/minute")  # Limite à 20 refresh par minute
def refresh_token(request: Request, refresh_request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Rafraîchit un access token en utilisant un refresh token."""
    user_id = AuthService.verify_token(refresh_request.refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = AuthService.get_user(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur inactif ou inexistant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Générer de nouveaux tokens
    new_access_token = AuthService.create_access_token(data={"sub": user.id})
    new_refresh_token = AuthService.create_refresh_token(data={"sub": user.id})
    
    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Récupère les informations de l'utilisateur actuel."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value
    }


@app.get("/api/auth/users")
@limiter.limit("50/minute")  # Limite à 50 requêtes par minute
def list_users(request: Request, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Liste tous les utilisateurs (nécessite rôle admin)."""
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
        for user in users
    ]


@app.delete("/api/auth/users/{user_id}")
@limiter.limit("20/minute")  # Limite à 20 suppressions par minute
def delete_user(request: Request, user_id: str, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Supprime un utilisateur (nécessite rôle admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
    
    db.delete(user)
    db.commit()
    
    return {"message": "Utilisateur supprimé avec succès"}


# ==================== SETTINGS ENDPOINTS ====================

@app.get("/api/settings/thresholds")
@limiter.limit("30/minute")
def get_global_thresholds(request: Request, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Récupère les seuils globaux."""
    settings = db.query(GlobalSettings).filter(GlobalSettings.id == 'default').first()
    if not settings:
        # Créer les settings par défaut s'ils n'existent pas
        settings = GlobalSettings(id='default')
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return {
        "id": settings.id,
        "cpu_warning": settings.cpu_warning_threshold,
        "cpu_critical": settings.cpu_critical_threshold,
        "ram_warning": settings.ram_warning_threshold,
        "ram_critical": settings.ram_critical_threshold,
        "disk_warning": settings.disk_warning_threshold,
        "disk_critical": settings.disk_critical_threshold,
        "updated_at": settings.updated_at
    }


@app.put("/api/settings/thresholds")
@limiter.limit("20/minute")
def update_global_thresholds(request: Request, thresholds: GlobalThresholdsRequest, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Met à jour les seuils globaux."""
    settings = db.query(GlobalSettings).filter(GlobalSettings.id == 'default').first()
    if not settings:
        settings = GlobalSettings(id='default')
        db.add(settings)

    settings.cpu_warning_threshold = thresholds.cpu_warning
    settings.cpu_critical_threshold = thresholds.cpu_critical
    settings.ram_warning_threshold = thresholds.ram_warning
    settings.ram_critical_threshold = thresholds.ram_critical
    settings.disk_warning_threshold = thresholds.disk_warning
    settings.disk_critical_threshold = thresholds.disk_critical

    db.commit()
    db.refresh(settings)

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_GLOBAL_THRESHOLDS",
        details=f"Updated global thresholds: {thresholds.dict()}"
    )

    return {
        "id": settings.id,
        "cpu_warning": settings.cpu_warning_threshold,
        "cpu_critical": settings.cpu_critical_threshold,
        "ram_warning": settings.ram_warning_threshold,
        "ram_critical": settings.ram_critical_threshold,
        "disk_warning": settings.disk_warning_threshold,
        "disk_critical": settings.disk_critical_threshold,
        "updated_at": settings.updated_at
    }


@app.get("/api/settings/messaging")
@limiter.limit("30/minute")
def get_messaging_config(request: Request, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Récupère la configuration de messagerie API CBC."""
    config = db.query(MessagingConfig).filter(MessagingConfig.id == 'default').first()
    if not config:
        config = MessagingConfig(id='default')
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "id": config.id,
        "recipients": json.loads(config.recipients) if config.recipients else [],
        "api_endpoint": config.api_endpoint,
        "api_timeout": config.api_timeout,
        "enabled": config.enabled,
        "updated_at": config.updated_at
    }


@app.put("/api/settings/messaging")
@limiter.limit("20/minute")
def update_messaging_config(request: Request, config_request: MessagingConfigRequest, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Met à jour la configuration de messagerie API CBC."""
    config = db.query(MessagingConfig).filter(MessagingConfig.id == 'default').first()
    if not config:
        config = MessagingConfig(id='default')
        db.add(config)

    config.recipients = json.dumps(config_request.recipients)
    config.api_endpoint = config_request.api_endpoint
    config.api_key = config_request.api_key
    config.api_timeout = config_request.api_timeout
    config.enabled = config_request.enabled

    db.commit()
    db.refresh(config)

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_MESSAGING_CONFIG",
        details=f"Updated messaging configuration"
    )

    return {
        "id": config.id,
        "recipients": json.loads(config.recipients),
        "api_endpoint": config.api_endpoint,
        "api_timeout": config.api_timeout,
        "enabled": config.enabled,
        "updated_at": config.updated_at
    }


@app.get("/api/system/notification-channel-status")
@limiter.limit("60/minute")
def get_notification_channel_status(request: Request, current_user: User = Depends(require_operator_or_admin())):
    """
    Récupère le statut du canal de notification.
    
    Cet endpoint est utilisé par le frontend pour afficher l'indicateur visuel
    de l'état du canal de notification (exigence R11 de l'encadreur).
    """
    status = MessagingService.health_check()
    return status


@app.get("/api/settings/retention")
@limiter.limit("30/minute")
def get_retention_config(request: Request, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Récupère la configuration de rétention."""
    config = db.query(RetentionConfig).filter(RetentionConfig.id == 'default').first()
    if not config:
        config = RetentionConfig(id='default')
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "id": config.id,
        "alerts_days": config.alerts_days,
        "heartbeats_days": config.heartbeats_days,
        "updated_at": config.updated_at
    }


@app.put("/api/settings/retention")
@limiter.limit("20/minute")
def update_retention_config(request: Request, config_request: RetentionConfigRequest, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Met à jour la configuration de rétention."""
    config = db.query(RetentionConfig).filter(RetentionConfig.id == 'default').first()
    if not config:
        config = RetentionConfig(id='default')
        db.add(config)

    config.alerts_days = config_request.alerts_days
    config.heartbeats_days = config_request.heartbeats_days

    db.commit()
    db.refresh(config)

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_RETENTION_CONFIG",
        details=f"Updated retention config: alerts={config_request.alerts_days}d, heartbeats={config_request.heartbeats_days}d"
    )

    return {
        "id": config.id,
        "alerts_days": config.alerts_days,
        "heartbeats_days": config.heartbeats_days,
        "updated_at": config.updated_at
    }


@app.get("/api/settings/tokens")
@limiter.limit("30/minute")
def get_enrollment_tokens(request: Request, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Récupère tous les tokens d'enrôlement."""
    tokens = db.query(EnrollmentToken).order_by(EnrollmentToken.created_at.desc()).all()
    return [
        {
            "id": token.id,
            "token": token.token,
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "status": token.status,
            "created_by": token.created_by
        }
        for token in tokens
    ]


@app.post("/api/settings/tokens")
@limiter.limit("10/minute")
def generate_enrollment_token(request: Request, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Génère un nouveau token d'enrôlement."""
    import secrets
    import string

    # Générer un token aléatoire
    token_str = f"CBC-ENROLL-{''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))}-{datetime.now().year}"

    # Expiration dans 24h
    expires_at = datetime.now() + timedelta(hours=24)

    token = EnrollmentToken(
        id=str(uuid.uuid4()),
        token=token_str,
        expires_at=expires_at,
        status='active',
        created_by=current_user.username
    )

    db.add(token)
    db.commit()
    db.refresh(token)

    audit_logger.log_action(
        user_id=current_user.id,
        action="GENERATE_ENROLLMENT_TOKEN",
        details=f"Generated enrollment token: {token_str}"
    )

    return {
        "id": token.id,
        "token": token.token,
        "created_at": token.created_at,
        "expires_at": token.expires_at,
        "status": token.status,
        "created_by": token.created_by
    }


# ==================== ADDITIONAL AGENT ENDPOINTS ====================

@app.put("/api/agents/{agent_id}/revoke")
@limiter.limit("20/minute")
def revoke_agent(request: Request, agent_id: str, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Révoque un agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    agent.status = 'revoked'
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        action="REVOKE_AGENT",
        details=f"Revoked agent {agent_id} ({agent.hostname})"
    )

    return {"message": "Agent révoqué avec succès"}


@app.delete("/api/agents/{agent_id}")
@limiter.limit("10/minute")
def delete_agent(request: Request, agent_id: str, current_user: User = Depends(require_admin()), db: Session = Depends(get_db)):
    """Supprime un agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    db.delete(agent)
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        action="DELETE_AGENT",
        details=f"Deleted agent {agent_id} ({agent.hostname})"
    )

    return {"message": "Agent supprimé avec succès"}


@app.put("/api/agents/{agent_id}/location")
@limiter.limit("30/minute")
def update_agent_location(request: Request, agent_id: str, location_req: UpdateAgentLocationRequest, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Met à jour la localisation d'un agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    agent.location = location_req.location
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_AGENT_LOCATION",
        details=f"Updated location for agent {agent_id} to {location_req.location}"
    )

    return {"message": "Localisation mise à jour avec succès"}


@app.put("/api/agents/{agent_id}/name")
@limiter.limit("30/minute")
def update_agent_name(request: Request, agent_id: str, name_req: UpdateAgentNameRequest, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """Met à jour le nom d'un agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    agent.name = name_req.name
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_AGENT_NAME",
        details=f"Updated name for agent {agent_id} to {name_req.name}"
    )

    return {"message": "Nom mis à jour avec succès"}


@app.get("/api/settings/services-monitoring")
@limiter.limit("30/minute")
def get_services_monitoring_config(request: Request, current_user: User = Depends(require_operator_or_admin())):
    """Récupère la configuration de supervision des services système."""
    try:
        services_list = json.loads(settings.services_monitoring_list) if settings.services_monitoring_list else []
    except json.JSONDecodeError:
        services_list = []
    
    return {
        "enabled": settings.services_monitoring_enabled,
        "services": services_list,
        "interval": settings.services_monitoring_interval
    }


@app.put("/api/settings/services-monitoring")
@limiter.limit("20/minute")
def update_services_monitoring_config(request: Request, config_request: ServicesMonitoringConfigRequest, current_user: User = Depends(require_admin())):
    """Met à jour la configuration de supervision des services système."""
    # Note: En production, ces paramètres devraient être stockés en base de données
    # Pour l'instant, on utilise les variables d'environnement/settings
    # Pour permettre la modification dynamique, on pourrait utiliser un modèle de configuration en DB
    
    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_SERVICES_MONITORING_CONFIG",
        details=f"Updated services monitoring configuration: enabled={config_request.enabled}"
    )
    
    return {
        "message": "Configuration de supervision des services mise à jour",
        "enabled": config_request.enabled,
        "services": config_request.services,
        "interval": config_request.interval
    }


@app.get("/api/settings/files-monitoring")
@limiter.limit("30/minute")
def get_files_monitoring_config(request: Request, current_user: User = Depends(require_operator_or_admin())):
    """Récupère la configuration de supervision des fichiers."""
    try:
        files_list = json.loads(settings.files_monitoring_list) if settings.files_monitoring_list else []
    except json.JSONDecodeError:
        files_list = []
    
    return {
        "enabled": settings.files_monitoring_enabled,
        "files": files_list,
        "interval": settings.files_monitoring_interval
    }


@app.put("/api/settings/files-monitoring")
@limiter.limit("20/minute")
def update_files_monitoring_config(request: Request, config_request: FilesMonitoringConfigRequest, current_user: User = Depends(require_admin())):
    """Met à jour la configuration de supervision des fichiers."""
    # Note: En production, ces paramètres devraient être stockés en base de données
    # Pour l'instant, on utilise les variables d'environnement/settings
    # Pour permettre la modification dynamique, on pourrait utiliser un modèle de configuration en DB
    
    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_FILES_MONITORING_CONFIG",
        details=f"Updated files monitoring configuration: enabled={config_request.enabled}"
    )
    
    return {
        "message": "Configuration de supervision des fichiers mise à jour",
        "enabled": config_request.enabled,
        "files": config_request.files,
        "interval": config_request.interval
    }


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str, db: Session = Depends(get_db)):
    """Endpoint WebSocket pour les notifications en temps réel."""
    # Vérifier le token JWT
    user_id = AuthService.verify_token(token)
    if not user_id:
        await websocket.close(code=1008)
        return
    
    user = AuthService.get_user(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=1008)
        return
    
    # Connecter le WebSocket
    await manager.connect(websocket, user_id)
    
    try:
        # Envoyer un message de confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Connecté aux notifications en temps réel",
            "user_id": user_id
        })
        
        # Garder la connexion ouverte
        while True:
            # Recevoir des messages ping/pong pour garder la connexion alive
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_keyfile=settings.ssl_keyfile,
        ssl_certfile=settings.ssl_certfile
    )
