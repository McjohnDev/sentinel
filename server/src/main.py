from fastapi import FastAPI, File, HTTPException, Depends, Header, status, Request, UploadFile, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, validator, EmailStr, constr
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from typing import Optional, Dict, Any, List
import uuid
import re
import logging
import json
import asyncio
from datetime import datetime, timedelta, timezone
from prometheus_client import Counter, Histogram, Gauge, generate_latest

from src.database import get_db, engine, Base
from src.config_service import ConfigService, deep_merge as config_deep_merge
from src.messaging_service import MessagingService
from src.audit_logger import audit_logger
from src.websocket_manager import manager
from src.cache_service import cache_service
from src.permissions import (
    Permission,
    require_admin,
    require_auth,
    require_operator_or_admin,
    require_agent_scope,
    require_permission,
    serialize_permissions,
    user_administers_agent,
)
from src.auth_service import AuthService
from src.alert_service import AlertService
from src.config import settings
from src.agent_purge import (
    RETIRED,
    delete_agent_with_deps,
    derived_agent_status,
    is_lab_or_sim_agent,
    is_agent_live,
    last_seen_age_seconds,
    note_platform_start,
)
from src.presence import publish_agent_presence
from src import monitoring_plan
from src import vlan_service
from src.agent_identity import AgentIdExhaustedError, generate_agent_id, normalize_agent_id
from src.agent_rejections import ledger as agent_rejection_ledger
from src.models import (
    AGENT_EDITABLE_FIELDS, AGENT_IMMUTABLE_FIELDS, AdminGroup, AdminGroupMember,
    VlanSubnet,
    Agent, Heartbeat, Alert, AlertType, User, GlobalSettings, 
    MessagingConfig, RetentionConfig, EnrollmentToken, MachineType,
    UserRole, AuthSource, AuditLog, LdapRoleMapping,
    NotificationChannelStatus, ServiceMonitoring, FileMonitoring,
    AvailabilityPolicy, MaintenanceWindow, AlertEvent, AlertStatus,
    MachineGroup, ConfigRevision, CoverageOverlap,
    CustomDashboard, ReportSchedule, NetworkDevice, ExternalConnector,
    CoverageCheck, PilotHost, UatCase, AcceptanceSignOff,
    RemoteTask, ActionApproval, MailTemplate,
)

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
# Un agent vivant dont la clé n'est plus reconnue frappait à la porte sans
# que rien ne l'enregistre : ni alerte, ni compteur, ni trace exploitable.
# L'hôte disparaissait du parc et la plateforme restait silencieuse.
agent_auth_rejected_total = Counter(
    'agent_auth_rejected_total',
    "Heartbeats/pings refusés faute d'identité connue (agent à ré-enrôler)",
)

# Créer les tables
Base.metadata.create_all(bind=engine)
from src.schema_migrate import ensure_schema
ensure_schema(engine)
try:
    from src.database import SessionLocal
    from src.uat_service import ensure_coverage_seed, ensure_uat_seed

    _db = SessionLocal()
    try:
        ensure_coverage_seed(_db)
        ensure_uat_seed(_db)
    finally:
        _db.close()
except Exception:
    logger.exception("FS8 seed skipped")

from contextlib import asynccontextmanager
from src.scheduler import scheduler, register_default_jobs


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Cycle de vie de l'application.

    L'ordonnanceur porte les tâches périodiques (détection hors ligne,
    escalade, santé plateforme, purge). Elles tournaient auparavant dans le
    handler de heartbeat, ce qui les rendait muettes pendant une panne de parc.
    """
    manager.bind_loop(asyncio.get_running_loop())
    # Repère de démarrage : la purge d'inventaire s'en sert pour ne pas
    # imputer aux agents le silence dû à l'arrêt de la plateforme.
    note_platform_start()
    if settings.scheduler_enabled:
        register_default_jobs()
        scheduler.start()
    else:
        logger.warning("Ordonnanceur désactivé (SCHEDULER_ENABLED=false)")
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(
    title="CBC Supervision Platform API",
    description="API pour la plateforme de supervision CBC - Gestion des agents, alertes et métriques système",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Rate limiting (disable with RATE_LIMIT_DISABLED=true for FS7 load drills)
limiter = Limiter(key_func=get_remote_address, enabled=not settings.rate_limit_disabled)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        # Poste de developpement sur reseau local (ajoute par BRYAN-1-C, a3dc085).
        # A externaliser en variable d'environnement avant le pilote.
        "http://172.20.10.3:3000",
    ],
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
    ip_address: Optional[constr(max_length=45)] = None
    os: constr(min_length=1, max_length=50)
    os_version: Optional[constr(max_length=50)] = None
    agent_version: constr(min_length=1, max_length=50)
    machine_type: constr(min_length=1, max_length=20) = "workstation"  # "server" ou "workstation"
    availability_config: Optional[Dict[str, Any]] = None  # Configuration des fenêtres horaires
    # Caractéristiques matérielles constatées (point 2) : la plateforme les
    # enregistre mais n'autorise personne à les corriger à la main.
    cpu_cores: Optional[int] = None
    ram_total_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    # Comment et où l'agent s'exécute sur l'hôte (point 9).
    runtime: Optional[Dict[str, Any]] = None
    #: VLAN que l'hôte étiquette lui-même, s'il en étiquette un.
    vlan_observed: Optional[constr(max_length=64)] = None
    
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
    ip_address: Optional[constr(max_length=45)] = None
    disk_mount: Optional[str] = None
    disks: Optional[list] = []
    services: Optional[list] = []  # Liste des services supervisés
    files: Optional[list] = []  # Liste des fichiers supervisés
    config_version: Optional[int] = None
    agent_cpu_percent: Optional[float] = None
    agent_ram_mb: Optional[float] = None
    # Facteurs système redéclarés à chaque battement : ils n'étaient envoyés
    # qu'à l'enrôlement, si bien qu'une montée de version d'OS ou une mise à
    # jour de l'agent restait invisible dans l'inventaire jusqu'à un
    # ré-enrôlement — qui n'arrive jamais en fonctionnement normal.
    os: Optional[constr(max_length=50)] = None
    os_version: Optional[constr(max_length=50)] = None
    agent_version: Optional[constr(max_length=50)] = None
    hostname: Optional[constr(max_length=255)] = None
    runtime: Optional[Dict[str, Any]] = None
    vlan_observed: Optional[constr(max_length=64)] = None
    
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


#: Identifiant de connexion : nom de compte local, sAMAccountName, UPN
#: (`utilisateur@domaine`), forme `DOMAINE\utilisateur` ou adresse email.
#:
#: Le motif précédent — `^[a-zA-Z0-9_\-\.]+$`, 50 caractères — refusait
#: l'arobase : toute tentative avec une adresse email était rejetée en 422
#: avant même d'atteindre l'authentification. Une liste blanche de caractères
#: est le mauvais outil ici (elle exclut aussi les patronymes accentués que
#: l'annuaire accepte) : l'injection est déjà traitée là où elle compte, par
#: `_escape()` côté LDAP et par le paramétrage des requêtes SQLAlchemy. On se
#: contente donc d'interdire les caractères de contrôle.
LOGIN_IDENTIFIER_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f]")
LOGIN_IDENTIFIER_MAX = 254  # longueur maximale d'une adresse email (RFC 5321)


class LoginRequest(BaseModel):
    username: constr(min_length=1, max_length=LOGIN_IDENTIFIER_MAX)
    # Aucune politique de longueur ici : la robustesse est imposée à la
    # création du compte, et un mot de passe d'annuaire ne nous appartient
    # pas. Un minimum de 8 rejetait en 422 des identifiants valides.
    password: constr(min_length=1, max_length=256)

    @validator('username')
    def validate_username(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Identifiant requis')
        if LOGIN_IDENTIFIER_FORBIDDEN.search(v):
            raise ValueError('Identifiant invalide')
        return v


#: Statut d'un hôte dont l'agent a été désinstallé. Distinct de `retired`
#: (silence prolongé, constaté) : ici la machine a explicitement annoncé son
#: retrait, ce qui n'appelle ni alerte ni relance.
UNINSTALLED = "uninstalled"


class DeregisterRequest(BaseModel):
    """Corps facultatif du désenrôlement — motif transmis par la CLI."""

    reason: Optional[constr(max_length=500)] = None


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
        # Liste dérivée de l'énumération : ajouter un rôle ne doit pas obliger
        # à penser à mettre cette validation à jour (le rôle 'security' avait
        # été ajouté au modèle sans l'être ici).
        valid_roles = [r.value for r in UserRole]
        if v.lower() not in valid_roles:
            raise ValueError(f'Rôle invalide. Rôles valides: {", ".join(valid_roles)}')
        return v.lower()


class UpdateUserRequest(BaseModel):
    """Mise à jour partielle d'un compte : seuls les champs fournis changent."""

    username: Optional[constr(min_length=3, max_length=50)] = None
    email: Optional[EmailStr] = None
    role: Optional[constr(min_length=1, max_length=20)] = None
    is_active: Optional[bool] = None
    manager_id: Optional[str] = None

    @validator('username')
    def validate_username(cls, v):
        if v is not None and not re.match(r'^[a-zA-Z0-9_\-\.]+$', v):
            raise ValueError('Username invalide')
        return v

    @validator('role')
    def validate_role(cls, v):
        if v is None:
            return v
        valid_roles = [r.value for r in UserRole]
        if v.lower() not in valid_roles:
            raise ValueError(f'Rôle invalide. Rôles valides: {", ".join(valid_roles)}')
        return v.lower()


class SetPasswordRequest(BaseModel):
    password: constr(min_length=8, max_length=128)


class ChangeOwnPasswordRequest(BaseModel):
    """Changement de mot de passe par le titulaire du compte.

    Distinct de `SetPasswordRequest`, qui sert la reinitialisation
    administrateur : ici le mot de passe courant est exige, car le titulaire
    n'a pas la permission USER_MANAGE et l'ancien secret doit etre prouve.
    """

    current_password: constr(min_length=1, max_length=128)
    new_password: constr(min_length=8, max_length=128)


class LdapProbeRequest(BaseModel):
    username: constr(min_length=1, max_length=128)


class LdapRoleMappingRequest(BaseModel):
    """Attribution d'un rôle Sentinel à une identité d'annuaire."""

    kind: constr(min_length=1, max_length=16)  # group | user
    value: constr(min_length=1, max_length=512)  # DN de groupe ou sAMAccountName
    role: constr(min_length=1, max_length=20)
    # Valeur la plus basse prioritaire, pour départager une double appartenance.
    priority: Optional[int] = 100
    description: Optional[constr(max_length=255)] = None
    enabled: Optional[bool] = True


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


class MaintenanceWindowRequest(BaseModel):
    agent_id: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    reason: str


class MailTemplatePreviewRequest(BaseModel):
    """Rendu d'un gabarit sur un jeu de valeurs, sans envoi."""

    subject: constr(min_length=1, max_length=300)
    body_html: constr(min_length=1, max_length=100000)
    context: Optional[Dict[str, Any]] = None


class WebhookTestRequest(BaseModel):
    """Essai du webhook signé — le canal par lequel n8n est déclenché."""

    event_key: Optional[constr(max_length=80)] = None


class InventoryRequest(BaseModel):
    """Inventaire logiciel remonté par l'agent.

    Les listes sont libres de forme : elles décrivent ce que l'hôte offre, et
    figer un schéma strict ferait rejeter l'inventaire entier d'un système
    dont un champ manque — pour une donnée d'appoint, le refus coûterait plus
    que l'imprécision.
    """

    services: Optional[List[Dict[str, Any]]] = None
    applications: Optional[List[Dict[str, Any]]] = None
    drivers: Optional[List[Dict[str, Any]]] = None
    truncated: Optional[List[str]] = None
    unavailable: Optional[List[str]] = None


class ConfigAckRequest(BaseModel):
    version: int


class MachineGroupCreateRequest(BaseModel):
    name: constr(min_length=1, max_length=128)
    description: Optional[str] = None


class MachineGroupAssignRequest(BaseModel):
    agent_id: str
    group_id: Optional[str] = None


class ConfigPublishRequest(BaseModel):
    payload: Dict[str, Any]
    note: Optional[str] = None


class ConfigRollbackRequest(BaseModel):
    to_version: int


class CoverageOverlapRequest(BaseModel):
    agent_id: str
    check_id: constr(min_length=1, max_length=64)
    plugin: constr(min_length=1, max_length=128)
    notes: Optional[str] = None


