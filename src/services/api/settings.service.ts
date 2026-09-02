/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { GlobalThresholds, DataRetentionConfig, EnrollmentToken } from '../../types';

export const settingsService = {
  async getGlobalThresholds(): Promise<GlobalThresholds> {
    const response = await axiosInstance.get('/settings/thresholds');
    const d = response.data;
    const rulesRaw = d.diskMountRules ?? d.disk_mount_rules ?? [];
    return {
      cpuWarning: d.cpuWarning ?? d.cpu_warning ?? 80,
      cpuCritical: d.cpuCritical ?? d.cpu_critical ?? 90,
      ramWarning: d.ramWarning ?? d.ram_warning ?? 80,
      ramCritical: d.ramCritical ?? d.ram_critical ?? 90,
      diskWarning: d.diskWarning ?? d.disk_warning ?? 85,
      diskCritical: d.diskCritical ?? d.disk_critical ?? 95,
      durationSeconds: d.durationSeconds ?? d.duration_seconds ?? 300,
      escalateAfterMinutes: d.escalateAfterMinutes ?? d.escalate_after_minutes ?? 15,
      diskMountRules: Array.isArray(rulesRaw)
        ? rulesRaw.map((r: { mount?: string; warning?: number; critical?: number }) => ({
            mount: String(r.mount || ''),
            warning: Number(r.warning ?? 85),
            critical: Number(r.critical ?? 95),
          }))
        : [],
    };
  },

  async updateGlobalThresholds(thresholds: GlobalThresholds): Promise<void> {
    await axiosInstance.put('/settings/thresholds', {
      cpu_warning: thresholds.cpuWarning,
      cpu_critical: thresholds.cpuCritical,
      ram_warning: thresholds.ramWarning,
      ram_critical: thresholds.ramCritical,
      disk_warning: thresholds.diskWarning,
      disk_critical: thresholds.diskCritical,
      duration_seconds: thresholds.durationSeconds,
      escalate_after_minutes: thresholds.escalateAfterMinutes,
      disk_mount_rules: (thresholds.diskMountRules || [])
        .filter((r) => r.mount?.trim())
        .map((r) => ({
          mount: r.mount.trim(),
          warning: r.warning,
          critical: r.critical,
        })),
    });
  },


  async updateMessagingConfig(config: {
    recipients: string[];
    apiEndpoint: string;
    apiKey: string;
    apiTimeout: number;
    enabled: boolean;
    webhookUrl?: string;
    webhookSecret?: string;
    webhookEnabled?: boolean;
  }): Promise<void> {
    await axiosInstance.put('/settings/messaging', {
      recipients: config.recipients,
      api_endpoint: config.apiEndpoint,
      api_key: config.apiKey,
      api_timeout: config.apiTimeout,
      enabled: config.enabled,
      webhook_url: config.webhookUrl || '',
      webhook_secret: config.webhookSecret || '',
      webhook_enabled: Boolean(config.webhookEnabled),
    });
  },

  async sendTestMail(payload?: { to?: string; subject?: string; body?: string; cc?: string[] }): Promise<{
    status: string;
    ok?: boolean;
    to?: string[];
    endpoint?: string;
    error?: string;
  }> {
    const response = await axiosInstance.post('/settings/messaging/test', payload || {});
    return response.data;
  },

  async getRetentionConfig(): Promise<DataRetentionConfig> {
    const response = await axiosInstance.get('/settings/retention');
    return response.data;
  },

  async updateRetentionConfig(config: DataRetentionConfig): Promise<void> {
    await axiosInstance.put('/settings/retention', config);
  },

  /** Configuration LDAP (aucun secret n'est renvoyé par le serveur). */
  async getLdapSettings(): Promise<{
    enabled: boolean;
    library_available: boolean;
    operational: boolean;
    server_uri: string | null;
    user_search_base: string | null;
    user_filter: string;
    use_ssl: boolean;
    start_tls: boolean;
    tls_verify: boolean;
    default_role: string;
    role_mapping: Record<string, string>;
    bind_dn_configured: boolean;
  }> {
    const response = await axiosInstance.get('/settings/ldap');
    return response.data;
  },

  /** Teste la joignabilité de l'annuaire et le bind du compte de service. */
  async testLdap(): Promise<{ ok: boolean; stage: string; detail: string }> {
    const response = await axiosInstance.post('/settings/ldap/test');
    return response.data;
  },

  /** Résout un compte et montre le rôle qui lui serait attribué. */
  async probeLdapUser(username: string): Promise<{
    found: boolean;
    detail?: string;
    username?: string;
    email?: string;
    display_name?: string;
    dn?: string;
    groups?: string[];
    resolved_role?: string;
  }> {
    const response = await axiosInstance.post('/settings/ldap/probe-user', { username });
    return response.data;
  },

  /**
   * Correspondances rôle <- identité d'annuaire, propres à l'application.
   *
   * Elles vivent dans la base de la plateforme : aucun groupe n'a à être créé
   * dans Active Directory et le compte de service reste en lecture seule.
   */
  async listLdapRoleMappings(): Promise<{
    data: Array<{
      id: string;
      kind: 'group' | 'user';
      value: string;
      role: string;
      priority: number;
      description: string | null;
      enabled: boolean;
      created_by: string | null;
      created_at: string;
    }>;
  }> {
    const response = await axiosInstance.get('/settings/ldap/role-mappings');
    return response.data;
  },

  async createLdapRoleMapping(body: {
    kind: 'group' | 'user';
    value: string;
    role: string;
    priority?: number;
    description?: string;
  }): Promise<void> {
    await axiosInstance.post('/settings/ldap/role-mappings', body);
  },

  async deleteLdapRoleMapping(id: string): Promise<void> {
    await axiosInstance.delete(`/settings/ldap/role-mappings/${id}`);
  },

  /** Rôle qu'obtiendrait un compte, correspondances appliquées. */
  async previewLdapRole(username: string): Promise<{
    found: boolean;
    detail?: string;
    username?: string;
    display_name?: string;
    dn?: string;
    groups?: string[];
    resolved_role?: string;
    attributes?: Record<string, string>;
  }> {
    const response = await axiosInstance.post('/settings/ldap/preview-role', { username });
    return response.data;
  },

  /** Crée un jeton d'enrôlement côté serveur. */
  async createEnrollmentToken(): Promise<any> {
    const response = await axiosInstance.post('/settings/tokens');
    return response.data;
  },

  async getEnrollmentTokens(): Promise<EnrollmentToken[]> {
    const response = await axiosInstance.get('/settings/tokens');
    return response.data;
  },

  async listMaintenance(): Promise<Array<{ id: string; agent_id?: string; starts_at: string; ends_at: string; reason: string; active: boolean }>> {
    const response = await axiosInstance.get('/maintenance');
    return response.data.data || [];
  },

  async createMaintenance(body: { agent_id?: string; starts_at: string; ends_at: string; reason: string }): Promise<void> {
    await axiosInstance.post('/maintenance', body);
  },

  async getDiscoveredPartitions(): Promise<
    Array<{
      name: string;
      mount: string;
      letter?: string | null;
      label?: string | null;
      fstype?: string;
      host_count?: number;
      hosts?: string[];
    }>
  > {
    const response = await axiosInstance.get('/settings/discovered-partitions');
    return response.data?.data || [];
  },

  async getPlatformStatus(): Promise<{
    status: string;
    checked_at?: string;
    unhealthy_count?: number;
    components?: Record<string, { status: string; error?: string }>;
    latency?: Record<string, unknown>;
  }> {
    const response = await axiosInstance.get('/platform/status');
    return response.data;
  },

  async recordPageLatency(seconds: number, path = '/'): Promise<void> {
    await axiosInstance.post('/platform/latency/page', { seconds, path });
  },
};

