/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

export interface MachineGroup {
  id: string;
  name: string;
  description?: string;
  current_version: number;
  agent_count: number;
  updated_at?: string;
}

export interface ConfigRevision {
  id: string;
  version: number;
  payload: Record<string, unknown>;
  note?: string;
  created_by?: string;
  created_at?: string;
}

export interface CoverageRow {
  check_id: string;
  plugin: string;
  status: string;
  sprint?: string;
  notes?: string;
}

export interface CoverageOverlap {
  id: string;
  agent_id: string;
  hostname?: string;
  check_id: string;
  plugin: string;
  notes?: string;
  detected_at?: string;
}

export const groupsService = {
  async list(): Promise<MachineGroup[]> {
    const response = await axiosInstance.get('/groups');
    return response.data.data || [];
  },

  async create(name: string, description?: string): Promise<MachineGroup> {
    const response = await axiosInstance.post('/groups', { name, description });
    return response.data;
  },

  async assign(agentId: string, groupId: string | null): Promise<void> {
    await axiosInstance.post('/groups/assign', { agent_id: agentId, group_id: groupId });
  },

  async revisions(groupId: string): Promise<ConfigRevision[]> {
    const response = await axiosInstance.get(`/groups/${groupId}/revisions`);
    return response.data.data || [];
  },

  async publish(groupId: string, payload: Record<string, unknown>, note?: string): Promise<{ version: number }> {
    const response = await axiosInstance.post(`/groups/${groupId}/publish`, { payload, note });
    return response.data;
  },

  async rollback(groupId: string, toVersion: number): Promise<{ version: number }> {
    const response = await axiosInstance.post(`/groups/${groupId}/rollback`, { to_version: toVersion });
    return response.data;
  },

  async coverageMap(): Promise<CoverageRow[]> {
    const response = await axiosInstance.get('/coverage/map');
    return response.data.data || [];
  },

  async overlaps(): Promise<CoverageOverlap[]> {
    const response = await axiosInstance.get('/coverage/overlaps');
    return response.data.data || [];
  },

  async flagOverlap(body: {
    agent_id: string;
    check_id: string;
    plugin: string;
    notes?: string;
  }): Promise<void> {
    await axiosInstance.post('/coverage/overlaps', body);
  },

  async clearOverlap(id: string): Promise<void> {
    await axiosInstance.post(`/coverage/overlaps/${id}/clear`);
  },
};
