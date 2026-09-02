/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { Agent, CustomThresholds } from '../../types';
import { DataMapper } from '../mappers/data.mapper';
import { BackendAgent } from '../types/api.types';

export interface AgentsListParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
}

/** Champs qu'un exploitant peut poser. Volontairement restreint : tout le
 *  reste est constaté par l'agent et refusé en écriture par le serveur. */
export interface AgentPatch {
  name?: string;
  location?: string;
  machine_type?: 'server' | 'workstation';
  vlan?: string | null;
  /** Cadence propre a l'hote. null = suit la cadence du parc. */
  heartbeat_interval_seconds?: number | null;
  owner_user_id?: string | null;
  admin_group_id?: string | null;
  group_id?: string | null;
  /** Adresses en copie des alertes de cet hote. Le destinataire principal
   *  n'est pas saisi : il vient du responsable et de l'equipe responsable. */
  alert_cc?: string[];
}

export interface PatchAgentResponse {
  message: string;
  id: string;
  changes: Record<string, { avant: unknown; 'après': unknown }>;
}

export interface AdminGroupMember {
  user_id: string;
  username: string;
  email: string;
  role: string;
  added_at?: string;
}

export interface AdminGroup {
  id: string;
  name: string;
  description?: string | null;
  members: AdminGroupMember[];
  agent_count: number;
}

/** Plan de supervision d'un hôte (point 6). */
export type ServiceState = 'running' | 'stopped';
export type FileCondition = 'must_exist' | 'must_not_exist';
export type CheckSeverity = 'minor' | 'major' | 'critical';

export interface MonitoredServiceRule {
  name: string;
  expected_state: ServiceState;
  severity: CheckSeverity;
  enabled: boolean;
}

export interface MonitoredFileRule {
  path: string;
  condition: FileCondition;
  severity: CheckSeverity;
  max_size_mb?: number | null;
  enabled: boolean;
}

export interface PartitionRule {
  mount: string;
  warning: number;
  critical: number;
}

export interface ThresholdPair {
  warning: number | null;
  critical: number | null;
  /** true quand l'hôte suit les seuils globaux au lieu d'une surcharge. */
  inherited?: boolean;
}

export interface MonitoringPlan {
  agent_id: string;
  version: number;
  version_acked: number;
  cpu: ThresholdPair;
  ram: ThresholdPair;
  disk: ThresholdPair & { partitions: PartitionRule[] };
  services: MonitoredServiceRule[];
  files: MonitoredFileRule[];
}

/** Envoi partiel accepté : une section absente n'est pas touchée, une section
 *  présente remplace intégralement son contenu — envoyer `services: []` vide
 *  donc la liste, ce qui est le comportement voulu quand on retire le
 *  dernier service surveillé. */
export interface MonitoringPlanPatch {
  cpu?: Partial<ThresholdPair>;
  ram?: Partial<ThresholdPair>;
  disk?: Partial<ThresholdPair> & { partitions?: PartitionRule[] };
  services?: MonitoredServiceRule[];
  files?: MonitoredFileRule[];
}

export interface AgentHeartbeatsParams {
  page?: number;
  limit?: number;
  start_date?: string;
  end_date?: string;
}

