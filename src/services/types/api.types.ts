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
  status: string;
  last_heartbeat: string;
  cpu_threshold_warning?: number;
  cpu_threshold_critical?: number;
  ram_threshold_warning?: number;
  ram_threshold_critical?: number;
  disk_threshold_warning?: number;
  disk_threshold_critical?: number;
  name?: string;
  location?: string;
  machine_type: 'server' | 'workstation'; // V1.1
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
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  comment?: string;
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
