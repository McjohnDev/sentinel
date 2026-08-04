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
  EmailNotificationConfig,
  DataRetentionConfig,
  EnrollmentToken,
} from '../../types';
import {
  BackendAgent,
  BackendAlert,
  BackendUser,
  BackendHeartbeat,
  BackendGlobalSettings,
  BackendEmailConfig,
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
    };
    return roleMap[backendRole.toLowerCase()] || 'ReadOnly';
  }

  static mapFrontendRole(frontendRole: Role): string {
    const roleMap: Record<Role, string> = {
      Admin: 'admin',
      Operator: 'operator',
      ReadOnly: 'read_only',
    };
    return roleMap[frontendRole];
  }

  // Agent Status Mapping
  static mapBackendAgentStatus(backendStatus: string): AgentStatus {
    const statusMap: Record<string, AgentStatus> = {
      active: 'online',
      revoked: 'revoked',
      deleted: 'offline',
    };
    return statusMap[backendStatus.toLowerCase()] || 'offline';
  }

  static mapFrontendAgentStatus(frontendStatus: AgentStatus): string {
    const statusMap: Record<AgentStatus, string> = {
      online: 'active',
      offline: 'deleted',
      obsolete: 'active',
      revoked: 'revoked',
    };
    return statusMap[frontendStatus];
  }

  // Alert Severity Mapping
  static mapBackendAlertSeverity(backendSeverity: string): AlertSeverity {
    const severityMap: Record<string, AlertSeverity> = {
      critical: 'critical',
      warning: 'warning',
      info: 'info',
    };
    return severityMap[backendSeverity.toLowerCase()] || 'info';
  }

  static mapFrontendAlertSeverity(frontendSeverity: AlertSeverity): string {
    const severityMap: Record<AlertSeverity, string> = {
      critical: 'CRITICAL',
      warning: 'WARNING',
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
    };
    return typeMap[backendType.toLowerCase()] || 'offline';
  }

  static mapFrontendAlertType(frontendType: AlertType): string {
    const typeMap: Record<AlertType, string> = {
      cpu: 'CPU_HIGH',
      ram: 'RAM_HIGH',
      disk: 'DISK_HIGH',
      offline: 'AGENT_OFFLINE',
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

  // Agent Mapping
  static mapBackendAgent(backendAgent: BackendAgent): Agent {
    const metrics: AgentMetrics = {
      cpu: 0,
      ram: 0,
      ramUsedGb: 0,
      ramTotalGb: 16,
      disk: 0,
      diskUsedGb: 0,
      diskTotalGb: 500,
      uptime: '0j 0h 0m',
      cpuHistory: [],
      ramHistory: [],
      diskHistory: [],
    };

    const customThresholds: CustomThresholds = {
      cpuWarning: backendAgent.cpu_threshold_warning || 80,
      cpuCritical: backendAgent.cpu_threshold_critical || 90,
      ramWarning: backendAgent.ram_threshold_warning || 80,
      ramCritical: backendAgent.ram_threshold_critical || 90,
      diskWarning: backendAgent.disk_threshold_warning || 85,
      diskCritical: backendAgent.disk_threshold_critical || 95,
    };

    return {
      id: backendAgent.id,
      name: backendAgent.name || backendAgent.hostname,
      hostname: backendAgent.hostname,
      os: this.mapBackendOS(backendAgent.os),
      osVersion: 'Unknown',
      agentVersion: 'v1.0',
      ipAddress: backendAgent.ip_address,
      status: this.mapBackendAgentStatus(backendAgent.status),
      metrics,
      activeAlertsCount: 0,
      lastHeartbeat: backendAgent.last_heartbeat,
      enrollmentDate: new Date().toISOString().split('T')[0],
      location: backendAgent.location || 'Unknown',
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
      timestamp: backendAlert.created_at,
      acknowledgedBy: backendAlert.acknowledged_by,
      acknowledgedAt: backendAlert.acknowledged_at,
      comment: backendAlert.comment,
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
    return {
      cpuWarning: backendSettings.cpu_warning_threshold,
      cpuCritical: backendSettings.cpu_critical_threshold,
      ramWarning: backendSettings.ram_warning_threshold,
      ramCritical: backendSettings.ram_critical_threshold,
      diskWarning: backendSettings.disk_warning_threshold,
      diskCritical: backendSettings.disk_critical_threshold,
    };
  }

  // Email Config Mapping
  static mapBackendEmailConfig(backendConfig: BackendEmailConfig): EmailNotificationConfig {
    return {
      recipients: JSON.parse(backendConfig.recipients || '[]'),
      smtpHost: backendConfig.smtp_host,
      smtpPort: backendConfig.smtp_port,
      smtpSecure: backendConfig.smtp_secure,
      smtpUser: backendConfig.smtp_user,
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