class DiskMountRule(BaseModel):
    mount: str
    warning: float = 85
    critical: float = 95

    @validator("mount")
    def validate_mount(cls, v):
        m = (v or "").strip()
        if not m:
            raise ValueError("Le point de montage est requis")
        return m

    @validator("warning", "critical")
    def validate_pct(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Le seuil doit être entre 0 et 100")
        return v


class UpdateAgentThresholdsRequest(BaseModel):
    cpu_warning_threshold: Optional[float] = None
    cpu_critical_threshold: Optional[float] = None
    ram_warning_threshold: Optional[float] = None
    ram_critical_threshold: Optional[float] = None
    disk_warning_threshold: Optional[float] = None
    disk_critical_threshold: Optional[float] = None
    disk_mount_rules: Optional[List[DiskMountRule]] = None

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
    duration_seconds: Optional[int] = 300
    escalate_after_minutes: Optional[int] = 15
    disk_mount_rules: Optional[List[DiskMountRule]] = None

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
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_enabled: bool = False


class MailTemplateUpdateRequest(BaseModel):
    kind: str
    event_key: str
    subject: str
    body_html: str
    agent_id: Optional[str] = ""
    description: Optional[str] = None


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


# Jeton d'amorçage optionnel, réservé aux laboratoires (BOOTSTRAP_ENROLLMENT_TOKEN).
# Non défini en production : les jetons y sont émis en base par un administrateur.
# Ce cache mémoire ne porte que le jeton d'amorçage ; les jetons émis vivent en
# base (table enrollment_tokens) et survivent donc à un redémarrage.
enrollment_tokens: Dict[str, Dict[str, Any]] = {}
if settings.bootstrap_enrollment_token:
    enrollment_tokens[settings.bootstrap_enrollment_token] = {
        "used": False,
        "expires_at": None,
        "reusable": bool(settings.bootstrap_token_reusable),
    }
    logger.warning(
        "Jeton d'enrôlement d'amorçage actif (réutilisable=%s) — laboratoire uniquement",
        settings.bootstrap_token_reusable,
    )


def _resolve_enrollment_token(db: Session, token: str):
    """Valide un jeton d'enrôlement sans le consommer.

    Deux sources : la table `enrollment_tokens` (jetons émis par un
    administrateur, à usage unique et datés) et un éventuel jeton d'amorçage
    de laboratoire déclaré en configuration.

    Retourne un descripteur opaque à passer à `_consume_enrollment_token`,
    ou lève une HTTPException si le jeton est inconnu, expiré ou déjà utilisé.
    """
    now = datetime.utcnow()

    row = db.query(EnrollmentToken).filter(EnrollmentToken.token == token).first()
    if row is not None:
        if row.status == "consumed":
            raise HTTPException(status_code=400, detail="Token déjà utilisé")
        if row.status != "active":
            raise HTTPException(status_code=401, detail="Token d'enrôlement invalide")
        if row.expires_at and row.expires_at < now:
            row.status = "expired"
            db.commit()
            raise HTTPException(status_code=401, detail="Token d'enrôlement expiré")
        return ("db", row)

    info = enrollment_tokens.get(token)
    if info is not None:
        if info.get("used") and not info.get("reusable"):
            raise HTTPException(status_code=400, detail="Token déjà utilisé")
        expires_at = info.get("expires_at")
        if expires_at and expires_at < now:
            raise HTTPException(status_code=401, detail="Token d'enrôlement expiré")
        return ("memory", info)

    raise HTTPException(status_code=401, detail="Token d'enrôlement invalide")


def _consume_enrollment_token(db: Session, handle) -> None:
    """Marque le jeton comme consommé après un enrôlement réussi.

    Les jetons sont à usage unique (AGT-004), y compris lorsqu'un hôte déjà
    connu se ré-enrôle : le jeton a bien servi. Seul un jeton d'amorçage
    explicitement déclaré réutilisable échappe à la consommation.
    """
    kind, obj = handle
    if kind == "db":
        obj.status = "consumed"
        db.commit()
    elif not obj.get("reusable"):
        obj["used"] = True


#: En-tête indiquant à l'agent que son identité n'existe plus côté plateforme
#: et qu'il doit se ré-enrôler au lieu de rejouer indéfiniment une clé morte.
REENROLL_HEADER = {"X-CBC-Reenroll": "1"}


def _agent_unknown(request: Optional[Request] = None) -> HTTPException:
    """401 explicite : la clé ne correspond à aucun agent, il faut ré-enrôler.

    Le refus est aussi compté et journalisé. Un agent vivant dont l'identité a
    disparu émettait auparavant dans le vide : la plateforme répondait 401 des
    heures durant sans qu'aucun écran ni aucune métrique ne le signale.
    """
    agent_auth_rejected_total.inc()
    source = "unknown"
    path = "-"
    if request is not None:
        source = request.client.host if request.client else "unknown"
        path = request.url.path
    agent_rejection_ledger.record(source, path=path)
    logger.warning(
        "Agent inconnu refusé sur %s depuis %s — ré-enrôlement demandé",
        path,
        source,
    )
    return HTTPException(
        status_code=401,
        detail={
            "detail": "Authentification invalide",
            "code": "agent_unknown",
            "action": "re_enroll",
        },
        headers=REENROLL_HEADER,
    )


def verify_agent(
    request: Request,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    """Vérifie l'authentification de l'agent."""
    agent = db.query(Agent).filter(Agent.auth_key == authorization).first()
    if not agent:
        raise _agent_unknown(request)
    return agent.id


#: Champs du bloc `runtime` remontés en colonnes indexées, pour pouvoir
#: filtrer un parc (« quels hôtes tournent encore en console ? ») sans
#: désérialiser le JSON de chaque ligne.
_RUNTIME_INDEXED = (("run_mode", "run_mode"), ("run_as_user", "run_as_user"))


def apply_reported_facts(agent: Agent, payload) -> None:
    """Recopie sur l'agent ce que la machine déclare d'elle-même.

    Ces champs sont *constatés*, pas *attribués* : ils appartiennent à l'hôte
    et l'interface n'a pas le droit de les écrire (voir
    `AGENT_IMMUTABLE_FIELDS`). Les rafraîchir à chaque battement est la seule
    façon d'avoir un inventaire qui décrit les machines telles qu'elles sont
    et non telles qu'elles étaient le jour de leur installation.

    Chaque champ n'est écrit que s'il est réellement fourni : un agent d'une
    version antérieure, qui n'envoie pas encore ces clés, ne doit pas effacer
    ce que la plateforme sait déjà.
    """
    for field in ("hostname", "os", "os_version", "agent_version", "ip_address", "vlan_observed"):
        value = getattr(payload, field, None)
        if value:
            setattr(agent, field, value)

    for field in ("cpu_cores", "ram_total_gb", "disk_total_gb"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(agent, field, value)

    runtime = getattr(payload, "runtime", None)
    if isinstance(runtime, dict) and runtime:
        agent.runtime_json = json.dumps(runtime, default=str)
        for column, key in _RUNTIME_INDEXED:
            extracted = runtime.get(key)
            if extracted:
                setattr(agent, column, str(extracted)[:120])


def _admit_agent(db: Session, agent_id: str) -> Agent:
    """Charge l'agent d'un tick de présence et le réintègre s'il avait été retiré.

    Un agent « retired » qui émet à nouveau est, par définition, toujours
    installé : la purge s'était trompée (ou la plateforme était restée
    indisponible). On le remet en service sans exiger un nouveau jeton
    d'enrôlement — sa clé d'auth n'a jamais été détruite.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise _agent_unknown()
    if agent.status == RETIRED:
        # Seul « retired » se soigne tout seul : « revoked » et « deleted » sont
        # des décisions d'administrateur, un heartbeat ne doit pas les annuler.
        agent.status = "active"
        logger.info(
            "Agent %s (%s) réintégré à l'inventaire : retired -> active",
            agent.id,
            agent.hostname,
        )
    elif agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent n'est pas actif")
    return agent


def _commit_agent_touch(db: Session, request: Optional[Request] = None) -> None:
    """Commit d'un tick de présence, en traduisant la disparition de la ligne.

    Si l'agent a été supprimé entre la lecture et l'écriture, SQLAlchemy lève
    StaleDataError et l'API répondait 500 — l'agent réessayait alors la même
    clé morte indéfiniment. On renvoie l'ordre de ré-enrôlement.
    """
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise _agent_unknown(request)


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
        "version": settings.app_version,
        # Horodatage attendu par les sondes pour distinguer une réponse fraîche
        # d'une réponse servie par un cache intermédiaire.
        "timestamp": datetime.utcnow().isoformat(),
        # L'ordonnanceur porte la détection hors ligne : s'il est arrêté, la
        # plateforme est aveugle même si l'API répond.
        "scheduler_running": scheduler.running,
    }


@app.get("/health/tsdb")
def health_check_tsdb():
    """Health of the self-hosted VictoriaMetrics TSDB (no cloud account)."""
    from src.tsdb_service import tsdb

    return tsdb.health()


@app.get("/health/logs")
def health_check_logs():
    """Health of self-hosted Loki (no cloud account)."""
    from src.log_store import log_store

    return log_store.health()


@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    """Endpoint de health check pour la base de données."""
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
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


@app.get("/health/platform")
def health_check_platform(db: Session = Depends(get_db)):
    """FS7-06 — Aggregate platform self-monitoring (NFR-010)."""
    from src.platform_health import aggregate_platform_health

    health = aggregate_platform_health(db)
    # Des agents refusés = des hôtes vivants absents du parc. C'est un défaut
    # de la plateforme, pas des postes : il a sa place dans sa santé.
    health["agent_auth_rejections"] = agent_rejection_ledger.summary()
    return health


@app.get("/api/agents/rejected")
@limiter.limit("60/minute")
def list_rejected_agents(
    request: Request,
    current_user: User = Depends(require_auth()),
):
    """Machines qui émettent avec une identité que la plateforme ne connaît plus.

    Sans cet écran, un agent bien vivant purgé de l'inventaire frappait à la
    porte en boucle sans laisser de trace visible : il fallait lire les
    journaux du conteneur pour comprendre qu'un hôte était perdu. Chaque
    entrée appelle un ré-enrôlement de l'agent concerné.
    """
    rows = agent_rejection_ledger.snapshot()
    return {
        "data": rows,
        "items": rows,
        "total": len(rows),
        "hint": (
            "Ces hôtes émettent avec une clé inconnue. Ré-enrôler l'agent "
            "(jeton depuis Paramètres → Agents) pour les réintégrer."
        ),
    }


@app.get("/api/platform/status")
@limiter.limit("60/minute")
def platform_status(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    """Authenticated platform health + latency SLO snapshot."""
    from src.platform_health import aggregate_platform_health
    from src.latency_slo import latency_slo

    health = aggregate_platform_health(db)
    return {**health, "latency": latency_slo.snapshot()}


@app.post("/api/platform/latency/page")
@limiter.limit("30/minute")
def record_page_latency(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(require_auth()),
):
    """Client reports dashboard page-load seconds (NFR-005)."""
    from src.latency_slo import latency_slo

    seconds = float(body.get("seconds", -1))
    latency_slo.record_page_load(seconds)
    return {"status": "recorded", "seconds": seconds}


class SimAgentsRequest(BaseModel):
    count: int = 10
    prefix: str = "load-sim"


@app.post("/api/platform/sim-agents")
@limiter.limit("5/minute")
def create_sim_agents(
    request: Request,
    body: SimAgentsRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """
    FS7-01 — Bulk-create synthetic agents for load drills.
    Requires ALLOW_LOAD_SIM=true. Max 500 per call.
    """
    if not settings.allow_load_sim:
        raise HTTPException(status_code=403, detail="ALLOW_LOAD_SIM is disabled")
    count = max(1, min(int(body.count), 500))
    created = []
    for i in range(1, count + 1):
        machine_id = f"{body.prefix}-{uuid.uuid4()}"
        auth_key = str(uuid.uuid4())
        agent = Agent(
            id=str(uuid.uuid4()),
            machine_id=machine_id,
            hostname=f"{body.prefix}-{i:04d}",
            ip_address="127.0.0.1",
            os="linux",
            os_version="sim",
            agent_version="load-1.0",
            machine_type=MachineType.SERVER,
            auth_key=auth_key,
            status="active",
            enrolled_at=datetime.utcnow(),
            last_communication=datetime.utcnow(),
            location="load-lab",
        )
        db.add(agent)
        created.append({"id": agent.id, "hostname": agent.hostname, "auth_key": auth_key})
    db.commit()
    cache_service.delete_pattern("agents:*")
    return {"created": len(created), "agents": created}


class PurgeLabAgentsRequest(BaseModel):
    dry_run: bool = True
    delete_all: bool = False
    keep_hostnames: List[str] = []


@app.post("/api/platform/purge-lab-agents")
@limiter.limit("5/minute")
def purge_lab_agents(
    request: Request,
    body: PurgeLabAgentsRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """
    Remove simulator / load-test agents so the fleet shows only real enrolled hosts.

    - Default: dry_run=true (lists candidates, deletes nothing).
    - Lab/sim match: hostname/machine_id prefixes sim-/load-, location load-lab, os_version sim.
    - delete_all=true: remove every agent except keep_hostnames (use with care).
    """
    keep = {h.lower() for h in (body.keep_hostnames or [])}
    agents = db.query(Agent).all()
    victims = []
    for agent in agents:
        hostname = (agent.hostname or "").lower()
        if hostname in keep:
            continue
        if body.delete_all or is_lab_or_sim_agent(agent):
            victims.append(agent)

    preview = [
        {
            "id": a.id,
            "hostname": a.hostname,
            "name": a.name,
            "location": a.location,
            "os_version": a.os_version,
        }
        for a in victims
    ]

    if body.dry_run:
        return {"dry_run": True, "would_delete": len(preview), "agents": preview}

    deleted = []
    for agent in victims:
        deleted.append({"id": agent.id, "hostname": agent.hostname})
        delete_agent_with_deps(db, agent)
    db.commit()
    cache_service.delete_pattern("agents:*")
    audit_logger.log_action(
        user_id=current_user.id,
        action="PURGE_LAB_AGENTS",
        details=f"Deleted {len(deleted)} lab/sim agents",
    )
    return {"dry_run": False, "deleted": len(deleted), "agents": deleted}


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
    
    # Valider le jeton (base ou amorçage laboratoire) sans le consommer :
    # la consommation n'a lieu qu'après un enrôlement réussi.
    try:
        token_handle = _resolve_enrollment_token(db, enroll_request.token)
    except HTTPException:
        audit_logger.log_agent_enrollment("unknown", enroll_request.hostname, client_ip, success=False)
        raise

    # Vérifier si l'agent existe déjà
    existing_agent = db.query(Agent).filter(Agent.machine_id == enroll_request.machine_id).first()
    if existing_agent:
        # Mettre à jour l'agent existant
        apply_reported_facts(existing_agent, enroll_request)
        existing_agent.machine_type = MachineType(enroll_request.machine_type)
        existing_agent.status = "active"
        existing_agent.last_communication = datetime.utcnow()
        # Une réinstallation efface la marque de désinstallation : l'hôte
        # est de nouveau supervisé, la trace reste dans l'audit.
        existing_agent.uninstalled_at = None
        existing_agent.uninstalled_by = None
        if not enroll_request.ip_address and client_ip and client_ip != "unknown":
            existing_agent.ip_address = client_ip
        db.commit()

        cache_service.delete_pattern("agents:*")
        publish_agent_presence(existing_agent, online=True)

        # Le jeton a servi, même pour un hôte déjà connu : sans cela tout
        # jeton restait indéfiniment réutilisable via un machine_id existant.
        _consume_enrollment_token(db, token_handle)

        audit_logger.log_agent_enrollment(existing_agent.id, enroll_request.hostname, client_ip, success=True)
        return EnrollResponse(
            agent_id=existing_agent.id,
            auth_key=existing_agent.auth_key,
            message="Agent mis à jour avec succès"
        )
    
    # Créer un nouvel agent. L'identifiant est un code hexadécimal court
    # attribué par la plateforme (voir src.agent_identity) : il doit pouvoir
    # être lu, retenu et dicté par un exploitant, ce qu'un UUID interdisait.
    auth_key = str(uuid.uuid4())
    try:
        agent_id = generate_agent_id(db)
    except AgentIdExhaustedError as exc:
        logger.error("Attribution d'identifiant impossible : %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Espace d'identifiants saturé — contactez l'administrateur de la plateforme.",
        )

    agent = Agent(
        id=agent_id,
        machine_id=enroll_request.machine_id,
        hostname=enroll_request.hostname,
        ip_address=enroll_request.ip_address or (client_ip if client_ip != "unknown" else ""),
        os=enroll_request.os,
        os_version=enroll_request.os_version,
        agent_version=enroll_request.agent_version,
        machine_type=MachineType(enroll_request.machine_type),
        auth_key=auth_key,
        status="active",
        enrolled_at=datetime.utcnow(),
        last_communication=datetime.utcnow()
    )
    apply_reported_facts(agent, enroll_request)

    db.add(agent)
    db.commit()

    _consume_enrollment_token(db, token_handle)

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
    publish_agent_presence(agent, online=True)

    audit_logger.log_agent_enrollment(agent.id, enroll_request.hostname, client_ip, success=True)
    return EnrollResponse(
        agent_id=agent.id,
        auth_key=auth_key,
        message="Agent enregistré avec succès"
    )


@app.post("/api/agents/ping")
@limiter.limit("180/minute")
def agent_ping(
    request: Request,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Cheap liveness tick — updates last_communication without collecting metrics."""
    agent = _admit_agent(db, agent_id)

    now = datetime.utcnow()
    agent.last_communication = now
    agent.updated_at = now
    _commit_agent_touch(db, request)

    AlertService.check_back_online(db, agent_id)
    publish_agent_presence(agent, online=True)

    return {
        "status": "ok",
        "agent_id": agent.id,
        "server_time": now.isoformat(),
        "last_seen_age_seconds": 0,
    }


@app.post("/api/agents/heartbeat")
def receive_heartbeat(
    request: Request,
    heartbeat: HeartbeatRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """
    Reçoit un heartbeat d'un agent.
    
    L'agent envoie ses métriques système. Le serveur les stocke et met à jour
    la dernière communication de l'agent, puis vérifie les alertes.
    """
    # Récupérer l'agent (et le réintégrer s'il avait été retiré par la purge)
    agent = _admit_agent(db, agent_id)

    # Créer le heartbeat
    disks_payload = heartbeat.disks or []
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
        disk_mount=heartbeat.disk_mount,
        disks_json=json.dumps(disks_payload) if disks_payload else None,
        uptime_seconds=heartbeat.uptime_seconds
    )
    
    db.add(heartbeat_record)
    
    # Mettre à jour la dernière communication de l'agent
    # Écart depuis le dernier contact, mesuré AVANT d'écraser la date : c'est
    # ce qui permet de reconnaître une reprise après indisponibilité (point 5).
    previous_contact = agent.last_communication
    agent.last_communication = datetime.utcnow()
    agent.updated_at = datetime.utcnow()
    # Facteurs système et bloc d'exécution, rafraîchis à chaque battement.
    apply_reported_facts(agent, heartbeat)
    if heartbeat.config_version is not None:
        # Soft sync: if agent already applied a version but ack was lost, trust heartbeat
        try:
            reported = int(heartbeat.config_version)
            if reported > int(agent.config_version_acked or 0):
                agent.config_version_acked = reported
            # Même repli pour le plan de supervision : si l'accusé explicite
            # s'est perdu, la version annoncée dans le battement fait foi.
            if reported > int(agent.monitoring_version_acked or 0):
                agent.monitoring_version_acked = reported
        except (TypeError, ValueError):
            pass
    if heartbeat.agent_cpu_percent is not None:
        agent.agent_cpu_percent = heartbeat.agent_cpu_percent
    if heartbeat.agent_ram_mb is not None:
        agent.agent_ram_mb = heartbeat.agent_ram_mb
    _commit_agent_touch(db, request)

    gap_seconds = (
        max(0, int((agent.last_communication - previous_contact).total_seconds()))
        if previous_contact
        else None
    )

    try:
        from src.tsdb_service import tsdb

        ts = heartbeat.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        tsdb.write_heartbeat_samples(
            agent_id=agent_id,
            host=agent.hostname or "unknown",
            ts=ts,
            cpu_percent=heartbeat.cpu_percent,
            ram_percent=heartbeat.ram_percent,
            disk_percent=heartbeat.disk_percent,
        )
    except Exception:
        logger.exception("TSDB heartbeat write skipped")
    
    # Vérifier les alertes de services et fichiers si des données sont fournies
    if heartbeat.services:
        AlertService.check_service_alerts(db, agent_id, heartbeat.services)
    
    if heartbeat.files:
        AlertService.check_file_alerts(db, agent_id, heartbeat.files)
    
    # Invalider le cache et pousser la présence (ping/heartbeat = session live)
    publish_agent_presence(agent, online=True)
    
    # Vérifier si l'agent est revenu en ligne
    AlertService.check_back_online(db, agent_id)
    
    # Vérifier les alertes CPU
    AlertService.check_cpu_alert(db, agent_id, heartbeat.cpu_percent)
    
    # Vérifier les alertes RAM
    AlertService.check_ram_alert(db, agent_id, heartbeat.ram_percent)
    
    # Vérifier les alertes Disque (per-mount when disks[] provided)
    AlertService.check_disk_alerts(
        db,
        agent_id,
        disks_payload,
        heartbeat.disk_percent,
        heartbeat.disk_mount,
    )

    if heartbeat.agent_cpu_percent is not None or heartbeat.agent_ram_mb is not None:
        AlertService.check_footprint_alert(
            db,
            agent_id,
            heartbeat.agent_cpu_percent,
            heartbeat.agent_ram_mb,
        )
    
    # Résoudre les alertes si les valeurs sont revenues sous le seuil
    AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.CPU_HIGH, heartbeat.cpu_percent)
    AlertService.resolve_alerts_below_threshold(db, agent_id, AlertType.RAM_HIGH, heartbeat.ram_percent)
    AlertService.resolve_disk_alerts(db, agent_id, disks_payload, heartbeat.disk_percent, heartbeat.disk_mount)
    # Détection hors ligne, escalade et purge d'inventaire sont portées par
    # l'ordonnanceur (src/scheduler.py) : les exécuter ici les rendait muettes
    # pendant une panne de parc, et imposait un balayage complet du parc à
    # chaque heartbeat reçu.

    # Configuration à pousser : le plan de supervision propre à l'hôte prime
    # sur la configuration de groupe. L'ordre compte — un réglage posé sur une
    # machine précise doit survivre à une publication de groupe, sinon
    # l'exploitant verrait son paramétrage individuel écrasé sans le savoir.
    config_push = None
    pending_group = ConfigService.pending_for_agent(db, agent)
    pending_plan = monitoring_plan.pending_for_agent(db, agent)

    if pending_group or pending_plan:
        merged: Dict[str, Any] = {}
        version = 0
        if pending_group:
            group_version, group_payload = pending_group
            merged = dict(group_payload or {})
            version = max(version, group_version)
        if pending_plan:
            merged = config_deep_merge(merged, pending_plan["payload"])
            version = max(version, pending_plan["version"])
        config_push = {"version": version, "payload": merged}

    from src.task_service import pending_tasks_for_agent

    tasks = pending_tasks_for_agent(db, agent_id)

    # Écho de présence (point 5). La plateforme ne peut pas ouvrir une
    # connexion vers un hôte derrière NAT : la réponse au battement est donc
    # le seul canal descendant réel. L'agent y trouve de quoi vérifier trois
    # choses qu'il ne peut pas déduire seul — que le serveur l'a bien
    # enregistré sous cette identité, si son horloge dérive, et si sa
    # configuration est en retard.
    server_now = datetime.utcnow()
    agent_clock = heartbeat.timestamp
    if agent_clock is not None and agent_clock.tzinfo is not None:
        agent_clock = agent_clock.astimezone(timezone.utc).replace(tzinfo=None)
    echo = {
        "agent_id": agent_id,
        "server_time": server_now.isoformat() + "Z",
        "received_at": agent.last_communication.isoformat() + "Z",
        "config_version": int(agent.config_version_acked or 0),
        "clock_skew_seconds": (
            int((server_now - agent_clock).total_seconds()) if agent_clock else None
        ),
        # Durée réelle du silence précédent : l'agent sait ainsi qu'il sort
        # d'une coupure et peut journaliser un rattrapage explicite plutôt
        # que de rejouer son tampon en silence.
        "previous_gap_seconds": gap_seconds,
        "resumed_after_outage": bool(
            gap_seconds is not None and gap_seconds > settings.heartbeat_timeout_seconds
        ),
    }

    if echo["resumed_after_outage"]:
        logger.info(
            "Reprise de contact agent %s (%s) après %ss de silence",
            agent.id,
            agent.hostname,
            gap_seconds,
        )
        audit_logger.log_event(
            event_type="agent_resync",
            details={
                "agent_id": agent.id,
                "hostname": agent.hostname,
                "silent_for_seconds": gap_seconds,
            },
        )

    return {
        "status": "success",
        "message": "Heartbeat reçu",
        "tasks": tasks,
        "config": config_push,
        "echo": echo,
    }


class MetricsIngestRequest(BaseModel):
    metrics: List[Dict[str, Any]]


@app.post("/api/ingest/metrics")
@limiter.limit("120/minute")
def ingest_metrics(
    request: Request,
    body: MetricsIngestRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """
    Canonical metric.v1 ingest (FS1 / PLT-001/002).
    Valid points are stored in self-hosted VictoriaMetrics; invalid payloads go to the DLQ.
    """
    from src.protocol_ingest import DeadLetterQueue, validate_metrics_batch
    from src.tsdb_service import tsdb

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent or agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent non autorisé")

    valid, rejected = validate_metrics_batch(body.metrics, DeadLetterQueue())
    written = tsdb.write_metric_v1(valid) if valid else 0
    agent.last_communication = datetime.utcnow()
    db.commit()
    publish_agent_presence(agent, online=True)

    # FS7-02 — collect → ingest lag vs metric timestamps
    try:
        from src.latency_slo import latency_slo

        now = datetime.now(timezone.utc)
        for m in valid[:50]:
            ts = getattr(m, "ts", None)
            if ts is None:
                continue
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.replace(tzinfo=timezone.utc)
            latency_slo.record_collect_to_ingest((now - ts).total_seconds())
    except Exception:
        pass

    logger.info(
        "metric.v1 ingest agent=%s accepted=%s rejected=%s written=%s",
        agent_id,
        len(valid),
        rejected,
        written,
    )
    return {
        "status": "success",
        "accepted": len(valid),
        "rejected": rejected,
        "written": written,
        "families": sorted({m.family for m in valid}),
        "dlq": rejected > 0,
    }


@app.get("/api/ingest/dlq")
def list_metrics_dlq(
    request: Request,
    limit: int = 50,
    current_user: User = Depends(require_admin()),
):
    """PLT-002 — inspect invalid metric.v1 payloads (Lot 1 DLQ)."""
    from src.protocol_ingest import DeadLetterQueue

    queue = DeadLetterQueue()
    return {
        "path": str(queue.path),
        "count": queue.size(),
        "items": queue.tail(min(max(limit, 1), 200)),
    }


class TaskResultsRequest(BaseModel):
    results: List[Dict[str, Any]]


@app.post("/api/agents/tasks/results")
@limiter.limit("60/minute")
def receive_task_results(
    request: Request,
    body: TaskResultsRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Accept L0 rejection / L1 execution results for task.v1 (AGT-010 / FS9)."""
    from src.task_service import apply_task_results

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent or agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent non autorisé")
    accepted = apply_task_results(db, agent_id, body.results)
    logger.info("task results agent=%s count=%s accepted=%s", agent_id, len(body.results), accepted)
    return {"status": "success", "accepted": accepted}


# ==================== FS9: actions + approvals ====================

class CreateActionRequest(BaseModel):
    agent_id: constr(min_length=1, max_length=64)
    plugin: constr(min_length=1, max_length=128)
    input: Dict[str, Any] = {}
    dry_run: bool = True
    force_approval: bool = False


class ApprovalDecisionRequest(BaseModel):
    decision: str
    comment: Optional[str] = None


@app.get("/api/actions/plugins")
@limiter.limit("60/minute")
def list_action_plugins(request: Request, current_user: User = Depends(require_auth())):
    from src.task_service import ALLOWLIST_PLUGINS, APPROVAL_REQUIRED_PLUGINS

    return {
        "data": [
            {
                "plugin": p,
                "requires_approval_when_live": p in APPROVAL_REQUIRED_PLUGINS,
                "capability": "L1",
            }
            for p in sorted(ALLOWLIST_PLUGINS)
        ]
    }


@app.get("/api/actions/tasks")
@limiter.limit("60/minute")
def list_action_tasks(
    request: Request,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.task_service import serialize_task

    q = db.query(RemoteTask).order_by(RemoteTask.created_at.desc())
    if status:
        q = q.filter(RemoteTask.status == status)
    if agent_id:
        q = q.filter(RemoteTask.agent_id == agent_id)
    rows = q.limit(200).all()
    return {"data": [serialize_task(t) for t in rows]}


@app.post("/api/actions/tasks")
@limiter.limit("30/minute")
def create_action_task(
    request: Request,
    body: CreateActionRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    from src.task_service import create_task, serialize_task

    try:
        task, approval = create_task(
            db,
            agent_id=body.agent_id,
            plugin=body.plugin,
            input_data=body.input or {},
            dry_run=body.dry_run,
            requested_by=current_user.username,
            force_approval=body.force_approval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "task": serialize_task(task),
        "approval_id": approval.id if approval else None,
    }


@app.get("/api/actions/tasks/{task_id}")
@limiter.limit("60/minute")
def get_action_task(
    request: Request,
    task_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.task_service import serialize_task

    task = db.query(RemoteTask).filter(RemoteTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    return serialize_task(task)


@app.get("/api/approvals")
@limiter.limit("60/minute")
def list_approvals(
    request: Request,
    status: str = "pending",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.task_service import serialize_task

    q = db.query(ActionApproval).order_by(ActionApproval.created_at.desc())
    if status and status != "all":
        q = q.filter(ActionApproval.status == status)
    rows = q.limit(100).all()
    data = []
    for a in rows:
        task = db.query(RemoteTask).filter(RemoteTask.id == a.task_id).first()
        data.append(
            {
                "id": a.id,
                "task_id": a.task_id,
                "status": a.status,
                "requested_by": a.requested_by,
                "decided_by": a.decided_by,
                "comment": a.comment,
                "created_at": a.created_at,
                "decided_at": a.decided_at,
                "task": serialize_task(task) if task else None,
            }
        )
    return {"data": data}


@app.post("/api/approvals/{approval_id}/decide")
@limiter.limit("30/minute")
def decide_approval_endpoint(
    request: Request,
    approval_id: str,
    body: ApprovalDecisionRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    from src.task_service import decide_approval

    try:
        row = decide_approval(
            db,
            approval_id,
            decide=body.decision,
            decided_by=current_user.username,
            comment=body.comment or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": row.id, "status": row.status}


@app.put("/api/agents/{agent_id}/capability")
@limiter.limit("20/minute")
def set_agent_capability(
    request: Request,
    agent_id: str,
    body: Dict[str, Any],
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Set agent capability_level L0|L1 (Lot 2). Also push via group config preferred."""
    level = str(body.get("capability_level") or "L0").upper()
    if level not in ("L0", "L1"):
        raise HTTPException(status_code=400, detail="capability_level must be L0 or L1")
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable")
    agent.capability_level = level
    db.commit()
    return {"id": agent.id, "capability_level": level}


class LogsIngestRequest(BaseModel):
    host: Optional[str] = None
    events: List[Dict[str, Any]]
    dropped: int = 0
    rate_limited: bool = False
    pattern_alerts: Optional[List[Dict[str, Any]]] = None


@app.post("/api/ingest/logs")
@limiter.limit("120/minute")
def ingest_logs(
    request: Request,
    body: LogsIngestRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Ship agent logs into Loki (STO-003 / AGT-035)."""
    from src.log_store import log_store

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent or agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent non autorisé")
    host = body.host or agent.hostname or "unknown"
    written = log_store.push(agent_id, host, body.events)
    if body.rate_limited:
        logger.warning("agent %s hit log rate limit dropped=%s", agent_id, body.dropped)
        AlertService.check_rate_limit_alert(db, agent_id, body.dropped)
    if body.pattern_alerts:
        AlertService.check_log_pattern_alerts(db, agent_id, body.pattern_alerts)
    return {"status": "success", "accepted": len(body.events), "written": written, "dropped": body.dropped}


@app.get("/api/logs/search")
@limiter.limit("60/minute")
def search_logs(
    request: Request,
    current_user: User = Depends(require_auth()),
    q: str = "",
    host: str = "",
    severity: str = "",
    source: str = "",
    hours: int = 24,
    limit: int = 200,
):
    """Search logs in Loki (DSH-005)."""
    from src.log_store import log_store

    if hours < 1:
        hours = 1
    if hours > 24 * 30:
        hours = 24 * 30
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    parts = ['{job="cbc-agent"']
    if host:
        parts[0] = parts[0] + f',host="{host}"'
    if severity:
        parts[0] = parts[0] + f',severity="{severity}"'
    if source:
        parts[0] = parts[0] + f',source="{source}"'
    logql = parts[0] + "}"
    if q:
        escaped = q.replace("\\", "\\\\").replace('"', '\\"')
        logql = f'{logql} |= "{escaped}"'
    return log_store.query(logql, start, end, limit=min(limit, 500))


@app.get("/api/agents")
@limiter.limit("100/minute")  # Limite à 100 requêtes par minute
def list_agents(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    include_offline: bool = True,
    include_retired: bool = False,
    include_uninstalled: bool = False,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db)
):
    """Inventaire des agents.

    Par défaut on inclut les hôtes hors ligne : un opérateur doit pouvoir
    ouvrir la fiche et voir le dernier contact. Passer include_offline=false
    pour n'avoir que les sessions live, include_retired=true pour voir aussi
    les hôtes mis de côté par la purge d'inventaire.

    Cette route ne modifie rien : la purge tournait ici « opportunément », si
    bien qu'ouvrir la liste pouvait supprimer des agents (y compris un agent
    en train de se ré-enrôler). Elle est portée par l'ordonnanceur seul.
    """
    if limit > 1000:
        limit = 1000  # Limite maximale pour éviter les requêtes trop lourdes

    # Clé de cache
    cache_key = (
        f"agents:v7:{skip}:{limit}:"
        f"{'all' if include_offline else 'live'}:{'ret' if include_retired else 'noret'}"
        f":{'uni' if include_uninstalled else 'nouni'}"
    )

    # Essayer de récupérer depuis le cache
    cached_data = cache_service.get(cache_key)
    if cached_data:
        return cached_data

    # Sinon, interroger la base de données
    agents = db.query(Agent).order_by(Agent.enrolled_at.desc()).all()

    now = datetime.utcnow()
    # Le plan d'adressage est lu une fois pour tout le parc : le relire par
    # hôte ferait une requête par ligne de la liste.
    vlan_rows = _vlan_rows(db)
    rows = []
    for agent in agents:
        last_hb = (
            db.query(Heartbeat)
            .filter(Heartbeat.agent_id == agent.id)
            .order_by(Heartbeat.timestamp.desc())
            .first()
        )
        live = is_agent_live(agent, now=now, timeout_seconds=settings.heartbeat_timeout_seconds)
        retired = agent.status == RETIRED
        uninstalled = agent.status == UNINSTALLED
        # Un hôte désinstallé n'est plus du parc : il ne réapparaît que si on
        # le demande explicitement (consultation d'historique, audit).
        if uninstalled and not include_uninstalled:
            continue
        if retired and not include_retired and not live:
            continue
        if not include_offline and not live:
            continue
        if last_hb is None and not live and not include_offline:
            continue
        last_seen = agent.last_communication
        derived_status = derived_agent_status(
            agent, now=now, timeout_seconds=settings.heartbeat_timeout_seconds
        )
        machine_type = agent.machine_type.value if getattr(agent.machine_type, "value", None) else str(agent.machine_type or "workstation")
        rows.append({
            "id": agent.id,
            "machine_id": agent.machine_id,
            "hostname": agent.hostname,
            "name": agent.name or agent.hostname,
            "ip_address": agent.ip_address or "",
            "os": agent.os,
            "os_version": agent.os_version,
            "agent_version": agent.agent_version,
            "status": derived_status,
            "retired": retired,
            "uninstalled": uninstalled,
            "uninstalled_at": agent.uninstalled_at,
            "cpu_cores": agent.cpu_cores,
            **resolve_vlan(agent, vlan_rows),
            "owner_user_id": agent.owner_user_id,
            "admin_group_id": agent.admin_group_id,
            "run_mode": agent.run_mode,
            "last_communication": last_seen,
            "last_heartbeat": last_seen,
            "last_seen_age_seconds": last_seen_age_seconds(agent, now=now),
            "enrolled_at": agent.enrolled_at,
            "location": agent.location,
            "machine_type": machine_type,
            "group_id": agent.group_id,
            "config_version_acked": agent.config_version_acked or 0,
            "agent_cpu_percent": agent.agent_cpu_percent,
            "agent_ram_mb": agent.agent_ram_mb,
            "cpu_percent": last_hb.cpu_percent if last_hb else None,
            "ram_percent": last_hb.ram_percent if last_hb else None,
            "ram_used_gb": last_hb.ram_used_gb if last_hb else None,
            # Le battement fait foi, l'inventaire prend le relais tant qu'il
            # n'y en a pas : un hôte fraîchement enrôlé a déclaré son matériel,
            # l'afficher vide jusqu'au premier battement le perdrait.
            "ram_total_gb": last_hb.ram_total_gb if last_hb else agent.ram_total_gb,
            "disk_percent": last_hb.disk_percent if last_hb else None,
            "disk_used_gb": last_hb.disk_used_gb if last_hb else None,
            "disk_total_gb": last_hb.disk_total_gb if last_hb else None,
            "uptime_seconds": last_hb.uptime_seconds if last_hb else None,
        })

    total = len(rows)
    paged = rows[skip:skip + limit]
    result = {
        "data": paged,
        "items": paged,
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


@app.post("/api/agents/deregister")
@limiter.limit("30/minute")
def deregister_agent(
    request: Request,
    deregister_request: Optional[DeregisterRequest] = None,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Désenrôlement signalé par l'agent au moment de sa désinstallation.

    L'hôte est **marqué désinstallé, pas effacé**. Supprimer la ligne
    immédiatement — le comportement précédent — détruisait du même coup
    l'historique de heartbeats, les alertes et la trace d'exploitation de la
    machine, au moment précis où l'on veut pouvoir répondre à « depuis quand
    cet hôte n'est-il plus supervisé, et qui l'a retiré ? ». La suppression
    définitive revient à la purge d'inventaire, à l'échéance de rétention.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    reason = (deregister_request.reason if deregister_request else None) or None

    hostname = agent.hostname
    now = datetime.utcnow()
    agent.status = UNINSTALLED
    agent.uninstalled_at = now
    agent.uninstalled_by = "agent"
    agent.updated_at = now
    db.commit()

    cache_service.delete_pattern("agents:*")
    publish_agent_presence(agent, online=False)

    # Les alertes ouvertes d'un hôte volontairement retiré n'ont plus d'objet :
    # les laisser ouvertes ferait sonner une machine qu'on a nous-mêmes
    # décidé de ne plus superviser.
    AlertService.resolve_open_alerts_for_agent(db, agent_id, reason="agent_uninstalled")

    audit_logger.log_event(
        event_type="agent_deregister",
        details={
            "agent_id": agent_id,
            "hostname": hostname,
            "action": "agent_self_deregister",
            "reason": reason,
        },
    )
    logger.info("Agent %s (%s) désinstallé et retiré de la supervision", agent_id, hostname)
    return {
        "message": "Agent désinstallé",
        "id": agent_id,
        "hostname": hostname,
        "status": UNINSTALLED,
        "uninstalled_at": now.isoformat() + "Z",
    }


# ------------------------------------------------- équipes d'administration


class AdminGroupRequest(BaseModel):
    name: constr(min_length=2, max_length=80)
    description: Optional[constr(max_length=250)] = None


class AdminGroupMembersRequest(BaseModel):
    user_ids: List[constr(max_length=64)]


def _serialize_admin_group(group: AdminGroup, db: Session) -> Dict[str, Any]:
    members = (
        db.query(AdminGroupMember, User)
        .join(User, User.id == AdminGroupMember.user_id)
        .filter(AdminGroupMember.group_id == group.id)
        .all()
    )
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_at": group.created_at,
        "members": [
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "added_at": membership.added_at,
            }
            for membership, user in members
        ],
        "agent_count": db.query(Agent.id).filter(Agent.admin_group_id == group.id).count(),
    }


@app.get("/api/admin-groups")
@limiter.limit("60/minute")
def list_admin_groups(
    request: Request,
    current_user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db),
):
    """Équipes responsables d'hôtes, avec leurs membres."""
    groups = db.query(AdminGroup).order_by(AdminGroup.name).all()
    rows = [_serialize_admin_group(g, db) for g in groups]
    return {"data": rows, "items": rows, "total": len(rows)}


@app.post("/api/admin-groups")
@limiter.limit("20/minute")
def create_admin_group(
    request: Request,
    body: AdminGroupRequest,
    current_user: User = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    if db.query(AdminGroup.id).filter(AdminGroup.name == body.name).first():
        raise HTTPException(status_code=400, detail="Une équipe porte déjà ce nom")

    group = AdminGroup(id=str(uuid.uuid4()), name=body.name, description=body.description)
    db.add(group)
    db.commit()
    audit_logger.log_action(
        user_id=current_user.id,
        action="CREATE_ADMIN_GROUP",
        details=f"Équipe d'administration créée : {body.name}",
    )
    return _serialize_admin_group(group, db)


@app.put("/api/admin-groups/{group_id}/members")
@limiter.limit("30/minute")
def set_admin_group_members(
    request: Request,
    group_id: str,
    body: AdminGroupMembersRequest,
    current_user: User = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    """Remplace la liste des membres.

    Remplacement plutôt qu'ajout/retrait : l'appelant envoie l'état voulu, ce
    qui évite qu'une interface désynchronisée laisse dans l'équipe quelqu'un
    qui n'y est plus — sur un droit d'accès, l'écart se paie.
    """
    group = db.query(AdminGroup).filter(AdminGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Équipe non trouvée")

    wanted = set(body.user_ids)
    known = {u.id for u in db.query(User.id).filter(User.id.in_(wanted)).all()} if wanted else set()
    unknown = sorted(wanted - known)
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "unknown_users", "user_ids": unknown})

    db.query(AdminGroupMember).filter(AdminGroupMember.group_id == group_id).delete(
        synchronize_session=False
    )
    for user_id in sorted(wanted):
        db.add(
            AdminGroupMember(
                id=str(uuid.uuid4()),
                group_id=group_id,
                user_id=user_id,
                added_by=current_user.id,
            )
        )
    db.commit()
    cache_service.delete_pattern("agents:*")
    audit_logger.log_action(
        user_id=current_user.id,
        action="SET_ADMIN_GROUP_MEMBERS",
        details=f"Équipe {group.name} : {len(wanted)} membre(s)",
    )
    return _serialize_admin_group(group, db)


@app.delete("/api/admin-groups/{group_id}")
@limiter.limit("20/minute")
def delete_admin_group(
    request: Request,
    group_id: str,
    current_user: User = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    group = db.query(AdminGroup).filter(AdminGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Équipe non trouvée")

    # Les hôtes rattachés retombent sous la seule responsabilité de
    # l'administrateur global ; ils ne doivent pas devenir orphelins avec un
    # identifiant d'équipe qui ne désigne plus rien.
    detached = db.query(Agent).filter(Agent.admin_group_id == group_id).update(
        {Agent.admin_group_id: None}, synchronize_session=False
    )
    db.query(AdminGroupMember).filter(AdminGroupMember.group_id == group_id).delete(
        synchronize_session=False
    )
    name = group.name
    db.delete(group)
    db.commit()
    cache_service.delete_pattern("agents:*")
    audit_logger.log_action(
        user_id=current_user.id,
        action="DELETE_ADMIN_GROUP",
        details=f"Équipe {name} supprimée ({detached} hôte(s) détaché(s))",
    )
    return {"message": "Équipe supprimée", "detached_agents": detached}


# ------------------------------------------------- plan de supervision (point 6)


class MonitoredServiceIn(BaseModel):
    name: constr(min_length=1, max_length=200)
    expected_state: constr(max_length=20) = "running"
    severity: constr(max_length=20) = "major"
    enabled: bool = True


class MonitoredFileIn(BaseModel):
    path: constr(min_length=1, max_length=500)
    condition: constr(max_length=20) = "must_exist"
    severity: constr(max_length=20) = "major"
    max_size_mb: Optional[int] = None
    enabled: bool = True


class ThresholdPairIn(BaseModel):
    warning: Optional[float] = None
    critical: Optional[float] = None


class PartitionRuleIn(BaseModel):
    mount: constr(min_length=1, max_length=200)
    warning: float = 85.0
    critical: float = 95.0


class DiskPlanIn(ThresholdPairIn):
    partitions: Optional[List[PartitionRuleIn]] = None


class MonitoringPlanIn(BaseModel):
    """Plan de supervision d'un hôte, envoyé en entier.

    Chaque section est facultative : n'envoyer que `services` ne touche pas
    aux seuils. En revanche une section *présente* remplace intégralement son
    contenu — une liste de services vide vide donc la liste, ce qui est le
    comportement attendu quand un exploitant retire le dernier service.
    """

    cpu: Optional[ThresholdPairIn] = None
    ram: Optional[ThresholdPairIn] = None
    disk: Optional[DiskPlanIn] = None
    services: Optional[List[MonitoredServiceIn]] = None
    files: Optional[List[MonitoredFileIn]] = None


@app.get("/api/agents/{agent_id}/monitoring")
@limiter.limit("60/minute")
def get_agent_monitoring(
    request: Request,
    agent_id: str,
    current_user: User = Depends(require_permission(Permission.AGENT_VIEW)),
    db: Session = Depends(get_db),
):
    """Plan de supervision complet d'un hôte : CPU, RAM, partitions, services, fichiers."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    return monitoring_plan.get_plan(db, agent)


@app.put("/api/agents/{agent_id}/monitoring")
@limiter.limit("30/minute")
def put_agent_monitoring(
    request: Request,
    agent_id: str,
    plan: MonitoringPlanIn,
    current_user: User = Depends(require_agent_scope(Permission.AGENT_EDIT)),
    db: Session = Depends(get_db),
):
    """Remplace le plan de supervision d'un hôte et le pousse vers l'agent.

    Remplace les anciens `PUT /api/settings/services-monitoring` et
    `/files-monitoring`, qui ne persistaient rien : ils journalisaient un
    évènement d'audit et renvoyaient la requête en écho, pendant que
    l'interface affichait « mise à jour avec succès ».
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    payload = plan.model_dump(exclude_unset=True)
    for section in ("cpu", "ram", "disk"):
        values = payload.get(section)
        if not values:
            continue
        warning, critical = values.get("warning"), values.get("critical")
        if warning is not None and critical is not None and warning >= critical:
            raise HTTPException(
                status_code=400,
                detail=f"{section} : le seuil d'avertissement doit être inférieur au seuil critique",
            )

    updated = monitoring_plan.replace_plan(db, agent, payload, updated_by=current_user.username)
    cache_service.delete_pattern("agents:*")
    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_MONITORING_PLAN",
        details=(
            f"Agent {agent_id} : plan v{updated['version']} — "
            f"{len(updated['services'])} service(s), {len(updated['files'])} fichier(s), "
            f"{len(updated['disk']['partitions'])} partition(s)"
        ),
    )
    return updated


class PatchAgentRequest(BaseModel):
    """Champs qu'un exploitant peut poser sur un hôte.

    Le modèle ne déclare **que** les champs attribués. Tout le reste (nom
    machine, IP, OS, caractéristiques matérielles) est constaté par l'agent :
    l'accepter ici produirait un inventaire qui contredit la machine réelle,
    et la contradiction ne se verrait qu'au prochain incident.
    """

    model_config = {"extra": "allow"}  # pour pouvoir *nommer* les champs refusés

    name: Optional[constr(max_length=120)] = None
    location: Optional[constr(max_length=120)] = None
    #: VLAN déclaré par l'exploitation — voir models.Agent.vlan.
    vlan: Optional[constr(max_length=64)] = None
    machine_type: Optional[constr(max_length=20)] = None
    owner_user_id: Optional[constr(max_length=64)] = None
    admin_group_id: Optional[constr(max_length=64)] = None
    group_id: Optional[constr(max_length=64)] = None


@app.patch("/api/agents/{agent_id}")
@limiter.limit("30/minute")
def patch_agent(
    request: Request,
    agent_id: str,
    patch: PatchAgentRequest,
    current_user: User = Depends(require_agent_scope(Permission.AGENT_EDIT)),
    db: Session = Depends(get_db),
):
    """Modifie les champs attribués d'un hôte (point 2).

    Remplace les routes mono-champ `PUT .../name` et `PUT .../location`, que
    l'interface n'a d'ailleurs jamais appelées. Une tentative d'écriture sur
    un champ constaté est refusée en nommant le champ, plutôt que d'être
    ignorée en silence — sinon l'utilisateur croit avoir renommé la machine.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    submitted = patch.model_dump(exclude_unset=True)

    refused = sorted(set(submitted) & AGENT_IMMUTABLE_FIELDS)
    if refused:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "immutable_fields",
                "message": (
                    "Ces champs sont constatés par l'agent sur l'hôte et ne "
                    "peuvent pas être modifiés depuis la plateforme."
                ),
                "fields": refused,
            },
        )

    unknown = sorted(set(submitted) - AGENT_EDITABLE_FIELDS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={"code": "unknown_fields", "fields": unknown},
        )

    changes = {}
    for field, value in submitted.items():
        if field == "machine_type":
            try:
                value = MachineType(value)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"machine_type invalide : {value!r} (attendu 'server' ou 'workstation')",
                )
        elif field == "owner_user_id" and value:
            if not db.query(User.id).filter(User.id == value).first():
                raise HTTPException(status_code=400, detail="Responsable inconnu")
        elif field == "admin_group_id" and value:
            if not db.query(AdminGroup.id).filter(AdminGroup.id == value).first():
                raise HTTPException(status_code=400, detail="Équipe d'administration inconnue")

        before = getattr(agent, field, None)
        before_value = before.value if hasattr(before, "value") else before
        after_value = value.value if hasattr(value, "value") else value
        if before_value != after_value:
            changes[field] = {"avant": before_value, "après": after_value}
            setattr(agent, field, value)

    if not changes:
        return {"message": "Aucune modification", "id": agent.id, "changes": {}}

    agent.updated_at = datetime.utcnow()
    db.commit()
    cache_service.delete_pattern("agents:*")

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_AGENT",
        details=f"Agent {agent_id} : " + ", ".join(
            f"{k} {v['avant']!r} -> {v['après']!r}" for k, v in changes.items()
        ),
    )
    return {"message": "Hôte mis à jour", "id": agent.id, "changes": changes}


def _vlan_rows(db: Session):
    """Plan d'adressage importé, sous la forme attendue par `vlan_service`."""
    return [
        vlan_service.SubnetRow(
            cidr=r.cidr, vlan=r.vlan, label=r.label,
            range_start=r.range_start, range_end=r.range_end,
        )
        for r in db.query(VlanSubnet).all()
    ]


def resolve_vlan(agent: Agent, rows) -> Dict[str, Any]:
    """VLAN retenu pour un hôte, et d'où il vient.

    Trois sources, par ordre d'autorité décroissante :

    1. `vlan` — saisi par l'exploitation sur cette fiche. Une saisie explicite
       l'emporte : elle sert justement à traiter l'exception que le plan
       d'adressage ne décrit pas.
    2. le plan d'adressage — déduit de l'adresse IP constatée. Couvre le parc
       entier sans saisie, et suit l'hôte quand il change d'adresse.
    3. `vlan_observed` — ce que l'hôte étiquette lui-même. Rare, mais c'est la
       seule source que la machine connaisse de première main.

    La provenance est rendue avec la valeur : un VLAN déduit et un VLAN saisi
    n'engagent pas la même confiance, et l'exploitant doit pouvoir les
    distinguer.
    """
    match = vlan_service.match_ip(agent.ip_address, rows) if rows else None
    derived = match.vlan if match else None

    if agent.vlan:
        effective, source = agent.vlan, "declared"
    elif derived:
        effective, source = derived, "derived"
    elif agent.vlan_observed:
        effective, source = agent.vlan_observed, "observed"
    else:
        effective, source = None, None

    return {
        "vlan": agent.vlan,
        "vlan_observed": agent.vlan_observed,
        "vlan_derived": derived,
        "vlan_subnet": match.cidr if match else None,
        "vlan_label": match.label if match else None,
        "vlan_effective": effective,
        "vlan_source": source,
    }


def _parse_runtime(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Bloc d'exécution stocké en JSON — illisible ne doit pas casser la fiche."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


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
    now = datetime.utcnow()
    
    return {
        "id": agent.id,
        "machine_id": agent.machine_id,
        "hostname": agent.hostname,
        "name": agent.name or agent.hostname,
        "location": agent.location,
        "ip_address": agent.ip_address,
        "os": agent.os,
        "os_version": agent.os_version,
        "agent_version": agent.agent_version,
        "status": derived_agent_status(agent, now=now),
        "last_communication": agent.last_communication,
        "last_seen_age_seconds": last_seen_age_seconds(agent, now=now),
        "enrolled_at": agent.enrolled_at,
        "machine_type": agent.machine_type.value if hasattr(agent.machine_type, "value") else str(agent.machine_type or ""),
        # Caractéristiques constatées de l'hôte (point 2)
        "cpu_cores": agent.cpu_cores,
        # Segmentation réseau : constaté par l'hôte, déclaré par
        # l'exploitation, déduit du plan d'adressage. Les trois, parce qu'ils
        # peuvent diverger — et cette divergence est justement ce qu'on veut
        # voir.
        **resolve_vlan(agent, _vlan_rows(db)),
        # Responsabilité (point 3)
        "owner_user_id": agent.owner_user_id,
        "owner_username": agent.owner.username if agent.owner else None,
        "admin_group_id": agent.admin_group_id,
        "admin_group_name": agent.admin_group.name if agent.admin_group else None,
        "group_id": agent.group_id,
        # Comment et où l'agent tourne (point 9)
        "runtime": _parse_runtime(agent.runtime_json),
        "run_mode": agent.run_mode,
        "run_as_user": agent.run_as_user,
        # Désinstallation (point 4)
        "uninstalled_at": agent.uninstalled_at,
        "uninstalled_by": agent.uninstalled_by,
        # Séparation imposée par l'API, servie à l'interface pour qu'elle
        # n'ait pas à redéfinir sa propre liste de champs verrouillés.
        "editable_fields": sorted(AGENT_EDITABLE_FIELDS),
        "cpu_warning_threshold": agent.cpu_warning_threshold,
        "cpu_critical_threshold": agent.cpu_critical_threshold,
        "ram_warning_threshold": agent.ram_warning_threshold,
        "ram_critical_threshold": agent.ram_critical_threshold,
        "disk_warning_threshold": agent.disk_warning_threshold,
        "disk_critical_threshold": agent.disk_critical_threshold,
        "disk_mount_rules": AlertService.parse_disk_mount_rules(getattr(agent, "disk_mount_rules", None)),
        "cpu_percent": last_heartbeat.cpu_percent if last_heartbeat else None,
        "ram_percent": last_heartbeat.ram_percent if last_heartbeat else None,
        "ram_used_gb": last_heartbeat.ram_used_gb if last_heartbeat else None,
        "ram_total_gb": last_heartbeat.ram_total_gb if last_heartbeat else agent.ram_total_gb,
        "disk_percent": last_heartbeat.disk_percent if last_heartbeat else None,
        "disk_used_gb": last_heartbeat.disk_used_gb if last_heartbeat else None,
        "disk_total_gb": last_heartbeat.disk_total_gb if last_heartbeat else agent.disk_total_gb,
        "uptime_seconds": last_heartbeat.uptime_seconds if last_heartbeat else None,
        "disks": _partitions_from_heartbeat(last_heartbeat),
        "last_heartbeat": {
            "timestamp": last_heartbeat.timestamp if last_heartbeat else None,
            "cpu_percent": last_heartbeat.cpu_percent if last_heartbeat else None,
            "cpu_cores": last_heartbeat.cpu_cores if last_heartbeat else None,
            "cpu_architecture": getattr(last_heartbeat, "cpu_architecture", None) if last_heartbeat else None,
            "ram_percent": last_heartbeat.ram_percent if last_heartbeat else None,
            "ram_total_gb": last_heartbeat.ram_total_gb if last_heartbeat else None,
            "ram_used_gb": last_heartbeat.ram_used_gb if last_heartbeat else None,
            "ram_free_gb": last_heartbeat.ram_free_gb if last_heartbeat else None,
            "disk_percent": last_heartbeat.disk_percent if last_heartbeat else None,
            "disk_total_gb": last_heartbeat.disk_total_gb if last_heartbeat else None,
            "disk_used_gb": last_heartbeat.disk_used_gb if last_heartbeat else None,
            "disk_free_gb": last_heartbeat.disk_free_gb if last_heartbeat else None,
            "disk_mount": getattr(last_heartbeat, "disk_mount", None) if last_heartbeat else None,
            "disks": _partitions_from_heartbeat(last_heartbeat),
            "uptime_seconds": last_heartbeat.uptime_seconds if last_heartbeat else None,
            "latency_ms": getattr(last_heartbeat, "latency_ms", None) if last_heartbeat else None,
            "temperature_celsius": getattr(last_heartbeat, "temperature_celsius", None) if last_heartbeat else None,
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
    if thresholds.disk_mount_rules is not None:
        cleaned = []
        seen: set[str] = set()
        for rule in thresholds.disk_mount_rules:
            mount = AlertService._normalize_mount(rule.mount)
            if not mount or mount in seen:
                continue
            if rule.warning >= rule.critical:
                raise HTTPException(
                    status_code=400,
                    detail=f"Warning doit être < critique pour {mount}",
                )
            seen.add(mount)
            cleaned.append({"mount": mount, "warning": rule.warning, "critical": rule.critical})
        agent.disk_mount_rules = json.dumps(cleaned)
    
    agent.updated_at = datetime.utcnow()
    db.commit()
    cache_service.delete_pattern("agents:*")
    
    return {
        "id": agent.id,
        "cpu_warning_threshold": agent.cpu_warning_threshold,
        "cpu_critical_threshold": agent.cpu_critical_threshold,
        "ram_warning_threshold": agent.ram_warning_threshold,
        "ram_critical_threshold": agent.ram_critical_threshold,
        "disk_warning_threshold": agent.disk_warning_threshold,
        "disk_critical_threshold": agent.disk_critical_threshold,
        "disk_mount_rules": AlertService.parse_disk_mount_rules(getattr(agent, "disk_mount_rules", None)),
        "message": "Seuils mis à jour avec succès"
    }


def _partitions_from_heartbeat(hb: Optional[Heartbeat]) -> List[Dict[str, Any]]:
    if not hb or not hb.disks_json:
        return []
    try:
        rows = json.loads(hb.disks_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    out: List[Dict[str, Any]] = []
    for d in rows or []:
        if not isinstance(d, dict):
            continue
        mount = str(d.get("mount") or "").strip()
        if not mount:
            continue
        out.append(
            {
                "name": d.get("name") or mount,
                "mount": mount,
                "letter": d.get("letter"),
                "label": d.get("label"),
                "device": d.get("device"),
                "fstype": d.get("fstype"),
                "percent": d.get("percent"),
                "total_gb": d.get("total_gb"),
                "used_gb": d.get("used_gb"),
                "free_gb": d.get("free_gb"),
                "alert": bool(d.get("alert")),
            }
        )
    return out


@app.get("/api/agents/{agent_id}/partitions")
@limiter.limit("60/minute")
def get_agent_partitions(
    request: Request,
    agent_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    """Partitions reported by the agent (from last heartbeat) for ceiling pickers."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    last_hb = (
        db.query(Heartbeat)
        .filter(Heartbeat.agent_id == agent_id)
        .order_by(Heartbeat.timestamp.desc())
        .first()
    )
    partitions = _partitions_from_heartbeat(last_hb)
    return {
        "agent_id": agent_id,
        "hostname": agent.hostname,
        "partitions": partitions,
        "disk_mount_rules": AlertService.parse_disk_mount_rules(getattr(agent, "disk_mount_rules", None)),
        "updated_at": last_hb.timestamp if last_hb else None,
    }


@app.get("/api/settings/discovered-partitions")
@limiter.limit("60/minute")
def list_discovered_partitions(
    request: Request,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    """Fleet-wide unique mounts seen in recent heartbeats (for global ceiling picker)."""
    agents = db.query(Agent).filter(Agent.status != "deleted").all()
    by_mount: Dict[str, Dict[str, Any]] = {}
    for agent in agents:
        last_hb = (
            db.query(Heartbeat)
            .filter(Heartbeat.agent_id == agent.id)
            .order_by(Heartbeat.timestamp.desc())
            .first()
        )
        for part in _partitions_from_heartbeat(last_hb):
            mount = part["mount"]
            entry = by_mount.get(mount)
            if entry is None:
                by_mount[mount] = {
                    **part,
                    "hosts": [agent.hostname],
                    "host_count": 1,
                }
            else:
                if agent.hostname not in entry["hosts"]:
                    entry["hosts"].append(agent.hostname)
                    entry["host_count"] = len(entry["hosts"])
    items = sorted(by_mount.values(), key=lambda r: (str(r.get("letter") or ""), str(r["mount"])))
    return {"data": items, "count": len(items)}



@app.get("/api/agents/{agent_id}/metrics/history")
@limiter.limit("60/minute")
def get_agent_metric_history(
    request: Request,
    agent_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
    name: str = "cpu.total.utilization",
    hours: int = 24,
    step: str = "60s",
):
    """Time-series history from VictoriaMetrics (STO-001 / DSH-002)."""
    from src.tsdb_service import tsdb

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")
    if hours < 1:
        hours = 1
    if hours > 24 * 90:
        hours = 24 * 90
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    return {
        "agent_id": agent_id,
        "name": name,
        "hours": hours,
        "step": step,
        **tsdb.query_range(agent_id, name, start, end, step),
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
            "cpu_architecture": getattr(hb, "cpu_architecture", None),
            "ram_percent": hb.ram_percent,
            "ram_total_gb": hb.ram_total_gb,
            "ram_used_gb": hb.ram_used_gb,
            "ram_free_gb": hb.ram_free_gb,
            "disk_percent": hb.disk_percent,
            "disk_total_gb": hb.disk_total_gb,
            "disk_used_gb": hb.disk_used_gb,
            "disk_free_gb": hb.disk_free_gb,
            "uptime_seconds": hb.uptime_seconds,
            "latency_ms": getattr(hb, "latency_ms", None),
            "temperature_celsius": getattr(hb, "temperature_celsius", None)
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
                "agent_name": alert.agent.hostname if alert.agent else None,
                "severity": AlertService.serialize_severity(alert.severity),
                "type": alert.type.value,
                "message": alert.message,
                "status": alert.status.value,
                "value": alert.value,
                "threshold": alert.threshold,
                "started_at": alert.started_at,
                "created_at": alert.started_at,
                "resolved_at": alert.resolved_at,
                "acknowledged_at": alert.acknowledged_at,
                "acknowledged_by": alert.acknowledged_by,
                "comment": alert.acknowledged_comment,
                "mail_status": alert.mail_status,
                "webhook_status": alert.webhook_status,
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
        "severity": AlertService.serialize_severity(alert.severity),
        "type": alert.type.value,
        "message": alert.message,
        "status": alert.status.value,
        "value": alert.value,
        "threshold": alert.threshold,
        "started_at": alert.started_at,
        "created_at": alert.started_at,
        "resolved_at": alert.resolved_at,
        "acknowledged_at": alert.acknowledged_at,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_comment": alert.acknowledged_comment,
        "mail_status": alert.mail_status,
        "webhook_status": alert.webhook_status,
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
    
    if alert.status != AlertStatus.OPEN:
        raise HTTPException(status_code=400, detail="Seules les alertes ouvertes peuvent être acquittées")
    
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.username
    alert.acknowledged_comment = ack_request.comment
    AlertService._record_event(
        db, "acknowledged", alert_id=alert.id, agent_id=alert.agent_id, actor=current_user.username, comment=ack_request.comment
    )
    
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
    
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.utcnow()
    alert.acknowledged_by = current_user.username
    alert.acknowledged_comment = resolve_request.comment
    AlertService._record_event(
        db, "resolved", alert_id=alert.id, agent_id=alert.agent_id, actor=current_user.username, comment=resolve_request.comment
    )
    
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


@app.get("/api/alerts/{alert_id}/timeline")
@limiter.limit("60/minute")
def alert_timeline(request: Request, alert_id: str, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    events = (
        db.query(AlertEvent)
        .filter(AlertEvent.alert_id == alert_id)
        .order_by(AlertEvent.created_at.asc())
        .all()
    )
    return {
        "alert_id": alert_id,
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "actor": e.actor,
                "comment": e.comment,
                "created_at": e.created_at,
            }
            for e in events
        ],
    }


@app.get("/api/maintenance")
@limiter.limit("60/minute")
def list_maintenance(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(MaintenanceWindow).order_by(MaintenanceWindow.starts_at.desc()).limit(200).all()
    now = datetime.utcnow()
    return {
        "data": [
            {
                "id": w.id,
                "agent_id": w.agent_id,
                "starts_at": w.starts_at,
                "ends_at": w.ends_at,
                "reason": w.reason,
                "created_by": w.created_by,
                "active": w.starts_at <= now <= w.ends_at,
            }
            for w in rows
        ]
    }


@app.post("/api/maintenance")
@limiter.limit("20/minute")
def create_maintenance(
    request: Request,
    body: MaintenanceWindowRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=400, detail="ends_at must be after starts_at")
    window = MaintenanceWindow(
        id=str(uuid.uuid4()),
        agent_id=body.agent_id,
        starts_at=body.starts_at.replace(tzinfo=None) if body.starts_at.tzinfo else body.starts_at,
        ends_at=body.ends_at.replace(tzinfo=None) if body.ends_at.tzinfo else body.ends_at,
        reason=body.reason,
        created_by=current_user.username,
    )
    db.add(window)
    db.commit()
    audit_logger.log_action(user_id=current_user.id, action="CREATE_MAINTENANCE", details=body.reason)
    return {"id": window.id, "status": "created"}


@app.delete("/api/maintenance/{window_id}")
@limiter.limit("20/minute")
def delete_maintenance(
    request: Request,
    window_id: str,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Fenêtre introuvable")
    db.delete(window)
    db.commit()
    return {"status": "deleted"}


@app.post("/api/agents/config/ack")
@limiter.limit("120/minute")
def ack_remote_config(
    request: Request,
    body: ConfigAckRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Accusé de réception d'une configuration appliquée (AGT-008).

    La version poussée est le maximum entre la révision de groupe et celle du
    plan d'hôte : l'accusé vaut donc pour les deux, sans quoi le plan serait
    republié indéfiniment à chaque battement.
    """
    try:
        agent = ConfigService.ack(db, agent_id, body.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    monitoring_plan.ack(db, agent, body.version)
    return {
        "status": "success",
        "agent_id": agent.id,
        "config_version_acked": agent.config_version_acked,
        "monitoring_version_acked": agent.monitoring_version_acked,
    }


@app.get("/api/groups")
@limiter.limit("60/minute")
def list_groups(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    groups = db.query(MachineGroup).order_by(MachineGroup.name.asc()).all()
    return {
        "data": [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "current_version": g.current_version,
                "agent_count": db.query(Agent).filter(Agent.group_id == g.id).count(),
                "updated_at": g.updated_at,
            }
            for g in groups
        ]
    }


@app.post("/api/groups")
@limiter.limit("20/minute")
def create_group(
    request: Request,
    body: MachineGroupCreateRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    if db.query(MachineGroup).filter(MachineGroup.name == body.name.strip()).first():
        raise HTTPException(status_code=400, detail="Nom de groupe déjà utilisé")
    group = ConfigService.create_group(db, body.name, body.description)
    audit_logger.log_action(user_id=current_user.id, action="CREATE_GROUP", details=group.name)
    return {"id": group.id, "name": group.name, "current_version": group.current_version}


@app.post("/api/groups/assign")
@limiter.limit("30/minute")
def assign_group(
    request: Request,
    body: MachineGroupAssignRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    try:
        agent = ConfigService.assign_agent(db, body.agent_id, body.group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_logger.log_action(
        user_id=current_user.id,
        action="ASSIGN_GROUP",
        details=f"agent={body.agent_id} group={body.group_id}",
    )
    return {"agent_id": agent.id, "group_id": agent.group_id, "config_version_acked": agent.config_version_acked}


@app.get("/api/groups/{group_id}/revisions")
@limiter.limit("60/minute")
def list_revisions(
    request: Request,
    group_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ConfigRevision)
        .filter(ConfigRevision.group_id == group_id)
        .order_by(ConfigRevision.version.desc())
        .limit(50)
        .all()
    )
    return {
        "data": [
            {
                "id": r.id,
                "version": r.version,
                "payload": json.loads(r.payload or "{}"),
                "note": r.note,
                "created_by": r.created_by,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@app.post("/api/groups/{group_id}/publish")
@limiter.limit("20/minute")
def publish_config(
    request: Request,
    group_id: str,
    body: ConfigPublishRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    try:
        rev = ConfigService.publish(
            db, group_id, body.payload or {}, created_by=current_user.username, note=body.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_logger.log_action(
        user_id=current_user.id,
        action="PUBLISH_CONFIG",
        details=f"group={group_id} v{rev.version}",
    )
    return {"group_id": group_id, "version": rev.version, "note": rev.note}


@app.post("/api/groups/{group_id}/rollback")
@limiter.limit("20/minute")
def rollback_config(
    request: Request,
    group_id: str,
    body: ConfigRollbackRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    try:
        rev = ConfigService.rollback(
            db, group_id, body.to_version, created_by=current_user.username
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"group_id": group_id, "version": rev.version, "note": rev.note}


@app.get("/api/coverage/overlaps")
@limiter.limit("60/minute")
def list_overlaps(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = (
        db.query(CoverageOverlap)
        .filter(CoverageOverlap.cleared_at.is_(None))
        .order_by(CoverageOverlap.detected_at.desc())
        .limit(200)
        .all()
    )
    return {
        "data": [
            {
                "id": o.id,
                "agent_id": o.agent_id,
                "hostname": o.agent.hostname if o.agent else None,
                "check_id": o.check_id,
                "plugin": o.plugin,
                "notes": o.notes,
                "detected_at": o.detected_at,
            }
            for o in rows
        ]
    }


@app.post("/api/coverage/overlaps")
@limiter.limit("30/minute")
def flag_overlap(
    request: Request,
    body: CoverageOverlapRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == body.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent introuvable")
    existing = (
        db.query(CoverageOverlap)
        .filter(
            CoverageOverlap.agent_id == body.agent_id,
            CoverageOverlap.check_id == body.check_id,
            CoverageOverlap.cleared_at.is_(None),
        )
        .first()
    )
    if existing:
        return {"id": existing.id, "status": "exists"}
    row = CoverageOverlap(
        id=str(uuid.uuid4()),
        agent_id=body.agent_id,
        check_id=body.check_id,
        plugin=body.plugin,
        notes=body.notes,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "status": "created"}


@app.post("/api/coverage/overlaps/{overlap_id}/clear")
@limiter.limit("30/minute")
def clear_overlap(
    request: Request,
    overlap_id: str,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    row = db.query(CoverageOverlap).filter(CoverageOverlap.id == overlap_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Overlap introuvable")
    row.cleared_at = datetime.utcnow()
    db.commit()
    return {"status": "cleared"}


@app.get("/api/coverage/map")
@limiter.limit("30/minute")
def coverage_map(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    """DES-004 status snapshot for UI (FS8 extinction tracking)."""
    from src.uat_service import ensure_coverage_seed, coverage_summary

    ensure_coverage_seed(db)
    rows = db.query(CoverageCheck).order_by(CoverageCheck.id.asc()).all()
    return {
        "data": [
            {
                "check_id": r.id,
                "plugin": r.plugin,
                "status": r.status,
                "sprint": r.sprint,
                "notes": r.notes,
                "description": r.description,
                "verified_at": r.verified_at,
                "decommissioned_at": r.decommissioned_at,
            }
            for r in rows
        ],
        "summary": coverage_summary(db),
    }


class CoverageStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


@app.patch("/api/coverage/checks/{check_id}")
@limiter.limit("30/minute")
def update_coverage_check(
    request: Request,
    check_id: str,
    body: CoverageStatusRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """FS8-05 — advance DES-004 row toward verified / decommissioned."""
    from src.uat_service import apply_coverage_status, ensure_coverage_seed

    ensure_coverage_seed(db)
    row = db.query(CoverageCheck).filter(CoverageCheck.id == check_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Check introuvable")
    try:
        apply_coverage_status(row, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.notes is not None:
        row.notes = body.notes
    db.commit()
    return {"check_id": row.id, "status": row.status}


@app.post("/api/coverage/checks/bulk-verify")
@limiter.limit("5/minute")
def bulk_verify_delivered(
    request: Request,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Mark all `delivered` checks as verified_in_production (pilot complete)."""
    from src.uat_service import apply_coverage_status, ensure_coverage_seed

    ensure_coverage_seed(db)
    updated = []
    for row in db.query(CoverageCheck).filter(CoverageCheck.status == "delivered").all():
        apply_coverage_status(row, "verified_in_production")
        updated.append(row.id)
    db.commit()
    return {"updated": updated}


@app.post("/api/coverage/checks/bulk-decommission")
@limiter.limit("5/minute")
def bulk_decommission_verified(
    request: Request,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """FS8-05 — decommission scripts for all verified_in_production checks."""
    from src.uat_service import apply_coverage_status, ensure_coverage_seed

    ensure_coverage_seed(db)
    updated = []
    for row in db.query(CoverageCheck).filter(CoverageCheck.status == "verified_in_production").all():
        apply_coverage_status(row, "script_decommissioned")
        updated.append(row.id)
    db.commit()
    return {"updated": updated}


# ==================== FS8: pilot, UAT, acceptance ====================

class PilotHostRequest(BaseModel):
    hostname: constr(min_length=1, max_length=255)
    agent_id: Optional[str] = None
    os: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class PilotChecklistRequest(BaseModel):
    enroll: bool = False
    first_metrics: bool = False
    heartbeat_ok: bool = False
    alerts_visible: bool = False
    status: Optional[str] = None
    notes: Optional[str] = None
    agent_id: Optional[str] = None


@app.get("/api/pilot/hosts")
@limiter.limit("60/minute")
def list_pilot_hosts(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(PilotHost).order_by(PilotHost.hostname.asc()).all()
    return {
        "data": [
            {
                "id": p.id,
                "hostname": p.hostname,
                "agent_id": p.agent_id,
                "os": p.os,
                "location": p.location,
                "checklist": json.loads(p.checklist or "{}"),
                "status": p.status,
                "notes": p.notes,
            }
            for p in rows
        ]
    }


@app.post("/api/pilot/hosts")
@limiter.limit("20/minute")
def create_pilot_host(
    request: Request,
    body: PilotHostRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    row = PilotHost(
        id=str(uuid.uuid4()),
        hostname=body.hostname,
        agent_id=body.agent_id,
        os=body.os,
        location=body.location,
        notes=body.notes,
        checklist=json.dumps(
            {"enroll": False, "first_metrics": False, "heartbeat_ok": False, "alerts_visible": False}
        ),
        status="pending",
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "hostname": row.hostname}


@app.patch("/api/pilot/hosts/{pilot_id}")
@limiter.limit("30/minute")
def update_pilot_host(
    request: Request,
    pilot_id: str,
    body: PilotChecklistRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    row = db.query(PilotHost).filter(PilotHost.id == pilot_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pilot host introuvable")
    checklist = {
        "enroll": body.enroll,
        "first_metrics": body.first_metrics,
        "heartbeat_ok": body.heartbeat_ok,
        "alerts_visible": body.alerts_visible,
    }
    row.checklist = json.dumps(checklist)
    if body.agent_id is not None:
        row.agent_id = body.agent_id or None
    if body.notes is not None:
        row.notes = body.notes
    if body.status:
        row.status = body.status
    elif all(checklist.values()):
        row.status = "onboarded"
    db.commit()
    return {"id": row.id, "status": row.status, "checklist": checklist}


@app.delete("/api/pilot/hosts/{pilot_id}")
@limiter.limit("20/minute")
def delete_pilot_host(
    request: Request,
    pilot_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    row = db.query(PilotHost).filter(PilotHost.id == pilot_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pilot host introuvable")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


class UatResultRequest(BaseModel):
    status: str
    evidence: Optional[str] = None
    tester: Optional[str] = None


@app.get("/api/uat/cases")
@limiter.limit("60/minute")
def list_uat_cases(
    request: Request,
    family: Optional[int] = None,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.uat_service import ensure_uat_seed, uat_summary

    ensure_uat_seed(db)
    q = db.query(UatCase).order_by(UatCase.family.asc(), UatCase.case_id.asc())
    if family is not None:
        q = q.filter(UatCase.family == family)
    rows = q.all()
    return {
        "data": [
            {
                "id": r.id,
                "family": r.family,
                "case_id": r.case_id,
                "title": r.title,
                "requirement_refs": r.requirement_refs,
                "status": r.status,
                "evidence": r.evidence,
                "tester": r.tester,
                "tested_at": r.tested_at,
            }
            for r in rows
        ],
        "summary": uat_summary(db),
    }


@app.patch("/api/uat/cases/{case_id}")
@limiter.limit("30/minute")
def update_uat_case(
    request: Request,
    case_id: str,
    body: UatResultRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    from src.uat_service import ensure_uat_seed

    ensure_uat_seed(db)
    row = db.query(UatCase).filter(UatCase.case_id == case_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="UAT case introuvable")
    if body.status not in ("pending", "pass", "fail", "blocked", "waived"):
        raise HTTPException(status_code=400, detail="Statut UAT invalide")
    row.status = body.status
    if body.evidence is not None:
        row.evidence = body.evidence
    row.tester = body.tester or current_user.username
    row.tested_at = datetime.utcnow()
    db.commit()
    return {"case_id": row.case_id, "status": row.status}


@app.get("/api/acceptance/pack")
@limiter.limit("20/minute")
def get_acceptance_pack(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    """FS8-06 — Lot 1 acceptance pack JSON."""
    from src.uat_service import build_acceptance_pack

    return build_acceptance_pack(db)


class SignOffRequest(BaseModel):
    role: constr(min_length=2, max_length=64)
    name: constr(min_length=1, max_length=128)
    decision: str = "approved"
    comment: Optional[str] = None


@app.get("/api/acceptance/signoffs")
@limiter.limit("30/minute")
def list_signoffs(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(AcceptanceSignOff).order_by(AcceptanceSignOff.signed_at.desc()).all()
    return {
        "data": [
            {
                "id": s.id,
                "role": s.role,
                "name": s.name,
                "decision": s.decision,
                "comment": s.comment,
                "signed_at": s.signed_at,
            }
            for s in rows
        ]
    }


@app.post("/api/acceptance/signoffs")
@limiter.limit("10/minute")
def create_signoff(
    request: Request,
    body: SignOffRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    if body.decision not in ("approved", "rejected", "conditional"):
        raise HTTPException(status_code=400, detail="Décision invalide")
    row = AcceptanceSignOff(
        id=str(uuid.uuid4()),
        role=body.role,
        name=body.name,
        decision=body.decision,
        comment=body.comment,
        signed_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "decision": row.decision}


# ==================== FS6: dashboards, reports, network, connectors ====================

class DashboardUpsertRequest(BaseModel):
    name: constr(min_length=1, max_length=128)
    widgets: List[Dict[str, Any]] = []
    shared: bool = False


class ReportScheduleRequest(BaseModel):
    name: constr(min_length=1, max_length=128)
    format: str = "csv"
    cron: str = "0 7 * * *"
    enabled: bool = True
    recipients: List[str] = []


class NetworkDeviceRequest(BaseModel):
    name: constr(min_length=1, max_length=128)
    host: constr(min_length=1, max_length=255)
    snmp_community: str = "public"
    snmp_version: str = "2c"
    enabled: bool = True


class ConnectorRequest(BaseModel):
    name: constr(min_length=1, max_length=128)
    kind: str = "docker_host"
    endpoint: Optional[str] = None
    enabled: bool = True


@app.get("/api/dashboards")
@limiter.limit("60/minute")
def list_dashboards(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = (
        db.query(CustomDashboard)
        .filter((CustomDashboard.owner_id == current_user.id) | (CustomDashboard.shared == True))  # noqa: E712
        .order_by(CustomDashboard.updated_at.desc())
        .all()
    )
    return {
        "data": [
            {
                "id": d.id,
                "name": d.name,
                "owner_id": d.owner_id,
                "widgets": json.loads(d.widgets or "[]"),
                "shared": d.shared,
                "updated_at": d.updated_at,
            }
            for d in rows
        ]
    }


@app.post("/api/dashboards")
@limiter.limit("30/minute")
def create_dashboard(
    request: Request,
    body: DashboardUpsertRequest,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    row = CustomDashboard(
        id=str(uuid.uuid4()),
        name=body.name,
        owner_id=current_user.id,
        widgets=json.dumps(body.widgets or []),
        shared=body.shared,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "shared": row.shared}


@app.put("/api/dashboards/{dashboard_id}")
@limiter.limit("30/minute")
def update_dashboard(
    request: Request,
    dashboard_id: str,
    body: DashboardUpsertRequest,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    row = db.query(CustomDashboard).filter(CustomDashboard.id == dashboard_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard introuvable")
    if row.owner_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Non autorisé")
    row.name = body.name
    row.widgets = json.dumps(body.widgets or [])
    row.shared = body.shared
    db.commit()
    return {"id": row.id, "status": "updated"}


@app.delete("/api/dashboards/{dashboard_id}")
@limiter.limit("20/minute")
def delete_dashboard(
    request: Request,
    dashboard_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    row = db.query(CustomDashboard).filter(CustomDashboard.id == dashboard_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Dashboard introuvable")
    if row.owner_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Non autorisé")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/reports/schedules")
@limiter.limit("60/minute")
def list_report_schedules(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(ReportSchedule).order_by(ReportSchedule.created_at.desc()).all()
    return {
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "format": r.format,
                "cron": r.cron,
                "enabled": r.enabled,
                "recipients": json.loads(r.recipients or "[]"),
                "last_run_at": r.last_run_at,
                "last_status": r.last_status,
            }
            for r in rows
        ]
    }


@app.post("/api/reports/schedules")
@limiter.limit("20/minute")
def create_report_schedule(
    request: Request,
    body: ReportScheduleRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    fmt = body.format.lower()
    if fmt not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    row = ReportSchedule(
        id=str(uuid.uuid4()),
        name=body.name,
        format=fmt,
        cron=body.cron,
        enabled=body.enabled,
        recipients=json.dumps(body.recipients or []),
        created_by=current_user.username,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name}


@app.post("/api/reports/generate")
@limiter.limit("20/minute")
def generate_report_now(
    request: Request,
    format: str = "csv",
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.report_service import fleet_rows, to_csv, to_pdf

    fmt = format.lower()
    if fmt not in ("csv", "pdf"):
        raise HTTPException(status_code=400, detail="format must be csv or pdf")
    agents = db.query(Agent).filter(Agent.status != "deleted").all()
    alerts = db.query(Alert).all()
    rows = fleet_rows(agents, alerts)
    if fmt == "csv":
        data = to_csv(rows)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="cbc-fleet-report.csv"'},
        )
    data = to_pdf("CBC Supervision — Fleet Report", rows)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cbc-fleet-report.pdf"'},
    )


@app.post("/api/reports/schedules/{schedule_id}/run")
@limiter.limit("20/minute")
def run_report_schedule(
    request: Request,
    schedule_id: str,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    from src.report_service import fleet_rows, to_csv, to_pdf

    sched = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule introuvable")
    agents = db.query(Agent).filter(Agent.status != "deleted").all()
    alerts = db.query(Alert).all()
    rows = fleet_rows(agents, alerts)
    payload = to_csv(rows) if sched.format == "csv" else to_pdf(sched.name, rows)
    sched.last_run_at = datetime.utcnow()
    sched.last_status = f"ok:{len(payload)}b"
    db.commit()
    media = "text/csv" if sched.format == "csv" else "application/pdf"
    ext = "csv" if sched.format == "csv" else "pdf"
    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="cbc-report-{sched.id}.{ext}"'},
    )


@app.get("/api/network/devices")
@limiter.limit("60/minute")
def list_network_devices(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(NetworkDevice).order_by(NetworkDevice.name.asc()).all()
    return {
        "data": [
            {
                "id": d.id,
                "name": d.name,
                "host": d.host,
                "snmp_community": d.snmp_community,
                "snmp_version": d.snmp_version,
                "enabled": d.enabled,
                "icmp_status": d.icmp_status,
                "snmp_status": d.snmp_status,
                "sys_descr": d.sys_descr,
                "last_rtt_ms": d.last_rtt_ms,
                "last_check": d.last_check,
                "error_message": d.error_message,
            }
            for d in rows
        ]
    }


@app.post("/api/network/devices")
@limiter.limit("20/minute")
def create_network_device(
    request: Request,
    body: NetworkDeviceRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    row = NetworkDevice(
        id=str(uuid.uuid4()),
        name=body.name,
        host=body.host,
        snmp_community=body.snmp_community,
        snmp_version=body.snmp_version,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name}


@app.post("/api/network/devices/{device_id}/probe")
@limiter.limit("30/minute")
def probe_network_device(
    request: Request,
    device_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.network_probe import probe_device

    row = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Device introuvable")
    result = probe_device(row.host, row.snmp_community or "public")
    row.icmp_status = result["icmp_status"]
    row.snmp_status = result["snmp_status"]
    row.last_rtt_ms = result["last_rtt_ms"]
    row.sys_descr = result["sys_descr"]
    row.error_message = result["error_message"]
    row.last_check = datetime.utcnow()
    db.commit()
    return {
        "id": row.id,
        "icmp_status": row.icmp_status,
        "snmp_status": row.snmp_status,
        "last_rtt_ms": row.last_rtt_ms,
        "sys_descr": row.sys_descr,
        "error_message": row.error_message,
    }


@app.post("/api/network/probe-all")
@limiter.limit("10/minute")
def probe_all_network_devices(
    request: Request,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    from src.network_probe import probe_device

    rows = db.query(NetworkDevice).filter(NetworkDevice.enabled == True).all()  # noqa: E712
    for row in rows:
        result = probe_device(row.host, row.snmp_community or "public")
        row.icmp_status = result["icmp_status"]
        row.snmp_status = result["snmp_status"]
        row.last_rtt_ms = result["last_rtt_ms"]
        row.sys_descr = result["sys_descr"]
        row.error_message = result["error_message"]
        row.last_check = datetime.utcnow()
    db.commit()
    return {"probed": len(rows)}


@app.delete("/api/network/devices/{device_id}")
@limiter.limit("20/minute")
def delete_network_device(
    request: Request,
    device_id: str,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    row = db.query(NetworkDevice).filter(NetworkDevice.id == device_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Device introuvable")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/connectors")
@limiter.limit("60/minute")
def list_connectors(request: Request, current_user: User = Depends(require_auth()), db: Session = Depends(get_db)):
    rows = db.query(ExternalConnector).order_by(ExternalConnector.name.asc()).all()
    return {
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "kind": c.kind,
                "endpoint": c.endpoint,
                "enabled": c.enabled,
                "status": c.status,
                "last_payload": json.loads(c.last_payload) if c.last_payload else None,
                "last_check": c.last_check,
                "error_message": c.error_message,
            }
            for c in rows
        ]
    }


@app.post("/api/connectors")
@limiter.limit("20/minute")
def create_connector(
    request: Request,
    body: ConnectorRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    if body.kind != "docker_host":
        raise HTTPException(status_code=400, detail="Only docker_host supported in Lot 1")
    row = ExternalConnector(
        id=str(uuid.uuid4()),
        name=body.name,
        kind=body.kind,
        endpoint=body.endpoint,
        enabled=body.enabled,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name}


@app.post("/api/connectors/{connector_id}/probe")
@limiter.limit("30/minute")
def probe_connector(
    request: Request,
    connector_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    from src.connector_service import probe_docker

    row = db.query(ExternalConnector).filter(ExternalConnector.id == connector_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Connector introuvable")
    result = probe_docker(row.endpoint)
    row.status = result["status"]
    row.error_message = result["error_message"]
    row.last_payload = result["last_payload"]
    row.last_check = datetime.utcnow()
    db.commit()
    return {
        "id": row.id,
        "status": row.status,
        "last_payload": json.loads(row.last_payload) if row.last_payload else None,
        "error_message": row.error_message,
    }


# Endpoints d'authentification
@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("30/minute")
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


def _serialize_user(user: User) -> Dict[str, Any]:
    """Représentation unique d'un utilisateur.

    La liste et le détail divergeaient : l'interface recevait des formes
    différentes pour la même ressource.
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "auth_source": (user.auth_source.value if user.auth_source else "local"),
        "external_id": user.external_id,
        "last_login_at": user.last_login_at,
        "manager_id": user.manager_id,
        "permissions": serialize_permissions(user.role),
    }


def _guard_last_admin(db: Session, user: User) -> None:
    """Refuse de laisser la plateforme sans administrateur actif."""
    remaining = (
        db.query(User)
        .filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
            User.id != user.id,
        )
        .count()
    )
    if remaining == 0:
        raise HTTPException(
            status_code=400,
            detail="Dernier administrateur actif : opération refusée",
        )


@app.get("/api/auth/users")
@limiter.limit("50/minute")  # Limite à 50 requêtes par minute
def list_users(
    request: Request,
    current_user: User = Depends(require_permission(Permission.USER_VIEW)),
    db: Session = Depends(get_db),
):
    """Liste tous les utilisateurs."""
    users = db.query(User).order_by(User.username.asc()).all()
    return [_serialize_user(u) for u in users]


@app.get("/api/auth/permissions")
@limiter.limit("60/minute")
def my_permissions(request: Request, current_user: User = Depends(require_auth())):
    """Permissions du compte connecté.

    L'interface s'en sert pour n'afficher que les actions réellement
    autorisées, au lieu de dupliquer la règle côté client.
    """
    return {
        "role": current_user.role.value,
        "permissions": serialize_permissions(current_user.role),
    }


@app.get("/api/auth/roles")
@limiter.limit("30/minute")
def list_roles(
    request: Request,
    current_user: User = Depends(require_permission(Permission.USER_VIEW)),
):
    """Matrice complète rôle -> permissions, pour l'écran d'administration."""
    return {
        "roles": [
            {"value": role.value, "permissions": serialize_permissions(role)}
            for role in UserRole
        ],
        "permissions": sorted(p.value for p in Permission),
    }


@app.put("/api/auth/users/{user_id}")
@limiter.limit("30/minute")
def update_user(
    request: Request,
    user_id: str,
    body: UpdateUserRequest,
    current_user: User = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    """Met à jour un utilisateur.

    Cet endpoint n'existait pas alors que l'interface l'appelait déjà : toute
    modification de compte échouait sans que l'opérateur en soit informé.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    is_self = user.id == current_user.id
    from_ldap = user.auth_source == AuthSource.LDAP

    if body.username is not None and body.username != user.username:
        if from_ldap:
            raise HTTPException(
                status_code=400,
                detail="Compte d'annuaire : l'identifiant est géré par le LDAP",
            )
        if db.query(User).filter(User.username == body.username, User.id != user_id).first():
            raise HTTPException(status_code=409, detail="Nom d'utilisateur déjà utilisé")
        user.username = body.username

    if body.email is not None and body.email != user.email:
        if db.query(User).filter(User.email == body.email, User.id != user_id).first():
            raise HTTPException(status_code=409, detail="Email déjà utilisé")
        user.email = body.email

    if body.role is not None:
        try:
            new_role = UserRole(body.role)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Rôle inconnu : "
                + str(body.role)
                + ". Attendu : "
                + ", ".join(r.value for r in UserRole),
            )
        # Se retirer soi-même l'administration peut laisser la plateforme sans
        # administrateur : on l'interdit explicitement.
        if is_self and user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            raise HTTPException(
                status_code=400,
                detail="Impossible de retirer son propre rôle administrateur",
            )
        if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            _guard_last_admin(db, user)
        user.role = new_role

    if body.is_active is not None and body.is_active != user.is_active:
        if is_self and not body.is_active:
            raise HTTPException(
                status_code=400, detail="Impossible de désactiver son propre compte"
            )
        if not body.is_active and user.role == UserRole.ADMIN:
            _guard_last_admin(db, user)
        user.is_active = body.is_active

    if body.manager_id is not None:
        if body.manager_id == user.id:
            raise HTTPException(
                status_code=400,
                detail="Un utilisateur ne peut pas être son propre responsable",
            )
        if body.manager_id and not db.query(User).filter(User.id == body.manager_id).first():
            raise HTTPException(status_code=404, detail="Responsable introuvable")
        user.manager_id = body.manager_id or None

    db.commit()
    db.refresh(user)

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_USER",
        details="user=" + user.username + " role=" + user.role.value + " active=" + str(user.is_active),
    )
    return _serialize_user(user)


@app.post("/api/auth/users/{user_id}/password")
@limiter.limit("10/minute")
def set_user_password(
    request: Request,
    user_id: str,
    body: SetPasswordRequest,
    current_user: User = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
):
    """Réinitialise le mot de passe d'un compte local."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if user.auth_source == AuthSource.LDAP:
        raise HTTPException(
            status_code=400,
            detail="Compte d'annuaire : le mot de passe est géré par le LDAP",
        )
    user.password_hash = AuthService.get_password_hash(body.password)
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        action="RESET_USER_PASSWORD",
        details="user=" + user.username,
    )
    return {"message": "Mot de passe mis à jour"}


@app.post("/api/auth/me/password")
@limiter.limit("5/minute")
def change_own_password(
    request: Request,
    body: ChangeOwnPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change le mot de passe du compte appelant.

    L'ecran Profil proposait un formulaire qui validait la saisie et affichait
    « Changement enregistre » sans rien envoyer : le mot de passe restait
    inchange. La reinitialisation administrateur
    (`/api/auth/users/{user_id}/password`) ne peut pas servir ici, car elle
    exige USER_MANAGE et ne verifie pas le secret courant.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")
    if user.auth_source == AuthSource.LDAP:
        raise HTTPException(
            status_code=400,
            detail="Compte d'annuaire : le mot de passe est gere par le LDAP",
        )
    if not AuthService.verify_password(body.current_password, user.password_hash):
        audit_logger.log_action(
            user_id=user.id,
            action="CHANGE_OWN_PASSWORD_DENIED",
            details="mot de passe courant invalide",
        )
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="Le nouveau mot de passe doit differer de l'actuel"
        )

    user.password_hash = AuthService.get_password_hash(body.new_password)
    db.commit()

    audit_logger.log_action(
        user_id=user.id,
        action="CHANGE_OWN_PASSWORD",
        details="user=" + user.username,
    )
    return {"message": "Mot de passe mis a jour"}


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


# ==================== AUDIT / CONFORMITÉ ====================


@app.get("/api/audit")
@limiter.limit("60/minute")
def list_audit_logs(
    request: Request,
    skip: int = 0,
    limit: int = 200,
    event_type: str = "",
    user_id: str = "",
    status: str = "",
    current_user: User = Depends(require_permission(Permission.AUDIT_VIEW)),
    db: Session = Depends(get_db),
):
    """Piste d'audit réelle, telle qu'elle a été écrite.

    Aucun endpoint de lecture n'existait : l'écran Audit reconstituait donc ses
    lignes à partir des alertes et des utilisateurs, avec une adresse IP codée
    en dur, et proposait ce résultat à l'export réglementaire.

    Réservé aux rôles Administrateur et Sécurité (permission `audit:view`).
    """
    if limit > 1000:
        limit = 1000

    query = db.query(AuditLog)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if status:
        query = query.filter(AuditLog.status == status)

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "event_type": r.event_type,
                "user_id": r.user_id,
                "username": r.username,
                "ip_address": r.ip_address,
                "target": r.target,
                "status": r.status,
                "details": r.details,
            }
            for r in rows
        ],
        "pagination": {"skip": skip, "limit": limit, "total": total},
    }


@app.get("/api/audit/export")
@limiter.limit("6/minute")
def export_audit_logs(
    request: Request,
    limit: int = 5000,
    current_user: User = Depends(require_permission(Permission.AUDIT_EXPORT)),
    db: Session = Depends(get_db),
):
    """Export CSV de la piste d'audit (COBAC).

    L'export est produit par le serveur à partir des lignes persistées : le
    fichier réglementaire ne peut donc pas contenir de données reconstituées
    côté navigateur. L'export est lui-même journalisé.
    """
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 50000))
        .all()
    )

    def _csv_cell(value) -> str:
        text = "" if value is None else str(value)
        # Le point-virgule est le séparateur : neutraliser toute occurrence.
        return '"' + text.replace('"', '""') + '"'

    lines = ["Horodatage;Acteur;IdentifiantActeur;Action;Cible;AdresseIP;Statut"]
    for r in rows:
        lines.append(
            ";".join(
                _csv_cell(v)
                for v in (
                    r.created_at.isoformat() if r.created_at else "",
                    r.username or "",
                    r.user_id or "",
                    r.event_type,
                    r.target or "",
                    r.ip_address or "",
                    r.status,
                )
            )
        )
    body = "\r\n".join(lines)

    audit_logger.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action="EXPORT_AUDIT",
        details="rows=" + str(len(rows)),
        ip_address=request.client.host if request.client else None,
    )

    from fastapi.responses import Response

    # BOM UTF-8 : Excel ouvre correctement les accents sans réglage manuel.
    return Response(
        content="\ufeff" + body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cbc-audit-cobac.csv"'},
    )


# ==================== LDAP / ANNUAIRE (API-003) ====================


@app.get("/api/settings/ldap")
@limiter.limit("30/minute")
def get_ldap_settings(
    request: Request,
    current_user: User = Depends(require_permission(Permission.SETTINGS_VIEW)),
):
    """Configuration de l'annuaire, sans aucun secret.

    Le mot de passe du compte de service n'est jamais renvoyé : seule
    l'information « configuré ou non » remonte.
    """
    from src.ldap_service import LdapService

    return LdapService.status()


@app.post("/api/settings/ldap/test")
@limiter.limit("6/minute")
def test_ldap_settings(
    request: Request,
    current_user: User = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    """Teste la joignabilité de l'annuaire et le bind du compte de service."""
    from src.ldap_service import LdapService

    result = LdapService.test_connection()
    audit_logger.log_action(
        user_id=current_user.id,
        action="TEST_LDAP",
        details="ok=" + str(result.get("ok")) + " stage=" + str(result.get("stage")),
    )
    return result


@app.post("/api/settings/ldap/probe-user")
@limiter.limit("6/minute")
def probe_ldap_user(
    request: Request,
    body: LdapProbeRequest,
    current_user: User = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    """Résout un compte dans l'annuaire et montre le rôle qui lui serait attribué.

    Permet de valider le filtre et la table de correspondance des groupes
    avant d'ouvrir l'authentification annuaire aux utilisateurs. Aucune
    authentification n'est effectuée : aucun mot de passe n'est demandé.
    """
    from src.ldap_service import LdapService

    if not LdapService.is_enabled():
        raise HTTPException(status_code=400, detail="Authentification annuaire inactive")

    profile = LdapService.find_user(body.username)
    if profile is None:
        return {"found": False, "detail": "Compte introuvable ou filtre ambigu"}
    return {
        "found": True,
        "username": profile.username,
        "email": profile.email,
        "display_name": profile.display_name,
        "dn": profile.dn,
        "groups": profile.groups,
        "resolved_role": profile.role.value,
    }


@app.get("/api/settings/ldap/role-mappings")
@limiter.limit("30/minute")
def list_ldap_role_mappings(
    request: Request,
    current_user: User = Depends(require_permission(Permission.SETTINGS_VIEW)),
    db: Session = Depends(get_db),
):
    """Correspondances rôle <- identité d'annuaire, propres à cette application.

    Elles vivent dans cette base : CBC n'a aucun groupe à créer côté Active
    Directory et le compte de service reste en lecture seule.
    """
    rows = (
        db.query(LdapRoleMapping)
        .order_by(LdapRoleMapping.priority.asc(), LdapRoleMapping.value.asc())
        .all()
    )
    return {
        "data": [
            {
                "id": r.id,
                "kind": r.kind,
                "value": r.value,
                "role": r.role.value,
                "priority": r.priority,
                "description": r.description,
                "enabled": r.enabled,
                "created_by": r.created_by,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@app.post("/api/settings/ldap/role-mappings")
@limiter.limit("20/minute")
def create_ldap_role_mapping(
    request: Request,
    body: LdapRoleMappingRequest,
    current_user: User = Depends(require_permission(Permission.SETTINGS_EDIT)),
    db: Session = Depends(get_db),
):
    """Attribue un rôle Sentinel à un groupe ou à un compte d'annuaire."""
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Rôle inconnu. Attendu : " + ", ".join(r.value for r in UserRole),
        )
    if body.kind not in ("group", "user"):
        raise HTTPException(status_code=422, detail="kind doit valoir 'group' ou 'user'")

    value = body.value.strip()
    if not value:
        raise HTTPException(status_code=422, detail="value ne peut pas être vide")

    existing = (
        db.query(LdapRoleMapping)
        .filter(LdapRoleMapping.kind == body.kind, LdapRoleMapping.value == value)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Cette correspondance existe déjà")

    row = LdapRoleMapping(
        id=str(uuid.uuid4()),
        kind=body.kind,
        value=value,
        role=role,
        priority=body.priority if body.priority is not None else 100,
        description=body.description,
        enabled=True if body.enabled is None else body.enabled,
        created_by=current_user.username,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Accorder des droits sur la plateforme de supervision est une action
    # sensible : elle doit laisser une trace nominative.
    audit_logger.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action="CREATE_LDAP_ROLE_MAPPING",
        details=body.kind + "=" + value + " -> " + role.value,
        ip_address=request.client.host if request.client else None,
    )
    return {"id": row.id, "kind": row.kind, "value": row.value, "role": row.role.value}


@app.delete("/api/settings/ldap/role-mappings/{mapping_id}")
@limiter.limit("20/minute")
def delete_ldap_role_mapping(
    request: Request,
    mapping_id: str,
    current_user: User = Depends(require_permission(Permission.SETTINGS_EDIT)),
    db: Session = Depends(get_db),
):
    row = db.query(LdapRoleMapping).filter(LdapRoleMapping.id == mapping_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Correspondance introuvable")

    detail = row.kind + "=" + row.value + " -> " + row.role.value
    db.delete(row)
    db.commit()

    audit_logger.log_action(
        user_id=current_user.id,
        username=current_user.username,
        action="DELETE_LDAP_ROLE_MAPPING",
        details=detail,
        ip_address=request.client.host if request.client else None,
    )
    return {"message": "Correspondance supprimée"}


@app.post("/api/settings/ldap/preview-role")
@limiter.limit("20/minute")
def preview_ldap_role(
    request: Request,
    body: LdapProbeRequest,
    current_user: User = Depends(require_permission(Permission.SETTINGS_VIEW)),
    db: Session = Depends(get_db),
):
    """Montre le rôle qu'obtiendrait un compte, correspondances appliquées.

    Permet de vérifier une attribution avant qu'un utilisateur ne se connecte,
    plutôt que de la découvrir en production.
    """
    from src.ldap_service import LdapService

    if not LdapService.is_enabled():
        raise HTTPException(status_code=400, detail="Authentification annuaire inactive")

    profile = LdapService.find_user(body.username, db=db)
    if profile is None:
        return {"found": False, "detail": "Compte introuvable ou filtre ambigu"}
    return {
        "found": True,
        "username": profile.username,
        "display_name": profile.display_name,
        "dn": profile.dn,
        "groups": profile.groups,
        "resolved_role": profile.role.value,
        "attributes": profile.attributes,
    }


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
        "disk_mount_rules": AlertService.parse_disk_mount_rules(getattr(settings, "disk_mount_rules", None)),
        "duration_seconds": settings.threshold_duration_seconds or 300,
        "escalate_after_minutes": settings.escalate_after_minutes or 15,
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
    if thresholds.duration_seconds is not None:
        settings.threshold_duration_seconds = max(0, int(thresholds.duration_seconds))
    if thresholds.escalate_after_minutes is not None:
        settings.escalate_after_minutes = max(1, int(thresholds.escalate_after_minutes))
    if thresholds.disk_mount_rules is not None:
        cleaned = []
        seen = set()
        for rule in thresholds.disk_mount_rules:
            mount = (rule.mount or "").strip()
            if not mount or mount in seen:
                continue
            if rule.warning >= rule.critical:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pour {mount}, le warning doit être inférieur au critique",
                )
            seen.add(mount)
            cleaned.append({
                "mount": mount,
                "warning": float(rule.warning),
                "critical": float(rule.critical),
            })
        settings.disk_mount_rules = json.dumps(cleaned)

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
        "disk_mount_rules": AlertService.parse_disk_mount_rules(getattr(settings, "disk_mount_rules", None)),
        "duration_seconds": settings.threshold_duration_seconds or 300,
        "escalate_after_minutes": settings.escalate_after_minutes or 15,
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
        "webhook_url": config.webhook_url,
        "webhook_enabled": bool(config.webhook_enabled),
        "webhook_secret_set": bool(config.webhook_secret),
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
    if config_request.webhook_url is not None:
        config.webhook_url = config_request.webhook_url
    if config_request.webhook_secret:
        config.webhook_secret = config_request.webhook_secret
    config.webhook_enabled = bool(config_request.webhook_enabled)

    db.commit()
    db.refresh(config)

    audit_logger.log_action(
        user_id=current_user.id,
        action="UPDATE_MESSAGING_CONFIG",
        details="Updated messaging configuration"
    )

    return {
        "id": config.id,
        "recipients": json.loads(config.recipients),
        "api_endpoint": config.api_endpoint,
        "api_timeout": config.api_timeout,
        "enabled": config.enabled,
        "updated_at": config.updated_at
    }


class MessagingTestRequest(BaseModel):
    to: Optional[EmailStr] = None
    subject: Optional[str] = "SENTINEL · Mail de test"
    body: Optional[str] = None
    cc: Optional[List[EmailStr]] = None


@app.post("/api/settings/messaging/test")
@limiter.limit("10/minute")
def send_messaging_test(
    request: Request,
    body: MessagingTestRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Send a simple test mail via CBC Mail API (Lot 1)."""
    cfg = MessagingService._runtime_config(db)
    to_addr = str(body.to) if body.to else None
    if not to_addr:
        recipients = cfg.get("recipients") or []
        to_addr = recipients[0] if recipients else None
    if not to_addr:
        raise HTTPException(
            status_code=400,
            detail="Indiquez un destinataire (to) ou ajoutez-en un dans Paramètres → Messagerie.",
        )
    html = body.body or (
        f"<p>Bonjour,</p>"
        f"<p>Ceci est un <strong>mail de test</strong> depuis SENTINEL / CBC Supervision.</p>"
        f"<ul>"
        f"<li>Envoyé par : <code>{current_user.username}</code> ({current_user.email})</li>"
        f"<li>Horodatage : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</li>"
        f"</ul>"
        f"<p style='color:#64748B;font-size:12px'>Si vous lisez ceci, l’API Mail CBC est joignable depuis la plateforme.</p>"
    )
    cc = [str(x) for x in (body.cc or [])] or None
    result = MessagingService.send_simple_mail(
        to=to_addr,
        subject=body.subject or "SENTINEL · Mail de test",
        body=html,
        is_html=True,
        cc=cc,
        db=db,
        require_enabled=True,
    )
    audit_logger.log_event(
        event_type="messaging_test",
        user_id=current_user.id,
        username=current_user.username,
        details={"to": to_addr, "ok": result.get("ok"), "error": result.get("error")},
        status="success" if result.get("ok") else "failed",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error") or "Échec d'envoi")
    return {"status": "sent", **result}


@app.get("/api/settings/mail-templates")
@limiter.limit("30/minute")
def list_mail_templates(
    request: Request,
    kind: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    from src.mail_templates import seed_defaults

    seed_defaults(db)
    q = db.query(MailTemplate)
    if kind:
        q = q.filter(MailTemplate.kind == kind)
    if agent_id is not None:
        q = q.filter(MailTemplate.agent_id == agent_id)
    rows = q.order_by(MailTemplate.kind, MailTemplate.event_key, MailTemplate.agent_id).all()
    return {
        "data": [
            {
                "id": r.id,
                "kind": r.kind,
                "event_key": r.event_key,
                "agent_id": r.agent_id or "",
                "subject": r.subject,
                "body_html": r.body_html,
                "description": r.description,
                "scope": "agent" if r.agent_id else "global",
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    }


@app.put("/api/settings/mail-templates")
@limiter.limit("20/minute")
def upsert_mail_template(
    request: Request,
    body: MailTemplateUpdateRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    aid = body.agent_id or ""
    row = (
        db.query(MailTemplate)
        .filter(
            MailTemplate.kind == body.kind,
            MailTemplate.event_key == body.event_key,
            MailTemplate.agent_id == aid,
        )
        .first()
    )
    if not row:
        row = MailTemplate(
            id=str(uuid.uuid4()),
            kind=body.kind,
            event_key=body.event_key,
            agent_id=aid,
        )
        db.add(row)
    row.subject = body.subject
    row.body_html = body.body_html
    if body.description is not None:
        row.description = body.description
    db.commit()
    db.refresh(row)
    audit_logger.log_action(
        user_id=current_user.id,
        action="UPSERT_MAIL_TEMPLATE",
        details=f"{body.kind}:{body.event_key} agent={aid or 'global'}",
    )
    return {
        "id": row.id,
        "kind": row.kind,
        "event_key": row.event_key,
        "agent_id": row.agent_id,
        "subject": row.subject,
    }


@app.get("/api/system/notification-channel-status")
@limiter.limit("60/minute")
def get_notification_channel_status(request: Request, current_user: User = Depends(require_operator_or_admin()), db: Session = Depends(get_db)):
    """
    Récupère le statut du canal de notification.
    
    Cet endpoint est utilisé par le frontend pour afficher l'indicateur visuel
    de l'état du canal de notification (exigence R11 de l'encadreur).
    """
    status = MessagingService.health_check(db)
    return status


@app.delete("/api/settings/mail-templates")
@limiter.limit("20/minute")
def reset_mail_template(
    request: Request,
    kind: str,
    event_key: str,
    agent_id: Optional[str] = None,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Revient au gabarit livré pour cette vérification.

    La ligne est supprimée plutôt que réécrite avec le défaut : recopier
    figerait une version du jour, et l'exploitant croirait suivre le gabarit
    livré tout en gardant une copie qui cesse d'évoluer avec le produit.
    """
    from src.mail_templates import seed_defaults

    target = (agent_id or "").strip()
    removed = (
        db.query(MailTemplate)
        .filter(
            MailTemplate.kind == kind,
            MailTemplate.event_key == event_key,
            MailTemplate.agent_id == target,
        )
        .delete()
    )
    db.commit()
    if target == "":
        # Sans réinstallation immédiate, la vérification n'aurait plus aucun
        # gabarit et l'alerte partirait sans mise en forme.
        seed_defaults(db)

    audit_logger.log_action(
        user_id=current_user.id,
        action="RESET_MAIL_TEMPLATE",
        details="%s/%s%s" % (kind, event_key, (" hote=%s" % target) if target else " (global)"),
    )
    return {"status": "success", "removed": removed}


@app.post("/api/settings/mail-templates/preview")
@limiter.limit("60/minute")
def preview_mail_template(
    request: Request,
    body: MailTemplatePreviewRequest,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    """Rend le gabarit sur un jeu de valeurs, sans rien envoyer.

    Un gabarit ne se relit pas, il se regarde. Sans aperçu, la première
    alerte réelle sert de test — au plus mauvais moment, et devant les
    destinataires.
    """
    from src.mail_templates import render

    sample: Dict[str, Any] = {
        "hostname": "web-01.prod",
        "agent_id": "A3F09C",
        "severity": "critical",
        "alert_type": "disk_high",
        "message": "Disque /u01 à 96 %",
        "value": 96,
        "threshold": 85,
        "mount": "/u01",
        "service_name": "swift-alliance",
        "file_path": "/var/lock/cbc.flag",
        "plugin": "service.manage",
        "status": "succeeded",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    sample.update(body.context or {})
    subject, html = render(body.subject, body.body_html, sample)
    return {"subject": subject, "body_html": html, "context": sample}


@app.post("/api/settings/webhook/test")
@limiter.limit("10/minute")
def send_webhook_test(
    request: Request,
    body: WebhookTestRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Envoie une charge signée de test — le canal qui déclenche n8n.

    Sans cet essai, la seule façon de savoir si n8n reçoit quelque chose est
    d'attendre un vrai incident. La charge porte `test: true` pour qu'un
    scénario n8n puisse la reconnaître et ne pas la traiter comme une alerte
    réelle.
    """
    cfg = db.query(MessagingConfig).filter(MessagingConfig.id == "default").first()
    if not cfg or not cfg.webhook_enabled or not cfg.webhook_url or not cfg.webhook_secret:
        raise HTTPException(
            status_code=400,
            detail="Webhook non configuré : renseigner l'URL et le secret, puis l'activer.",
        )

    payload = {
        "test": True,
        "event": body.event_key or "webhook.test",
        "severity": "info",
        "hostname": "essai-plateforme",
        "message": "Essai de webhook émis depuis la plateforme CBC Supervision.",
        "emitted_at": datetime.utcnow().isoformat() + "Z",
        "emitted_by": current_user.username,
    }
    from src import webhook_service

    ok = webhook_service.post_signed(cfg.webhook_url, cfg.webhook_secret, payload)

    audit_logger.log_action(
        user_id=current_user.id,
        action="TEST_WEBHOOK",
        details="url=%s resultat=%s" % (cfg.webhook_url, "ok" if ok else "echec"),
    )
    if not ok:
        raise HTTPException(
            status_code=502,
            detail="Le webhook n'a pas répondu favorablement. Vérifier l'URL, le "
                   "secret partagé et que le scénario n8n est actif.",
        )
    return {"status": "success", "url": cfg.webhook_url, "signed": True}


@app.post("/api/agents/inventory")
@limiter.limit("12/hour")
def push_inventory(
    request: Request,
    body: InventoryRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    """Reçoit l'inventaire logiciel d'un hôte.

    Cadence volontairement basse : ce relevé interroge la base de registre ou
    le gestionnaire de paquets, et ne bouge que rarement. Il ne voyage donc
    pas avec le battement.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    payload = {
        "services": body.services or [],
        "applications": body.applications or [],
        "drivers": body.drivers or [],
        "truncated": body.truncated or [],
        "unavailable": body.unavailable or [],
    }
    agent.inventory_json = json.dumps(payload, default=str)
    agent.inventory_at = datetime.utcnow()
    db.commit()
    cache_service.delete_pattern("agents:*")

    return {
        "status": "success",
        "services": len(payload["services"]),
        "applications": len(payload["applications"]),
        "drivers": len(payload["drivers"]),
    }


@app.get("/api/agents/{agent_id}/inventory")
@limiter.limit("60/minute")
def get_inventory(
    request: Request,
    agent_id: str,
    current_user: User = Depends(require_auth()),
    db: Session = Depends(get_db),
):
    """Inventaire d'un hôte : services offerts, applications, pilotes.

    Sert aussi le sélecteur de services du plan de supervision : l'exploitant
    choisit parmi ce que l'hôte déclare, au lieu de saisir un nom. Une faute
    de frappe produirait une surveillance qui ne surveille rien — le service
    resterait « inconnu » au lieu d'être « arrêté ».
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    parsed = _parse_runtime(agent.inventory_json) or {}
    return {
        "agent_id": agent.id,
        "collected_at": agent.inventory_at,
        "services": parsed.get("services") or [],
        "applications": parsed.get("applications") or [],
        "drivers": parsed.get("drivers") or [],
        "truncated": parsed.get("truncated") or [],
        "unavailable": parsed.get("unavailable") or [],
    }


@app.get("/api/vlan-subnets")
@limiter.limit("60/minute")
def list_vlan_subnets(
    request: Request,
    current_user: User = Depends(require_operator_or_admin()),
    db: Session = Depends(get_db),
):
    """Plan d'adressage importé : sous-réseau → VLAN."""
    rows = db.query(VlanSubnet).order_by(VlanSubnet.cidr).all()
    return {
        "data": [
            {
                "id": r.id,
                "cidr": r.cidr,
                "range_start": r.range_start,
                "range_end": r.range_end,
                "vlan": r.vlan,
                "label": r.label,
                "imported_at": r.imported_at,
                "imported_by": r.imported_by,
                "source_file": r.source_file,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.post("/api/vlan-subnets/import")
@limiter.limit("10/minute")
async def import_vlan_subnets(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Importe le plan d'adressage de l'équipe réseau (CSV ou .xlsx).

    L'import **remplace** la table au lieu de la compléter : un plan
    d'adressage est un document entier, et fusionner laisserait vivre
    indéfiniment des sous-réseaux supprimés du fichier — donc des hôtes
    rattachés à un VLAN qui n'existe plus.

    Les lignes fautives sont rendues à l'appelant, ligne par ligne. Un import
    à moitié appliqué en silence rattacherait des hôtes au mauvais VLAN sans
    que personne ne le sache.
    """
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (2 Mo maximum).")

    try:
        report = vlan_service.parse(content, file.filename or "")
    except vlan_service.VlanImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.query(VlanSubnet).delete()
    now = datetime.utcnow()
    for row in report.rows:
        db.add(
            VlanSubnet(
                id=str(uuid.uuid4()),
                cidr=row.cidr,
                range_start=row.range_start,
                range_end=row.range_end,
                vlan=row.vlan,
                label=row.label,
                imported_at=now,
                imported_by=current_user.username,
                source_file=(file.filename or "")[:255],
            )
        )
    db.commit()
    cache_service.delete_pattern("agents:*")

    audit_logger.log_action(
        user_id=current_user.id,
        action="IMPORT_VLAN_SUBNETS",
        details="fichier=%s acceptees=%d rejetees=%d"
        % (file.filename, report.accepted_count, len(report.rejected)),
    )

    return {
        "imported": report.accepted_count,
        "rejected": report.rejected,
        "message": "%d sous-réseau(x) importé(s)" % report.accepted_count,
    }


@app.delete("/api/vlan-subnets")
@limiter.limit("10/minute")
def clear_vlan_subnets(
    request: Request,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db),
):
    """Vide le plan d'adressage. Les VLAN déduits disparaissent avec lui."""
    removed = db.query(VlanSubnet).delete()
    db.commit()
    cache_service.delete_pattern("agents:*")
    audit_logger.log_action(
        user_id=current_user.id,
        action="CLEAR_VLAN_SUBNETS",
        details="supprimes=%d" % removed,
    )
    return {"removed": removed}


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

    # Expiration en UTC : _resolve_enrollment_token compare à datetime.utcnow(),
    # datetime.now() aurait donné une durée décalée du fuseau de l'hôte.
    expires_at = datetime.utcnow() + timedelta(hours=settings.enrollment_token_ttl_hours)

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
    """Supprime un agent et ses dépendances."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    hostname = agent.hostname
    delete_agent_with_deps(db, agent)
    db.commit()
    cache_service.delete_pattern("agents:*")

    audit_logger.log_action(
        user_id=current_user.id,
        action="DELETE_AGENT",
        details=f"Deleted agent {agent_id} ({hostname})"
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
    """Route retirée : la supervision se règle désormais par hôte.

    Cette route n'a jamais rien enregistré — elle journalisait un évènement
    d'audit puis renvoyait la requête en écho, pendant que l'interface
    affichait « mise à jour avec succès » et perdait tout au rafraîchissement.
    Répondre 410 plutôt que de la supprimer donne à un appelant existant la
    raison et la destination, au lieu d'un 404 muet.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "code": "moved_to_agent_plan",
            "message": (
                "La supervision des services et des fichiers se règle par hôte. "
                "Utilisez GET/PUT /api/agents/{agent_id}/monitoring."
            ),
            "replacement": "/api/agents/{agent_id}/monitoring",
        },
    )


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
    """Route retirée : la supervision se règle désormais par hôte.

    Même constat que pour les services : cette route n'enregistrait rien.
    Voir `PUT /api/agents/{agent_id}/monitoring`.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "code": "moved_to_agent_plan",
            "message": (
                "La supervision des services et des fichiers se règle par hôte. "
                "Utilisez GET/PUT /api/agents/{agent_id}/monitoring."
            ),
            "replacement": "/api/agents/{agent_id}/monitoring",
        },
    )


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