export interface MailTemplate {
  id: string;
  kind: string;
  event_key: string;
  agent_id: string;
  subject: string;
  body_html: string;
  description?: string | null;
  scope: 'global' | 'agent';
  updated_at?: string | null;
}

/**
 * Gabarits de courriel, un par vérification (point 8).
 *
 * Le catalogue rendu couvre toutes les vérifications connues, pas seulement
 * celles déjà personnalisées : l'exploitant doit voir ce qui *peut* être
 * réglé plutôt que de deviner les clés d'événement.
 */
export const mailTemplatesService = {
  async list(agentId?: string): Promise<MailTemplate[]> {
    const { data } = await axiosInstance.get('/settings/mail-templates', {
      params: agentId ? { agent_id: agentId } : undefined,
    });
    return data.data || [];
  },

  async save(body: {
    kind: string;
    event_key: string;
    subject: string;
    body_html: string;
    agent_id?: string;
  }): Promise<void> {
    await axiosInstance.put('/settings/mail-templates', body);
  },

  /** Revient au gabarit livré. La ligne est supprimée, pas recopiée. */
  async reset(kind: string, eventKey: string, agentId?: string): Promise<void> {
    await axiosInstance.delete('/settings/mail-templates', {
      params: { kind, event_key: eventKey, ...(agentId ? { agent_id: agentId } : {}) },
    });
  },

  /** Rend le gabarit sans rien envoyer. */
  async preview(subject: string, bodyHtml: string): Promise<{ subject: string; body_html: string }> {
    const { data } = await axiosInstance.post('/settings/mail-templates/preview', {
      subject,
      body_html: bodyHtml,
    });
    return data;
  },

  /** Essai du webhook signé — le canal qui déclenche n8n. */
  async testWebhook(): Promise<{ status: string; url: string }> {
    const { data } = await axiosInstance.post('/settings/webhook/test', {});
    return data;
  },
};

export interface SmtpConfig {
  enabled: boolean;
  host: string | null;
  port: number;
  auth: boolean;
  username: string | null;
  /** Le mot de passe n'est jamais rendu : seule sa présence l'est. */
  password_set: boolean;
  encryption: string;
  from_address: string | null;
  from_name: string | null;
}

/** Relais SMTP interne — second canal d'alerte, à côté de l'API Mail CBC. */
export const smtpService = {
  async get(): Promise<SmtpConfig> {
    const { data } = await axiosInstance.get('/settings/smtp');
    return data;
  },

  /** Omettre `password` conserve celui enregistré ; le passer vide l'efface. */
  async save(body: Partial<SmtpConfig> & { password?: string }): Promise<SmtpConfig> {
    const { data } = await axiosInstance.put('/settings/smtp', body);
    return data;
  },

  async test(to?: string): Promise<{ status: string; to: string }> {
    const { data } = await axiosInstance.post('/settings/smtp/test', to ? { to } : {});
    return data;
  },
};
