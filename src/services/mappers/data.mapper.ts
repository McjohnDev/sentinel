/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import {
  Agent,
  Alert,
  User,
  Role,
  AgentStatus,
  AlertSeverity,
  AlertType,
  AlertStatus,
  OperatingSystem,
  AgentMetrics,
  CustomThresholds,
  GlobalThresholds,
  DataRetentionConfig,
  EnrollmentToken,
} from '../../types';
import {
  BackendAgent,
  BackendAlert,
  BackendUser,
  BackendHeartbeat,
  BackendGlobalSettings,
  BackendRetentionConfig,
  BackendEnrollmentToken,
} from '../types/api.types';

export class DataMapper {
  // Role Mapping
  static mapBackendRole(backendRole: string): Role {
    const roleMap: Record<string, Role> = {
      admin: 'Admin',
      operator: 'Operator',
      read_only: 'ReadOnly',
      security: 'Security',
    };
    return roleMap[backendRole.toLowerCase()] || 'ReadOnly';
  }

  static mapFrontendRole(frontendRole: Role): string {
    const roleMap: Record<Role, string> = {
      Admin: 'admin',
      Operator: 'operator',
      ReadOnly: 'read_only',
      Security: 'security',
    };
    return roleMap[frontendRole];
  }

  // Agent Status Mapping
  static mapBackendAgentStatus(backendStatus: string): AgentStatus {
    const statusMap: Record<string, AgentStatus> = {
      offline: 'offline',
      active: 'online',
      revoked: 'revoked',
      deleted: 'offline',
      uninstalled: 'uninstalled',
    };
    return statusMap[backendStatus.toLowerCase()] || 'offline';
  }

  static mapFrontendAgentStatus(frontendStatus: AgentStatus): string {
    const statusMap: Record<AgentStatus, string> = {
      online: 'active',
      offline: 'deleted',
      obsolete: 'active',
      revoked: 'revoked',
      uninstalled: 'uninstalled',
    };
    return statusMap[frontendStatus];
  }

  // Alert Severity Mapping
  static mapBackendAlertSeverity(backendSeverity: string): AlertSeverity {
    const severityMap: Record<string, AlertSeverity> = {
      critical: 'critical',
      major: 'major',
      warning: 'major',
      minor: 'minor',
      info: 'info',
    };
    return severityMap[backendSeverity.toLowerCase()] || 'info';
  }

  static mapFrontendAlertSeverity(frontendSeverity: AlertSeverity): string {
    const severityMap: Record<AlertSeverity, string> = {
      critical: 'CRITICAL',
      major: 'MAJOR',
      warning: 'MAJOR',
      minor: 'MINOR',
      info: 'INFO',
    };
    return severityMap[frontendSeverity];
  }

  // Alert Type Mapping
  static mapBackendAlertType(backendType: string): AlertType {
    const typeMap: Record<string, AlertType> = {
      agent_offline: 'offline',
      cpu_high: 'cpu',
      ram_high: 'ram',
      disk_high: 'disk',
      back_online: 'offline',
      log_pattern: 'log',
      rate_limit: 'log',
    };
    return typeMap[backendType.toLowerCase()] || 'other';
  }

  static mapFrontendAlertType(frontendType: AlertType): string {
    const typeMap: Record<AlertType, string> = {
      cpu: 'CPU_HIGH',
      ram: 'RAM_HIGH',
      disk: 'DISK_HIGH',
      offline: 'AGENT_OFFLINE',
      log: 'LOG_PATTERN',
      other: 'FILE_ANOMALY',
    };
    return typeMap[frontendType];
  }

  // Alert Status Mapping
  static mapBackendAlertStatus(backendStatus: string): AlertStatus {
    const statusMap: Record<string, AlertStatus> = {
      open: 'open',
      acknowledged: 'acknowledged',
      resolved: 'resolved',
      archived: 'resolved',
    };
    return statusMap[backendStatus.toLowerCase()] || 'open';
  }

  static mapFrontendAlertStatus(frontendStatus: AlertStatus): string {
    const statusMap: Record<AlertStatus, string> = {
      open: 'OPEN',
      acknowledged: 'ACKNOWLEDGED',
      resolved: 'RESOLVED',
    };
    return statusMap[frontendStatus];
  }