export function unwrapList<T>(payload: any): T[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

export const agentsService = {
  async getAgents(params?: AgentsListParams): Promise<Agent[]> {
    const response = await axiosInstance.get('/agents', {
      params: { include_offline: true, ...params },
    });
    const backendAgents = unwrapList<BackendAgent>(response.data);
    return backendAgents.map((agent) => DataMapper.mapBackendAgent(agent));
  },

  async getAgent(id: string): Promise<Agent> {
    const response = await axiosInstance.get(`/agents/${id}`);
    return DataMapper.mapBackendAgent(response.data);
  },

  async getAgentHeartbeats(id: string, params?: AgentHeartbeatsParams): Promise<any[]> {
    const response = await axiosInstance.get(`/agents/${id}/heartbeats`, { params });
    return response.data.items || response.data;
  },

  async getAgentMetricHistory(
    id: string,
    params?: { name?: string; hours?: number; step?: string }
  ): Promise<{
    name: string;
    status: string;
    result: Array<{ points: Array<{ ts: string; value: number }> }>;
  }> {
    const response = await axiosInstance.get(`/agents/${id}/metrics/history`, { params });
    return response.data;
  },

  async updateAgentThresholds(id: string, thresholds: CustomThresholds): Promise<void> {
    await axiosInstance.put(`/agents/${id}/thresholds`, {
      cpu_warning_threshold: thresholds.cpuWarning,
      cpu_critical_threshold: thresholds.cpuCritical,
      ram_warning_threshold: thresholds.ramWarning,
      ram_critical_threshold: thresholds.ramCritical,
      disk_warning_threshold: thresholds.diskWarning,
      disk_critical_threshold: thresholds.diskCritical,
      disk_mount_rules: (thresholds.diskMountRules || [])
        .filter((r) => r.mount?.trim())
        .map((r) => ({
          mount: r.mount.trim(),
          warning: r.warning,
          critical: r.critical,
        })),
    });
  },

  async getAgentPartitions(id: string): Promise<{
    partitions: Array<{
      name: string;
      mount: string;
      letter?: string | null;
      label?: string | null;
      fstype?: string;
      percent?: number;
      total_gb?: number;
      used_gb?: number;
    }>;
    disk_mount_rules: Array<{ mount: string; warning: number; critical: number }>;
  }> {
    const response = await axiosInstance.get(`/agents/${id}/partitions`);
    return response.data;
  },

  async revokeAgent(id: string): Promise<void> {
    await axiosInstance.put(`/agents/${id}/revoke`);
  },

  async deleteAgent(id: string): Promise<void> {
    await axiosInstance.delete(`/agents/${id}`);
  },

  /**
   * Modifie les champs attribués d'un hôte.
   *
   * Remplace les anciennes routes mono-champ `/name` et `/location`, qui
   * n'avaient d'ailleurs aucun appelant. Le serveur refuse explicitement
   * toute écriture sur un champ constaté par l'agent (nom machine, IP, OS,
   * matériel) plutôt que de l'ignorer en silence.
   */
  /** Alias court de `patchAgent`. */
  async patch(id: string, changes: AgentPatch): Promise<PatchAgentResponse> {
    return this.patchAgent(id, changes);
  },

  async patchAgent(id: string, changes: AgentPatch): Promise<PatchAgentResponse> {
    const { data } = await axiosInstance.patch(`/agents/${id}`, changes);
    return data;
  },

  /** Plan de supervision complet d'un hôte. */
  /**
   * Inventaire logiciel d'un hôte : services offerts, applications, pilotes.
   *
   * Alimente aussi le sélecteur de services du plan : l'exploitant choisit
   * parmi ce que l'hôte déclare, au lieu de saisir un nom. Une faute de
   * frappe produirait une surveillance qui ne surveille rien.
   */
  async getInventory(id: string): Promise<HostInventory> {
    const { data } = await axiosInstance.get(`/agents/${id}/inventory`);
    return data;
  },

  async getMonitoringPlan(id: string): Promise<MonitoringPlan> {
    const { data } = await axiosInstance.get(`/agents/${id}/monitoring`);
    return data;
  },

  /** Remplace le plan et déclenche sa publication vers l'agent. */
  async updateMonitoringPlan(id: string, plan: MonitoringPlanPatch): Promise<MonitoringPlan> {
    const { data } = await axiosInstance.put(`/agents/${id}/monitoring`, plan);
    return data;
  },

  /** @deprecated remplacé par patchAgent — conservé pour compatibilité. */
  async updateAgentLocation(id: string, location: string): Promise<void> {
    await axiosInstance.patch(`/agents/${id}`, { location });
  },

  /** @deprecated remplacé par patchAgent — conservé pour compatibilité. */
  async updateAgentName(id: string, name: string): Promise<void> {
    await axiosInstance.patch(`/agents/${id}`, { name });
  },
};

export interface HostInventory {
  agent_id: string;
  collected_at?: string | null;
  services: Array<{ name: string; display_name?: string | null; status?: string | null; start_type?: string | null }>;
  applications: Array<{ name: string; version?: string | null; publisher?: string | null; install_date?: string | null }>;
  drivers: Array<{ name: string; display_name?: string | null; version?: string | null; state?: string | null }>;
  truncated: string[];
  unavailable: string[];
}

export interface VlanSubnet {
  id: string;
  cidr: string;
  vlan: string;
  label?: string | null;
  imported_at?: string | null;
  imported_by?: string | null;
  source_file?: string | null;
}

export interface VlanImportResult {
  imported: number;
  rejected: Array<{ line: number; reason: string; value?: string }>;
  message: string;
}

/**
 * Plan d'adressage fourni par l'équipe réseau.
 *
 * Une table de sous-réseaux plutôt qu'une liste d'hôtes : l'agent remonte son
 * IP à chaque battement, le VLAN se déduit donc pour tout le parc sans saisie,
 * et la déduction suit quand une machine change d'adresse.
 */
export const vlanSubnetsService = {
  async list(): Promise<VlanSubnet[]> {
    const { data } = await axiosInstance.get('/vlan-subnets');
    return unwrapList<VlanSubnet>(data);
  },

  async import(file: File): Promise<VlanImportResult> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await axiosInstance.post('/vlan-subnets/import', form);
    return data;
  },

  async clear(): Promise<void> {
    await axiosInstance.delete('/vlan-subnets');
  },
};

/** Équipes responsables d'hôtes (point 3). */
export const adminGroupsService = {
  async list(): Promise<AdminGroup[]> {
    const { data } = await axiosInstance.get('/admin-groups');
    return unwrapList<AdminGroup>(data);
  },

  async create(name: string, description?: string): Promise<AdminGroup> {
    const { data } = await axiosInstance.post('/admin-groups', { name, description });
    return data;
  },

  async setMembers(groupId: string, userIds: string[]): Promise<AdminGroup> {
    const { data } = await axiosInstance.put(`/admin-groups/${groupId}/members`, {
      user_ids: userIds,
    });
    return data;
  },

  async remove(groupId: string): Promise<void> {
    await axiosInstance.delete(`/admin-groups/${groupId}`);
  },
};
