/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type Role = 'Admin' | 'Operator' | 'ReadOnly';

export type AgentStatus = 'online' | 'offline' | 'obsolete' | 'revoked';

export type OperatingSystem = 'windows' | 'linux' | 'macos';

export type AlertSeverity = 'info' | 'warning' | 'critical';

export type AlertType = 'cpu' | 'ram' | 'disk' | 'offline';

export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export interface Partition {
  name: string;
  mountPoint: string;
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
}

export interface Agent {
  id: string;
  name: string;
  hostname: string;
  os: OperatingSystem;
  osVersion: string; // Detailed OS version / distribution (e.g., "Red Hat Enterprise Linux 9.2", "Windows Server 2022")
  agentVersion: string; // CBC Agent binary version (e.g., "CBC Agent v1.0")
  ipAddress: string;
  status: AgentStatus;
  metrics: AgentMetrics;
  activeAlertsCount: number;
  lastHeartbeat: string;
  enrollmentDate: string;
  location: string; // e.g., "Douala HQ Data Center", "Bafoussam Branch"
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
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  createdAt: string;
  status: 'active' | 'inactive';
}

export interface GlobalThresholds {
  cpuWarning: number;
  cpuCritical: number;
  ramWarning: number;
  ramCritical: number;
  diskWarning: number;
  diskCritical: number;
}

export interface EmailNotificationConfig {
  recipients: string[];
  smtpHost: string;
  smtpPort: number;
  smtpSecure: boolean;
  smtpUser: string;
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
