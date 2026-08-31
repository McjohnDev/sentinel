/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// API Response Types for Backend DTOs

export interface BackendAgent {
  id: string;
  hostname: string;
  ip_address: string;
  os: string;
  os_version?: string;
  agent_version?: string;
  status: string;
  /** Hôte mis de côté par la purge d'inventaire : ligne conservée, revient seul s'il ré-émet. */
  retired?: boolean;
  /** Agent désinstallé et désenrôlé volontairement (point 4). */
  uninstalled?: boolean;
  uninstalled_at?: string | null;
  uninstalled_by?: string | null;
  enrolled_at?: string;
  machine_id?: string;
  /** Caractéristiques matérielles constatées (point 2). */
  cpu_cores?: number | null;
  disk_total_gb_host?: number | null;
  /** Responsabilité de l'hôte (point 3). */
  owner_user_id?: string | null;
  owner_username?: string | null;
  admin_group_id?: string | null;
  admin_group_name?: string | null;
  group_id?: string | null;
  /** Exécution sur l'hôte (point 9). */
  runtime?: Record<string, unknown> | null;
  run_mode?: string | null;
  run_as_user?: string | null;
  /** Champs que l'API accepte en écriture — source de vérité côté serveur. */
  editable_fields?: string[];
  /** Nombre d'alertes actives, quand le serveur le calcule. */
  active_alerts_count?: number;
  config_version_acked?: number;
  last_communication?: string;
  last_seen_age_seconds?: number;
  cpu_percent?: number;
  ram_percent?: number;
  ram_used_gb?: number;
  ram_total_gb?: number;
  disk_percent?: number;
  disk_used_gb?: number;
  disk_total_gb?: number;
  uptime_seconds?: number;
  cpu_threshold_warning?: number;
  cpu_threshold_critical?: number;
  ram_threshold_warning?: number;
  ram_threshold_critical?: number;
  disk_threshold_warning?: number;
  disk_threshold_critical?: number;
  cpu_warning_threshold?: number;
  cpu_critical_threshold?: number;
  ram_warning_threshold?: number;
  ram_critical_threshold?: number;
  disk_warning_threshold?: number;
  disk_critical_threshold?: number;
  disk_mount_rules?: Array<{ mount: string; warning: number; critical: number }>;
  name?: string;
  location?: string;
  machine_type?: 'server' | 'workstation';
  last_heartbeat?:
    | string
    | {
        timestamp?: string;
        cpu_percent?: number;
        ram_percent?: number;
        disk_percent?: number;
        disk_used_gb?: number;
        disk_total_gb?: number;
        uptime_seconds?: number;
        disks?: Array<{
          name?: string;
          mount?: string;
          letter?: string | null;
          label?: string | null;
          percent?: number;
          total_gb?: number;
          used_gb?: number;
          free_gb?: number;
          fstype?: string;
          alert?: boolean;
        }>;
      };
  disks?: Array<{
    name?: string;
    mount?: string;
    letter?: string | null;
    label?: string | null;
    percent?: number;
    total_gb?: number;
    used_gb?: number;
    alert?: boolean;
  }>;
}

export interface BackendAlert {
  id: string;
  agent_id: string;
  agent_name?: string;
  type: string;
  severity: string;
  status: string;
  message: string;
  created_at: string;
  started_at?: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  comment?: string;
  mail_status?: string;
  webhook_status?: string;
}

export interface BackendUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface BackendHeartbeat {
  id: string;
  agent_id: string;
  timestamp: string;
  cpu_usage: number;
  ram_usage: number;
  disk_usage: number;
  uptime_seconds: number;
}

export interface BackendGlobalSettings {
  id: string;
  cpu_warning_threshold: number;
  cpu_critical_threshold: number;
  ram_warning_threshold: number;
  ram_critical_threshold: number;
  disk_warning_threshold: number;
  disk_critical_threshold: number;
  disk_mount_rules?: Array<{ mount: string; warning: number; critical: number }> | string;
  threshold_duration_seconds?: number;
  escalate_after_minutes?: number;
  duration_seconds?: number;
  updated_at: string;
}

export interface BackendMessagingConfig {
  id: string;
  recipients: string[];
  api_endpoint: string;
  api_timeout: number;
  enabled: boolean;
  updated_at: string;
}

export interface BackendNotificationChannelStatus {
  status: 'operational' | 'degraded' | 'error' | 'unknown' | 'disabled';
  configured: boolean;
  enabled: boolean;
  last_check: string;
  error?: string;
}

export interface BackendRetentionConfig {
  id: string;
  alerts_days: number;
  heartbeats_days: number;
  updated_at: string;
}

export interface BackendEnrollmentToken {
  id: string;
  token: string;
  created_at: string;
  expires_at: string;
  status: string;
  created_by: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}