  // Operating System Mapping
  static mapBackendOS(backendOS: string): OperatingSystem {
    const osMap: Record<string, OperatingSystem> = {
      windows: 'windows',
      linux: 'linux',
      darwin: 'macos',
      macos: 'macos',
    };
    return osMap[backendOS.toLowerCase()] || 'linux';
  }

  static formatLastSeen(ageSeconds?: number | null, fallback?: string): string {
    if (ageSeconds == null) return fallback || '—';
    if (ageSeconds < 20) return "À l'instant";
    if (ageSeconds < 60) return `Il y a ${ageSeconds}s`;
    if (ageSeconds < 3600) return `Il y a ${Math.floor(ageSeconds / 60)} min`;
    if (ageSeconds < 86400) return `Il y a ${Math.floor(ageSeconds / 3600)} h`;
    return `Il y a ${Math.floor(ageSeconds / 86400)} j`;
  }

  // Agent Mapping
  static mapBackendAgent(backendAgent: BackendAgent): Agent {
    // `last_heartbeat` peut être une chaîne (horodatage seul) ou l'objet
    // complet selon l'endpoint. Rétrécir une fois évite huit accès non typés.
    const rawHeartbeat = backendAgent.last_heartbeat;
    const hb = typeof rawHeartbeat === 'string' ? undefined : rawHeartbeat;
    const lastSeen =
      (typeof rawHeartbeat === 'string' ? rawHeartbeat : hb?.timestamp) ||
      backendAgent.last_communication ||
      new Date().toISOString();
    const age = backendAgent.last_seen_age_seconds;
    const uptimeSeconds = backendAgent.uptime_seconds ?? hb?.uptime_seconds ?? 0;
    const days = Math.floor(uptimeSeconds / 86400);
    const hours = Math.floor((uptimeSeconds % 86400) / 3600);
    const minutes = Math.floor((uptimeSeconds % 3600) / 60);

    const diskRows = backendAgent.disks ?? hb?.disks ?? [];
    const metrics: AgentMetrics = {
      cpu: backendAgent.cpu_percent ?? hb?.cpu_percent ?? 0,
      ram: backendAgent.ram_percent ?? hb?.ram_percent ?? 0,
      ramUsedGb: backendAgent.ram_used_gb ?? 0,
      ramTotalGb: backendAgent.ram_total_gb ?? 16,
      disk: backendAgent.disk_percent ?? hb?.disk_percent ?? 0,
      diskUsedGb: backendAgent.disk_used_gb ?? hb?.disk_used_gb ?? 0,
      diskTotalGb: backendAgent.disk_total_gb ?? hb?.disk_total_gb ?? 500,
      uptime: `${days}j ${hours}h ${minutes}m`,
      cpuHistory: [],
      ramHistory: [],
      diskHistory: [],
    };

    if (diskRows.length > 0) {
      metrics.partitions = diskRows.map((d) => ({
        name: d.name || d.mount || 'disk',
        mountPoint: d.mount || '',
        letter: d.letter ?? null,
        label: d.label ?? null,
        fstype: (d as { fstype?: string }).fstype,
        totalGb: d.total_gb ?? 0,
        usedGb: d.used_gb ?? 0,
        usedPercent: d.percent ?? 0,
      }));
    }

    // Un seuil surchargé se distingue d'un seuil hérité par la présence
    // d'une valeur, pas par une valeur de repli. L'ancienne version comblait
    // chaque champ absent avec 80/90/85/95 : `customThresholds` n'était donc
    // jamais indéfini et TOUS les hôtes s'affichaient « Surcharge », y
    // compris ceux qui suivaient sagement les seuils globaux.
    const thresholdValues = {
      cpuWarning: backendAgent.cpu_warning_threshold ?? backendAgent.cpu_threshold_warning,
      cpuCritical: backendAgent.cpu_critical_threshold ?? backendAgent.cpu_threshold_critical,
      ramWarning: backendAgent.ram_warning_threshold ?? backendAgent.ram_threshold_warning,
      ramCritical: backendAgent.ram_critical_threshold ?? backendAgent.ram_threshold_critical,
      diskWarning: backendAgent.disk_warning_threshold ?? backendAgent.disk_threshold_warning,
      diskCritical: backendAgent.disk_critical_threshold ?? backendAgent.disk_threshold_critical,
    };
    const mountRules = Array.isArray(backendAgent.disk_mount_rules)
      ? backendAgent.disk_mount_rules.map((r: { mount?: string; warning?: number; critical?: number }) => ({
          mount: String(r.mount || ''),
          warning: Number(r.warning ?? 85),
          critical: Number(r.critical ?? 95),
        }))
      : [];

    const hasOverride =
      Object.values(thresholdValues).some((v) => v !== undefined && v !== null) ||
      mountRules.length > 0;

    const customThresholds: CustomThresholds | undefined = hasOverride
      ? {
          cpuWarning: thresholdValues.cpuWarning ?? 80,
          cpuCritical: thresholdValues.cpuCritical ?? 90,
          ramWarning: thresholdValues.ramWarning ?? 80,
          ramCritical: thresholdValues.ramCritical ?? 90,
          diskWarning: thresholdValues.diskWarning ?? 85,
          diskCritical: thresholdValues.diskCritical ?? 95,
          diskMountRules: mountRules,
        }
      : undefined;

    return {
      id: backendAgent.id,
      name: backendAgent.name || backendAgent.hostname,
      hostname: backendAgent.hostname,
      os: this.mapBackendOS(backendAgent.os || 'linux'),
      osVersion: backendAgent.os_version || 'Unknown',
      agentVersion: backendAgent.agent_version || 'v1.1.0',
      ipAddress: backendAgent.ip_address || '',
      status: this.mapBackendAgentStatus(backendAgent.status),
      metrics,
      // Servi par la liste quand le serveur le calcule ; sinon recalculé par
      // le contexte à partir des alertes réellement chargées. Le zéro codé
      // en dur rendait la colonne « Alertes » et son filtre inertes.
      activeAlertsCount: backendAgent.active_alerts_count ?? 0,
      lastHeartbeat: this.formatLastSeen(age, lastSeen),
      lastSeenAgeSeconds: age,
      // Date réelle d'enrôlement. Elle était remplacée par la date du jour,
      // ce qui faisait de chaque hôte un hôte enrôlé aujourd'hui.
      enrollmentDate: backendAgent.enrolled_at
        ? String(backendAgent.enrolled_at).split('T')[0]
        : '',
      location: backendAgent.location || '',
      machineType: backendAgent.machine_type,
      // Cycle de vie et responsabilité (lot A)
      retired: backendAgent.retired ?? false,
      uninstalled: backendAgent.uninstalled ?? false,
      uninstalledAt: backendAgent.uninstalled_at ?? null,
      heartbeatIntervalSeconds:
        (backendAgent as { heartbeat_interval_seconds?: number | null }).heartbeat_interval_seconds ?? null,
      vlanObserved: backendAgent.vlan_observed ?? null,
      vlan: backendAgent.vlan ?? null,
      vlanDerived: backendAgent.vlan_derived ?? null,
      vlanSubnet: backendAgent.vlan_subnet ?? null,
      vlanLabel: backendAgent.vlan_label ?? null,
      vlanEffective: backendAgent.vlan_effective ?? null,
      vlanSource: backendAgent.vlan_source ?? null,
      ownerUserId: backendAgent.owner_user_id ?? null,
      ownerUsername: backendAgent.owner_username ?? null,
      adminGroupId: backendAgent.admin_group_id ?? null,
      adminGroupName: backendAgent.admin_group_name ?? null,
      cpuCores: backendAgent.cpu_cores ?? null,
      ramTotalGb: backendAgent.ram_total_gb ?? null,
      runtime: backendAgent.runtime ?? null,
      runMode: backendAgent.run_mode ?? null,
      editableFields: backendAgent.editable_fields ?? [],
      customThresholds,
    };
  }

