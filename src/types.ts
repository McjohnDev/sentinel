/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Doit rester aligné sur UserRole côté serveur (server/src/models.py).
// 'Security' = profil conformité (DSH-025) : lecture complète + audit.
export type Role = 'Admin' | 'Operator' | 'ReadOnly' | 'Security';

/** Origine du compte : base locale ou annuaire d'entreprise. */
export type AuthSource = 'local' | 'ldap';

export type AgentStatus = 'online' | 'offline' | 'obsolete' | 'revoked' | 'uninstalled';

export type OperatingSystem = 'windows' | 'linux' | 'macos';

export type AlertSeverity = 'info' | 'minor' | 'major' | 'critical' | 'warning';

export type AlertType = 'cpu' | 'ram' | 'disk' | 'offline' | 'log' | 'other';

export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export interface Partition {
  name: string;
  mountPoint: string;
  letter?: string | null;
  label?: string | null;
  fstype?: string;
  totalGb: number;
  usedGb: number;
  usedPercent: number;
}

export interface AgentMetrics {
  cpu: number; // 0 - 100%
  ram: number; // 0 - 100%
  ramUsedGb: number;
  ramTotalGb: number;
  disk: number; // 0 - 100%
  diskUsedGb: number;
  diskTotalGb: number;
  uptime: string; // e.g. "45j 12h 30m"
  cpuHistory: number[];
  ramHistory: number[];
  diskHistory: number[];
  partitions?: Partition[];
}

export interface CustomThresholds {
  cpuWarning: number;
  cpuCritical: number;
  ramWarning: number;
  ramCritical: number;
  diskWarning: number;
  diskCritical: number;
  diskMountRules?: DiskMountThreshold[];
}

/** Descriptif « où et comment l'agent tourne » remonté par l'hôte (point 9). */
export interface AgentRuntime {
  executable_path?: string;
  install_dir?: string;
  working_dir?: string;
  /** Fichier de configuration réellement chargé — pas celui que la doc suppose. */
  config_path?: string | null;
  run_mode?: string;
  service_name?: string | null;
  packaging?: string;
  pid?: number;
  started_at?: string | null;
  uptime_seconds?: number | null;
  run_as_user?: string | null;
  elevated?: boolean | null;
  python_version?: string;
  frozen?: boolean;
  platform?: string;
  server_url?: string | null;
  tls_verify?: boolean | null;
  buffer_records?: number | null;
  last_error?: string | null;
  plugins?: string[];
  collected_at?: string;
}

export interface Agent {
  /** Code hexadécimal à 6 caractères attribué par la plateforme (ex. A3F09C). */
  id: string;
  /** Nom d'hôte affiché — attribué par l'exploitation, modifiable. */
  name: string;
  /** Nom machine constaté par l'agent — non modifiable. */
  hostname: string;
  os: OperatingSystem;
  osVersion: string; // Detailed OS version / distribution (e.g., "Red Hat Enterprise Linux 9.2", "Windows Server 2022")
  agentVersion: string; // CBC Agent binary version (e.g., "CBC Agent v1.0")
  ipAddress: string;
  status: AgentStatus;
  metrics: AgentMetrics;
  activeAlertsCount: number;
  lastHeartbeat: string;
  lastSeenAgeSeconds?: number;
  enrollmentDate: string;
  location: string; // e.g., "Douala HQ Data Center", "Bafoussam Branch"
  machineType?: 'server' | 'workstation';

  // --- Cycle de vie (lot A) ---
  /** Mis de côté par la purge d'inventaire ; revient seul s'il ré-émet. */
  retired?: boolean;
  /** Agent désinstallé et désenrôlé volontairement. */
  uninstalled?: boolean;
  uninstalledAt?: string | null;

  // --- Responsabilité de l'hôte (point 3) ---
  /** VLAN constaté par l'hôte — vide s'il ne peut pas le déterminer. */
  vlanObserved?: string | null;
  /** VLAN déclaré par l'exploitation — modifiable. */
  vlan?: string | null;
  ownerUserId?: string | null;
  ownerUsername?: string | null;
  adminGroupId?: string | null;
  adminGroupName?: string | null;

  // --- Caractéristiques constatées (point 2) ---
  cpuCores?: number | null;
  ramTotalGb?: number | null;

  // --- Exécution sur l'hôte (point 9) ---
  runtime?: AgentRuntime | null;
  runMode?: string | null;

  /** Champs que l'API accepte en écriture — servi par le serveur, pour que
   *  l'interface n'ait pas sa propre copie de la règle. */
  editableFields?: string[];

  /** Absent quand l'hôte suit les seuils globaux (pas de surcharge locale). */
  customThresholds?: CustomThresholds;
}

export interface Alert {
  id: string;
  agentId: string;
  agentName: string;
  type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  message: string;
  timestamp: string;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
  comment?: string;
  mailStatus?: string;
  webhookStatus?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  authSource?: AuthSource;
  lastLoginAt?: string | null;
  permissions?: string[];
  createdAt: string;
  status: 'active' | 'inactive';
}

export interface DiskMountThreshold {
  mount: string;
  warning: number;
  critical: number;
}

export interface GlobalThresholds {
  cpuWarning: number;
  cpuCritical: number;
  ramWarning: number;
  ramCritical: number;
  diskWarning: number;
  diskCritical: number;
  durationSeconds: number;
  escalateAfterMinutes: number;
  /** Per-partition ceilings; empty = use default diskWarning/diskCritical */
  diskMountRules: DiskMountThreshold[];
}

export interface MessagingNotificationConfig {
  recipients: string[];
  apiEndpoint: string;
  apiKey: string;
  apiTimeout: number;
  enabled: boolean;
  webhookUrl?: string;
  webhookSecret?: string;
  webhookEnabled?: boolean;
}

export interface ServicesMonitoringConfig {
  enabled: boolean;
  services: string[];
  interval: number;
}

export interface FilesMonitoringConfig {
  enabled: boolean;
  files: Array<{
    path: string;
    max_size_mb?: number;
  }>;
  interval: number;
}

export interface TimeWindow {
  start: string; // HH:MM format
  end: string; // HH:MM format
}

export interface AvailabilityPolicy {
  enabled: boolean;
  timeWindows: {
    [day: string]: TimeWindow[]; // day: "monday", "tuesday", etc.
  };
  offlineThresholdSeconds?: number;
}

export interface DataRetentionConfig {
  alertsDays: number;
  heartbeatsDays: number;
}

export interface EnrollmentToken {
  id: string;
  token: string;
  createdAt: string;
  expiresAt: string;
  status: 'active' | 'expired' | 'consumed';
  createdBy: string;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
}

export type ViewMode =
  | 'login'
  | 'dashboard'
  | 'agents'
  | 'agent-detail'
  | 'alerts'
  | 'settings'
  | 'users'
  | 'profile';
