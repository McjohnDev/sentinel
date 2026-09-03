from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Enum as SQLEnum, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from src.database import Base


class UserRole(enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    READ_ONLY = "read_only"
    # DSH-025 — profil sécurité : lecture complète + audit et conformité,
    # sans droit de modification sur le parc ni sur la configuration.
    SECURITY = "security"


class AuthSource(enum.Enum):
    """Origine du compte : base locale ou annuaire d'entreprise."""

    LOCAL = "local"
    LDAP = "ldap"


class MachineType(enum.Enum):
    SERVER = "server"
    WORKSTATION = "workstation"


class User(Base):
    """Modèle de données pour un utilisateur du dashboard."""
    
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    
    role = Column(SQLEnum(UserRole), default=UserRole.OPERATOR, nullable=False)

    # Org hierarchy for mail CC (owner → manager → …)
    manager_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    # API-003 — provenance du compte. Un compte LDAP n'a pas de mot de passe
    # local exploitable et ne peut pas en changer depuis l'application.
    auth_source = Column(SQLEnum(AuthSource), default=AuthSource.LOCAL, nullable=False)
    # Identifiant stable côté annuaire (DN), pour retrouver le compte même
    # après un renommage.
    external_id = Column(String, nullable=True, index=True)
    last_login_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    manager = relationship("User", remote_side=[id], foreign_keys=[manager_id])


class Agent(Base):
    """Modèle de données pour un agent de supervision.

    Deux familles de champs, volontairement distinguées (AGT-002) :

    * **Constatés** — déclarés par l'agent et rafraîchis à chaque heartbeat :
      identité machine, réseau, système, caractéristiques matérielles. La
      plateforme n'en est pas propriétaire et refuse toute écriture par
      l'interface : les corriger à la main produirait un inventaire qui
      contredit la machine réelle.
    * **Attribués** — posés par l'exploitation : nom d'affichage, site,
      responsable, seuils. Modifiables (voir `EDITABLE_FIELDS`).
    """

    __tablename__ = 'agents'

    #: Code hexadécimal à 6 caractères attribué par la plateforme
    #: (voir `src.agent_identity`). Court exprès : il doit pouvoir être dicté.
    id = Column(String, primary_key=True)
    machine_id = Column(String, unique=True, nullable=False, index=True)  # UUID de la machine
    hostname = Column(String, nullable=False)  # nom machine — constaté, non modifiable
    name = Column(String, nullable=True)  # nom d'hôte affiché — attribué, modifiable
    ip_address = Column(String)
    os = Column(String)  # Windows, Linux, macOS
    os_version = Column(String)
    agent_version = Column(String)
    auth_key = Column(String, unique=True, nullable=False)  # Clé d'authentification
    # active | retired | uninstalled | revoked | deleted
    status = Column(String, default='active')
    last_communication = Column(DateTime)
    enrolled_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    location = Column(String, nullable=True)  # Localisation de l'agent
    machine_type = Column(SQLEnum(MachineType), default=MachineType.WORKSTATION, nullable=False)  # Type de machine

    # --- Caractéristiques de l'hôte (constatées, rafraîchies au heartbeat) ---
    cpu_cores = Column(Integer, nullable=True)
    ram_total_gb = Column(Float, nullable=True)
    disk_total_gb = Column(Float, nullable=True)

    #: VLAN que l'hôte étiquette lui-même, quand il en étiquette un. Vide pour
    #: la plupart des machines : sur un port d'accès, le commutateur pose et
    #: retire l'étiquette de façon transparente et l'hôte ne peut pas la
    #: connaître. « Vide » veut donc dire *non déterminable depuis l'hôte*,
    #: jamais *aucun VLAN* — d'où le champ déclaré ci-dessous, qui lui existe
    #: pour tous les hôtes.
    vlan_observed = Column(String, nullable=True)

    #: VLAN déclaré par l'exploitation. Attribué, donc modifiable : c'est une
    #: information que l'équipe réseau détient et que la machine ignore.
    vlan = Column(String, nullable=True)

    #: Cadence de battement propre à cet hôte. Vide = suit la cadence globale.
    #: Un serveur SWIFT peut mériter dix secondes là où un poste de bureau se
    #: contente d'une minute : imposer la même cadence à tout le parc, c'est
    #: choisir entre surveiller trop peu les machines critiques ou trop
    #: souvent les autres.
    heartbeat_interval_seconds = Column(Integer, nullable=True)

    #: Inventaire logiciel remonté par l'agent : services offerts, applications
    #: et pilotes installés. Stocké en JSON plutôt qu'en tables dédiées : c'est
    #: un document par hôte, consulté en entier (fiche, sélecteur de services)
    #: et jamais joint. Une recherche à l'échelle du parc — « quels hôtes ont
    #: cette version ? » — demanderait des tables ; ce n'est pas demandé
    #: aujourd'hui et la simplicité prime.
    inventory_json = Column(Text, nullable=True)
    inventory_at = Column(DateTime, nullable=True)

    # --- Exécution de l'agent sur l'hôte (AGT-012, point 9) ---
    # Bloc JSON : chemin d'installation, mode d'exécution, service, PID,
    # compte, élévation, canal de packaging, plugins chargés… Stocké en JSON
    # car c'est un descriptif d'affichage : on le lit entier, on n'y requête
    # pas. Les deux champs ci-dessous en sont extraits pour pouvoir filtrer
    # un parc (« quels hôtes tournent en console ? »).
    runtime_json = Column(Text, nullable=True)
    run_mode = Column(String, nullable=True, index=True)  # service|systemd|launchd|console|docker
    run_as_user = Column(String, nullable=True)

    # --- Désinstallation (point 4) ---
    uninstalled_at = Column(DateTime, nullable=True)
    uninstalled_by = Column(String, nullable=True)  # 'agent' | identifiant utilisateur

    # Seuils personnalisés par agent (None = utiliser les seuils globaux)
    cpu_warning_threshold = Column(Float, nullable=True)
    cpu_critical_threshold = Column(Float, nullable=True)
    ram_warning_threshold = Column(Float, nullable=True)
    ram_critical_threshold = Column(Float, nullable=True)
    disk_warning_threshold = Column(Float, nullable=True)
    disk_critical_threshold = Column(Float, nullable=True)
    # Per-host partition ceilings: [{"mount":"C:\\","warning":85,"critical":95}]
    disk_mount_rules = Column(Text, nullable=True)

    # FS5 / AGT-008 — group membership + remote config ack
    group_id = Column(String, ForeignKey("machine_groups.id"), nullable=True, index=True)
    config_version_acked = Column(Integer, default=0, nullable=False)
    agent_cpu_percent = Column(Float, nullable=True)  # AGT-007 footprint
    agent_ram_mb = Column(Float, nullable=True)
    capability_level = Column(String, default="L0")  # L0 reject actions; L1 Lot 2 actions
    # Host owner — alert mail "to"; managers of owner go in CC (see MessagingService.resolve_recipients_for_agent)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    # Équipe responsable de l'hôte (point 3). Distincte de `group_id`, qui
    # désigne un groupe *de configuration* : ici ce sont des *personnes*.
    admin_group_id = Column(String, ForeignKey("admin_groups.id"), nullable=True, index=True)

    # --- Plan de supervision (point 6) ---
    # Version du plan propre à cet hôte. Incrémentée à chaque modification,
    # elle sert de déclencheur de push : l'agent reçoit le nouveau plan dans
    # sa réponse au heartbeat tant qu'il n'a pas accusé cette version.
    monitoring_version = Column(Integer, default=0, nullable=False)
    monitoring_version_acked = Column(Integer, default=0, nullable=False)

    heartbeats = relationship("Heartbeat", back_populates="agent", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="agent", cascade="all, delete-orphan")
    group = relationship("MachineGroup", back_populates="agents")
    #: Adresses mises en copie des alertes de cet hote, en JSON.
    #:
    #: Le destinataire principal n'est pas saisi : c'est le responsable de
    #: l'hote, ou les membres de l'equipe responsable, dont l'adresse vient
    #: de l'annuaire. La copie, elle, ne se deduit de rien -- un prestataire,
    #: un chef de projet, le metier proprietaire de l'application -- et se
    #: saisit donc a la main, hote par hote.
    alert_cc = Column(Text, default="[]")

    owner = relationship("User", foreign_keys=[owner_user_id])
    admin_group = relationship("AdminGroup", back_populates="agents")


#: Champs qu'un exploitant peut écrire via `PATCH /api/agents/{id}`.
#: Tout le reste est constaté par l'agent et refusé en écriture.
class VlanSubnet(Base):
    """Plan d'adressage fourni par l'équipe réseau : sous-réseau → VLAN.

    Une table de sous-réseaux plutôt qu'une liste d'hôtes : une machine sur
    port d'accès ne connaît pas son VLAN, mais l'agent remonte son adresse à
    chaque battement. Le VLAN se déduit donc pour tout le parc, sans saisie
    par hôte, et la déduction suit quand une machine change d'adresse.
    """

    __tablename__ = 'vlan_subnets'

    id = Column(String, primary_key=True)
    #: Forme lisible telle que l'équipe réseau l'a écrite, et identité de la
    #: ligne : `10.20.4.1-10.20.4.254` ou `10.20.4.0/24`.
    cidr = Column(String, unique=True, nullable=False, index=True)
    #: Bornes sur lesquelles se fait la comparaison. Stockées parce qu'une
    #: plage n'est pas toujours exprimable en CIDR sans la déformer :
    #: `10.20.4.1-10.20.4.254` n'est pas `10.20.4.0/24`, qui inclut l'adresse
    #: réseau et la diffusion.
    range_start = Column(String, nullable=True)
    range_end = Column(String, nullable=True)
    vlan = Column(String, nullable=False)
    label = Column(String, nullable=True)
    imported_at = Column(DateTime, default=func.now())
    imported_by = Column(String, nullable=True)
    source_file = Column(String, nullable=True)


AGENT_EDITABLE_FIELDS = frozenset(
    {
        "name",
        "location",
        "machine_type",
        "owner_user_id",
        "admin_group_id",
        "group_id",
        "capability_level",
        "vlan",
        "heartbeat_interval_seconds",
        "alert_cc",
    }
)

#: Champs déclarés par l'agent. Listés explicitement pour que le refus
#: d'écriture puisse *nommer* le champ fautif au lieu d'un « non modifiable »
#: opaque qui laisse l'utilisateur deviner.
AGENT_IMMUTABLE_FIELDS = frozenset(
    {
        "id",
        "machine_id",
        "hostname",
        "ip_address",
        "os",
        "os_version",
        "agent_version",
        "auth_key",
        "cpu_cores",
        "ram_total_gb",
        "disk_total_gb",
        "vlan_observed",
        "runtime_json",
        "run_mode",
        "run_as_user",
        "enrolled_at",
        "status",
        "last_communication",
    }
)


class AdminGroup(Base):
    """Équipe responsable d'un ensemble d'hôtes (point 3).

    À ne pas confondre avec `MachineGroup` : celui-ci regroupe des *machines*
    pour leur pousser une configuration, celui-là regroupe des *personnes*
    pour leur donner la main sur des machines.

    L'appartenance ne confère aucun droit par elle-même : elle **restreint**
    l'exercice des droits que le rôle accorde déjà (voir
    `src.permissions.require_agent_scope`). Un lecteur seul membre d'une
    équipe reste un lecteur seul.
    """

    __tablename__ = "admin_groups"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agents = relationship("Agent", back_populates="admin_group")
    members = relationship(
        "AdminGroupMember", back_populates="group", cascade="all, delete-orphan"
    )


class AdminGroupMember(Base):
    """Appartenance d'un utilisateur à une équipe d'administration."""

    __tablename__ = "admin_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_admin_group_member"),
    )

    id = Column(String, primary_key=True)
    group_id = Column(String, ForeignKey("admin_groups.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    added_at = Column(DateTime, default=func.now())
    added_by = Column(String, nullable=True)

    group = relationship("AdminGroup", back_populates="members")
    user = relationship("User")


class Heartbeat(Base):
    """Modèle de données pour un heartbeat envoyé par un agent."""
    
    __tablename__ = 'heartbeats'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    # Métriques CPU
    cpu_percent = Column(Float)
    cpu_cores = Column(Integer)
    
    # Métriques RAM
    ram_percent = Column(Float)
    ram_total_gb = Column(Float)
    ram_used_gb = Column(Float)
    ram_free_gb = Column(Float)
    
    # Métriques Disque
    disk_percent = Column(Float)
    disk_total_gb = Column(Float)
    disk_used_gb = Column(Float)
    disk_free_gb = Column(Float)
    disk_mount = Column(String, nullable=True)
    disks_json = Column(String, nullable=True)  # JSON array of partition metrics
    
    # Autres métriques
    uptime_seconds = Column(Integer)
    
    created_at = Column(DateTime, default=func.now())
    
    agent = relationship("Agent", back_populates="heartbeats")


class AlertSeverity(enum.Enum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    WARNING = "warning"  # legacy rows; serialize as major (ALR-004)


class AlertType(enum.Enum):
    AGENT_OFFLINE = "agent_offline"
    CPU_HIGH = "cpu_high"
    RAM_HIGH = "ram_high"
    DISK_HIGH = "disk_high"
    BACK_ONLINE = "back_online"
    SERVICE_DOWN = "service_down"
    FILE_ANOMALY = "file_anomaly"
    NOTIFICATION_CHANNEL_DOWN = "notification_channel_down"
    LOG_PATTERN = "log_pattern"
    RATE_LIMIT = "rate_limit"
    AGENT_FOOTPRINT = "agent_footprint"


class AlertStatus(enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class Alert(Base):
    """Modèle de données pour une alerte."""
    
    __tablename__ = 'alerts'
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    type = Column(SQLEnum(AlertType), nullable=False)
    message = Column(String, nullable=False)
    
    status = Column(SQLEnum(AlertStatus), default=AlertStatus.OPEN, nullable=False)
    
    # Valeurs au moment de l'alerte
    value = Column(Float)  # Valeur qui a déclenché l'alerte
    threshold = Column(Float)  # Seuil qui a été dépassé
    mount = Column(String, nullable=True)  # Mount point for per-partition disk alerts
    # Sujet précis de l'alerte quand le type en distingue plusieurs par hôte :
    # nom de service, chemin de fichier. Sans ce discriminant, une seule
    # alerte « service arrêté » pouvait exister par machine — le deuxième
    # service tombé était silencieusement absorbé par la déduplication.
    target = Column(String, nullable=True, index=True)
    
    started_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)  # User ID
    acknowledged_comment = Column(String, nullable=True)

    # --- Workflow interne : validation, prise en charge, résolution (point 9)
    #: Verdict de la validation : l'alerte décrit-elle un incident réel ?
    #: `false_positive` compte autant que `real` — une vérification qui crie
    #: pour rien doit se voir, sinon on la corrige jamais et les opérateurs
    #: apprennent à ignorer ses alertes.
    verdict = Column(String, nullable=True)  # real | false_positive
    #: Qui a la charge de l'alerte. Une alerte validée mais non attribuée
    #: n'appartient à personne, et c'est ainsi qu'un incident reste ouvert
    #: pendant que chacun suppose qu'un autre s'en occupe.
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)
    assigned_by = Column(String, nullable=True)
    #: Distinct de `acknowledged_by` : la résolution écrasait jusqu'ici le nom
    #: de celui qui avait validé, si bien qu'une alerte validée par l'un et
    #: résolue par l'autre n'en gardait qu'un seul — le mauvais.
    resolved_by = Column(String, nullable=True)

    # --- Relance périodique tant que l'alerte reste ouverte
    #: Intervalle de relance propre à cette alerte, en heures. `None` : on suit
    #: le réglage du parc. `0` : aucune relance, pour une alerte connue dont on
    #: attend une intervention planifiée et qu'il est inutile de rappeler.
    #:
    #: Le réglage est porté par l'alerte plutôt que par le type de
    #: vérification : c'est en la traitant qu'on sait si elle mérite un rappel
    #: dans une heure ou plus du tout, et ce jugement ne vaut pas pour toutes
    #: les alertes du même type.
    reminder_hours = Column(Float, nullable=True)
    #: Dernier rappel émis. Sert de point de départ au décompte suivant : sans
    #: lui, le délai se recompterait depuis l'ouverture et toutes les relances
    #: partiraient d'un coup au premier passage du planificateur.
    last_reminder_at = Column(DateTime, nullable=True)
    #: Nombre de rappels déjà émis, affiché à l'opérateur. Une alerte relancée
    #: six fois ne se lit pas comme une alerte relancée une fois.
    reminder_count = Column(Integer, default=0)

    #: Chargé de l'alerte, pour afficher un nom plutôt qu'un identifiant.
    assignee = relationship("User", foreign_keys=[assigned_to])
    
    archived_at = Column(DateTime, nullable=True)
    mail_status = Column(String, nullable=True)  # pending|sent|failed|skipped
    webhook_status = Column(String, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    agent = relationship("Agent", back_populates="alerts")
    events = relationship("AlertEvent", back_populates="alert", cascade="all, delete-orphan")


class GlobalSettings(Base):
    """Modèle de données pour les paramètres globaux de seuils."""

    __tablename__ = 'global_settings'

    id = Column(String, primary_key=True, default='default')
    cpu_warning_threshold = Column(Float, default=80)
    cpu_critical_threshold = Column(Float, default=90)
    ram_warning_threshold = Column(Float, default=80)
    ram_critical_threshold = Column(Float, default=90)
    disk_warning_threshold = Column(Float, default=85)
    disk_critical_threshold = Column(Float, default=95)
    # JSON list: [{"mount":"/u01","warning":80,"critical":90}, ...] — per-partition ceilings
    disk_mount_rules = Column(Text, default="[]")
    threshold_duration_seconds = Column(Integer, default=300)  # ALR-001: no alert on spike
    escalate_after_minutes = Column(Integer, default=15)  # ALR-006
    agent_cpu_max_percent = Column(Float, default=2.0)  # AGT-007
    agent_ram_max_mb = Column(Float, default=300.0)  # AGT-007
    #: Cadence de battement par défaut pour tout le parc, en secondes.
    #: Doit rester nettement sous le seuil de bascule hors ligne du serveur
    #: (`heartbeat_timeout_seconds`) : une cadence plus lente que le
    #: seuil ferait basculer tous les hôtes en permanence, sans qu'aucun ne
    #: soit en panne.
    heartbeat_interval_seconds = Column(Integer, default=30)
    #: Délai de relance par courriel d'une alerte restée ouverte, en heures.
    #: `0` désactive la relance pour tout le parc.
    alert_reminder_hours = Column(Float, default=12.0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MessagingConfig(Base):
    """Modèle de données pour la configuration des notifications via API de messagerie CBC."""

    __tablename__ = 'messaging_config'

    id = Column(String, primary_key=True, default='default')
    recipients = Column(String, default='[]')  # JSON array of recipient identifiers
    api_endpoint = Column(String)  # URL de l'API de messagerie interne CBC
    api_key = Column(String)  # Clé d'authentification pour l'API CBC
    api_timeout = Column(Integer, default=30)  # Timeout en secondes
    enabled = Column(Boolean, default=True)
    webhook_url = Column(String, nullable=True)
    webhook_secret = Column(String, nullable=True)
    webhook_enabled = Column(Boolean, default=False)

    # --- Serveur SMTP interne -------------------------------------------
    #: Second canal de courriel, indépendant de l'API Mail CBC. Les deux
    #: coexistent : un relais SMTP interne reste joignable quand l'API est en
    #: panne, et inversement.
    smtp_enabled = Column(Boolean, default=False)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, default=25)
    smtp_auth = Column(Boolean, default=False)
    smtp_username = Column(String, nullable=True)
    #: Stocké tel quel, comme `webhook_secret`, et **jamais** rendu par l'API :
    #: une clé qui repart vers le navigateur finit dans un cache, un journal
    #: de proxy ou une capture d'écran.
    smtp_password = Column(String, nullable=True)
    #: none | starttls | ssl
    smtp_encryption = Column(String, default="none")
    smtp_from = Column(String, nullable=True)
    smtp_from_name = Column(String, nullable=True)
    #: Vérifier le certificat du relais lors du STARTTLS.
    #:
    #: Un relais interne présente souvent un certificat auto-signé : la
    #: vérification échoue alors et aucune alerte ne part. Le choix est
    #: explicite plutôt que silencieux — désactiver la vérification protège
    #: encore le mot de passe du regard passif, mais plus d'un interlocuteur
    #: qui se ferait passer pour le relais.
    smtp_verify_cert = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RetentionConfig(Base):
    """Modèle de données pour la configuration de rétention des données."""

    __tablename__ = 'retention_config'

    id = Column(String, primary_key=True, default='default')
    alerts_days = Column(Integer, default=30)
    heartbeats_days = Column(Integer, default=7)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class EnrollmentToken(Base):
    """Modèle de données pour les tokens d'enrôlement des agents."""

    __tablename__ = 'enrollment_tokens'

    id = Column(String, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    status = Column(String, default='active')  # active, expired, consumed
    created_by = Column(String)  # User who created the token


class NotificationChannelStatus(Base):
    """Modèle de données pour le statut du canal de notification."""

    __tablename__ = 'notification_channel_status'

    id = Column(String, primary_key=True, default='default')
    status = Column(String, default='unknown')  # operational, degraded, error, unknown
    last_check = Column(DateTime, default=func.now())
    last_success = Column(DateTime, nullable=True)
    last_error = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ServiceMonitoring(Base):
    """Modèle de données pour la supervision des services système."""

    __tablename__ = 'service_monitoring'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    service_name = Column(String, nullable=False, index=True)
    status = Column(String, default='unknown')  # running, stopped, unknown
    last_check = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class FileMonitoring(Base):
    """Modèle de données pour la supervision des fichiers."""

    __tablename__ = 'file_monitoring'

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False, index=True)
    file_path = Column(String, nullable=False, index=True)
    exists = Column(Boolean, default=False)
    size_bytes = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    last_check = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class AvailabilityPolicy(Base):
    """Modèle de données pour la politique de disponibilité (fenêtres horaires)."""

    __tablename__ = 'availability_policies'

    id = Column(String, primary_key=True, default='default')  # 'default' ou agent_id
    agent_id = Column(String, ForeignKey('agents.id'), nullable=True, index=True)  # Null pour politique globale
    
    # Configuration des fenêtres horaires par jour (JSON)
    # Format: {"monday": [{"start": "08:00", "end": "12:00"}, {"start": "14:00", "end": "18:00"}], ...}
    time_windows = Column(String, default='{}')
    
    # Seuil offline en secondes (remplace le seuil par défaut si défini)
    offline_threshold_seconds = Column(Integer, nullable=True)
    
    # Activer/désactiver la vérification des fenêtres horaires
    time_windows_enabled = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class ServiceState(enum.Enum):
    """État attendu d'un service supervisé.

    Les deux sens comptent : on veut alerter quand un service critique
    s'arrête, mais aussi quand un service qui devrait rester à l'arrêt se met
    à tourner (service de test rallumé en production, par exemple).
    """

    RUNNING = "running"
    STOPPED = "stopped"


class FileCondition(enum.Enum):
    """Condition attendue sur un fichier supervisé.

    `MUST_EXIST` couvre le cas classique (un journal, un verrou applicatif
    qui doit être présent). `MUST_NOT_EXIST` couvre l'inverse, qui n'existait
    nulle part : un fichier sentinelle dont l'apparition signale un incident
    (drapeau d'erreur, fichier de blocage, cœur applicatif).
    """

    MUST_EXIST = "must_exist"
    MUST_NOT_EXIST = "must_not_exist"


class MonitoredService(Base):
    """Service à surveiller sur un hôte donné (point 6).

    Remplace `ServiceMonitoringConfig`, qui n'a jamais été écrit par personne :
    les endpoints de configuration se contentaient de renvoyer la requête en
    écho, et le moteur d'alerte comparait à une liste codée en dur et vide.
    """

    __tablename__ = "monitored_services"
    __table_args__ = (
        UniqueConstraint("agent_id", "service_name", name="uq_monitored_service"),
    )

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    service_name = Column(String, nullable=False, index=True)
    expected_state = Column(SQLEnum(ServiceState), default=ServiceState.RUNNING, nullable=False)
    severity = Column(SQLEnum(AlertSeverity), default=AlertSeverity.MAJOR, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class MonitoredFile(Base):
    """Fichier à surveiller sur un hôte donné (point 6)."""

    __tablename__ = "monitored_files"
    __table_args__ = (UniqueConstraint("agent_id", "path", name="uq_monitored_file"),)

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    path = Column(String, nullable=False, index=True)
    condition = Column(SQLEnum(FileCondition), default=FileCondition.MUST_EXIST, nullable=False)
    severity = Column(SQLEnum(AlertSeverity), default=AlertSeverity.MAJOR, nullable=False)
    #: Plafond de taille facultatif, en Mo. None = pas de contrôle de taille.
    max_size_mb = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class MaintenanceWindow(Base):
    """ALR-007 — suppress alerts per host (distinct from availability windows)."""

    __tablename__ = "maintenance_windows"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True, index=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=False, index=True)
    reason = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    agent = relationship("Agent")


class AlertEvent(Base):
    """ALR-005 timeline: opened / ack / resolved / notified / suppressed / escalated."""

    __tablename__ = "alert_events"

    id = Column(String, primary_key=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True, index=True)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    alert = relationship("Alert", back_populates="events")


class MachineGroup(Base):
    """AGT-008 — config groups for remote versioned push."""

    __tablename__ = "machine_groups"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    current_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agents = relationship("Agent", back_populates="group")
    revisions = relationship(
        "ConfigRevision", back_populates="group", cascade="all, delete-orphan"
    )


class ConfigRevision(Base):
    """Immutable config version for a machine group (publish + rollback = new version)."""

    __tablename__ = "config_revisions"

    id = Column(String, primary_key=True)
    group_id = Column(String, ForeignKey("machine_groups.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    payload = Column(String, nullable=False, default="{}")  # JSON object merged into agent config
    note = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    group = relationship("MachineGroup", back_populates="revisions")


class CoverageOverlap(Base):
    """AGT-014 — legacy PowerShell check still running alongside an agent plugin."""

    __tablename__ = "coverage_overlaps"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    check_id = Column(String, nullable=False, index=True)  # DES-004 row e.g. PS-001
    plugin = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    detected_at = Column(DateTime, default=func.now())
    cleared_at = Column(DateTime, nullable=True)

    agent = relationship("Agent")


class CustomDashboard(Base):
    """DSH-003 — user-defined widget grids, optionally shareable."""

    __tablename__ = "custom_dashboards"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    widgets = Column(String, default="[]")  # JSON list of widget defs
    shared = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ReportSchedule(Base):
    """DSH-007 — scheduled or on-demand fleet reports."""

    __tablename__ = "report_schedules"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    format = Column(String, default="csv")  # csv | pdf
    cron = Column(String, default="0 7 * * *")
    enabled = Column(Boolean, default=True)
    recipients = Column(String, default="[]")
    created_by = Column(String, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class NetworkDevice(Base):
    """AGT-029 — SNMP/ICMP perimeter gear (not agent hosts)."""

    __tablename__ = "network_devices"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    host = Column(String, nullable=False)
    snmp_community = Column(String, default="public")
    snmp_version = Column(String, default="2c")
    enabled = Column(Boolean, default=True)
    icmp_status = Column(String, default="unknown")
    snmp_status = Column(String, default="unknown")
    sys_descr = Column(String, nullable=True)
    last_rtt_ms = Column(Float, nullable=True)
    last_check = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ExternalConnector(Base):
    """PLT-004 — external connectors (Docker host metrics, …)."""

    __tablename__ = "external_connectors"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # docker_host
    endpoint = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    status = Column(String, default="unknown")
    last_payload = Column(String, nullable=True)
    last_check = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CoverageCheck(Base):
    """DES-004 / AGT-013 — PowerShell check → plugin extinction tracking."""

    __tablename__ = "coverage_checks"

    id = Column(String, primary_key=True)  # PS-001 …
    description = Column(String, nullable=False)
    plugin = Column(String, nullable=False)
    legacy_script = Column(String, nullable=True)
    hosts = Column(String, nullable=True)
    status = Column(String, default="planned", nullable=False, index=True)
    sprint = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    decommissioned_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PilotHost(Base):
    """FS8-01 — agreed pilot fleet for UAT family 1."""

    __tablename__ = "pilot_hosts"

    id = Column(String, primary_key=True)
    hostname = Column(String, nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True, index=True)
    os = Column(String, nullable=True)
    location = Column(String, nullable=True)
    # JSON checklist: enroll, first_metrics, heartbeat_ok, alerts_visible
    checklist = Column(String, default="{}")
    status = Column(String, default="pending")  # pending | onboarded | blocked
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    agent = relationship("Agent")


class UatCase(Base):
    """FS8 UAT Part K — family checklist items with evidence."""

    __tablename__ = "uat_cases"

    id = Column(String, primary_key=True)
    family = Column(Integer, nullable=False, index=True)  # 1–5 Lot 1
    case_id = Column(String, nullable=False, unique=True, index=True)  # UAT-1.01
    title = Column(String, nullable=False)
    requirement_refs = Column(String, default="")  # comma-separated IDs
    status = Column(String, default="pending")  # pending | pass | fail | blocked | waived
    evidence = Column(String, nullable=True)
    tester = Column(String, nullable=True)
    tested_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AcceptanceSignOff(Base):
    """FS8-06 — Lot 1 M4 sign-off records."""

    __tablename__ = "acceptance_signoffs"

    id = Column(String, primary_key=True)
    role = Column(String, nullable=False)  # cbc_ops | tech_lead | sponsor
    name = Column(String, nullable=False)
    decision = Column(String, nullable=False)  # approved | rejected | conditional
    comment = Column(String, nullable=True)
    signed_at = Column(DateTime, default=func.now())
    signed_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)


class RemoteTask(Base):
    """FS9 / Lot 2 — platform-initiated task.v1 lifecycle (SEC-005)."""

    __tablename__ = "remote_tasks"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    plugin = Column(String, nullable=False)
    input_json = Column(String, default="{}")
    dry_run = Column(Boolean, default=True)
    status = Column(String, default="pending_approval", index=True)
    issued_by = Column(String, default="user")
    requested_by = Column(String, nullable=True)
    approval_ref = Column(String, nullable=True, index=True)
    signature = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    result_json = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)
    audit_trail = Column(String, default="[]")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    dispatched_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    agent = relationship("Agent")


class ActionApproval(Base):
    """FS9 — human approval queue for high-impact tasks."""

    __tablename__ = "action_approvals"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("remote_tasks.id"), nullable=False, index=True)
    status = Column(String, default="pending")
    requested_by = Column(String, nullable=True)
    decided_by = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    decided_at = Column(DateTime, nullable=True)

    task = relationship("RemoteTask")


class MailTemplate(Base):
    """HTML mail templates — global or per-agent override (kind + event_key)."""

    __tablename__ = "mail_templates"
    __table_args__ = (
        UniqueConstraint("kind", "event_key", "agent_id", name="uq_mail_template_kind_event_agent"),
    )

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False, index=True)  # alert | task | system
    event_key = Column(String, nullable=False, index=True)  # cpu_high | service.manage:succeeded | …
    agent_id = Column(String, nullable=False, default="", index=True)  # "" = global default
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """Piste d'audit persistée (COBAC / conformité bancaire).

    Les évènements d'audit n'étaient écrits que dans un fichier de log, sans
    table ni endpoint de lecture. L'écran Audit fabriquait donc ses lignes à
    partir des alertes et des utilisateurs, avec une adresse IP codée en dur,
    et proposait ce résultat à l'export réglementaire. Une piste d'audit doit
    être persistée, requêtable et exportable telle qu'elle a été écrite.
    """

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    # Horodatage serveur : jamais fourni par le client.
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    # Auteur de l'action. Conservé sous forme d'identifiant et de libellé :
    # la trace doit rester lisible même si le compte est supprimé ensuite.
    user_id = Column(String, nullable=True, index=True)
    username = Column(String, nullable=True)
    # Adresse réellement observée sur la requête, pas une valeur d'affichage.
    ip_address = Column(String, nullable=True)
    target = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="success", index=True)
    details = Column(Text, nullable=True)


class LdapRoleMapping(Base):
    """Attribution de rôle Sentinel à une identité d'annuaire.

    Portée applicative : la correspondance vit dans cette base, pas dans
    l'annuaire. CBC n'a donc **aucun groupe à créer côté Active Directory**
    et le compte de service reste en lecture seule — ce qui est le mode
    d'accès convenu.

    Deux granularités, volontairement :

    * `group` — un DN de groupe AD. C'est le mode normal : les arrivées et
      départs suivent l'annuaire sans intervention.
    * `user`  — un identifiant de connexion (sAMAccountName). Utile pour
      amorcer un administrateur avant qu'un groupe dédié n'existe, ou pour
      une exception nominative tracée.

    `priority` départage : la valeur la plus basse gagne. Sans cela, un
    utilisateur membre de plusieurs groupes mappés obtiendrait un rôle
    dépendant de l'ordre de lecture de l'annuaire.
    """

    __tablename__ = "ldap_role_mappings"
    __table_args__ = (
        UniqueConstraint("kind", "value", name="uq_ldap_role_mapping_kind_value"),
    )

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False, index=True)  # group | user
    # DN du groupe ou sAMAccountName. Comparé sans tenir compte de la casse :
    # les annuaires ne sont pas cohérents sur ce point.
    value = Column(String, nullable=False, index=True)
    role = Column(SQLEnum(UserRole), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    description = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TsdbRollupState(Base):
    """Avancement du sous-échantillonnage par niveau d'agrégat.

    VictoriaMetrics en édition open source n'a pas de sous-échantillonnage
    natif : la plateforme calcule les agrégats et les réécrit. Mémoriser la
    dernière borne traitée rend le traitement **idempotent** — sans cela, un
    redémarrage réécrirait les mêmes intervalles, et une exécution manquée
    laisserait un trou définitif dans les séries agrégées.
    """

    __tablename__ = "tsdb_rollup_state"

    tier = Column(String, primary_key=True)  # 1h | 1d
    last_bucket_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    buckets_written = Column(Integer, nullable=False, default=0)
    samples_written = Column(Integer, nullable=False, default=0)