  // Alert Mapping
  static mapBackendAlert(backendAlert: BackendAlert): Alert {
    return {
      id: backendAlert.id,
      agentId: backendAlert.agent_id,
      agentName: backendAlert.agent_name || 'Unknown',
      type: this.mapBackendAlertType(backendAlert.type),
      severity: this.mapBackendAlertSeverity(backendAlert.severity),
      status: this.mapBackendAlertStatus(backendAlert.status),
      message: backendAlert.message,
      timestamp: backendAlert.created_at || backendAlert.started_at,
      acknowledgedBy: backendAlert.acknowledged_by,
      acknowledgedAt: backendAlert.acknowledged_at,
      comment: backendAlert.comment,
      verdict: (backendAlert as { verdict?: string }).verdict as Alert['verdict'],
      assignedTo: (backendAlert as { assigned_to?: string | null }).assigned_to ?? null,
      assignedToUsername:
        (backendAlert as { assigned_to_username?: string | null }).assigned_to_username ?? null,
      assignedAt: (backendAlert as { assigned_at?: string | null }).assigned_at ?? null,
      assignedBy: (backendAlert as { assigned_by?: string | null }).assigned_by ?? null,
      resolvedBy: (backendAlert as { resolved_by?: string | null }).resolved_by ?? null,
      mailStatus: backendAlert.mail_status,
      webhookStatus: backendAlert.webhook_status,
    };
  }

  // User Mapping
  static mapBackendUser(backendUser: BackendUser): User {
    return {
      id: backendUser.id,
      name: backendUser.username,
      email: backendUser.email,
      role: this.mapBackendRole(backendUser.role),
      createdAt: backendUser.created_at.split('T')[0],
      status: backendUser.is_active ? 'active' : 'inactive',
    };
  }

  // Global Settings Mapping
  static mapBackendGlobalSettings(backendSettings: BackendGlobalSettings): GlobalThresholds {
    let rules: GlobalThresholds['diskMountRules'] = [];
    const raw = backendSettings.disk_mount_rules;
    if (Array.isArray(raw)) {
      rules = raw.map((r) => ({
        mount: String(r.mount || ''),
        warning: Number(r.warning ?? 85),
        critical: Number(r.critical ?? 95),
      }));
    } else if (typeof raw === 'string' && raw.trim()) {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          rules = parsed.map((r: { mount?: string; warning?: number; critical?: number }) => ({
            mount: String(r.mount || ''),
            warning: Number(r.warning ?? 85),
            critical: Number(r.critical ?? 95),
          }));
        }
      } catch {
        rules = [];
      }
    }
    return {
      cpuWarning: backendSettings.cpu_warning_threshold,
      cpuCritical: backendSettings.cpu_critical_threshold,
      ramWarning: backendSettings.ram_warning_threshold,
      ramCritical: backendSettings.ram_critical_threshold,
      diskWarning: backendSettings.disk_warning_threshold,
      diskCritical: backendSettings.disk_critical_threshold,
      durationSeconds: backendSettings.threshold_duration_seconds ?? backendSettings.duration_seconds ?? 300,
      escalateAfterMinutes: backendSettings.escalate_after_minutes ?? 15,
    // Valeur réelle du serveur ; 30 s n'est qu'un repli si la plateforme est
    // d'une version antérieure au réglage.
    heartbeatIntervalSeconds:
      (backendSettings as { heartbeat_interval_seconds?: number }).heartbeat_interval_seconds ?? 30,
      diskMountRules: rules,
    };
  }

  // Retention Config Mapping
  static mapBackendRetentionConfig(backendConfig: BackendRetentionConfig): DataRetentionConfig {
    return {
      alertsDays: backendConfig.alerts_days,
      heartbeatsDays: backendConfig.heartbeats_days,
    };
  }

  // Enrollment Token Mapping
  static mapBackendEnrollmentToken(backendToken: BackendEnrollmentToken): EnrollmentToken {
    return {
      id: backendToken.id,
      token: backendToken.token,
      createdAt: backendToken.created_at,
      expiresAt: backendToken.expires_at,
      status: backendToken.status as 'active' | 'expired' | 'consumed',
      createdBy: backendToken.created_by,
    };
  }
}
