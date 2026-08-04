/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { Agent, CustomThresholds } from '../../types';
import { DataMapper } from '../mappers/data.mapper';

export interface AgentsListParams {
  page?: number;
  limit?: number;
  status?: string;
  search?: string;
}

export interface AgentHeartbeatsParams {
  page?: number;
  limit?: number;
  start_date?: string;
  end_date?: string;
}

export const agentsService = {
  async getAgents(params?: AgentsListParams): Promise<Agent[]> {
    const response = await axiosInstance.get('/agents', { params });
    const backendAgents = response.data.items || response.data;
    return backendAgents.map(DataMapper.mapBackendAgent);
  },

  async getAgent(id: string): Promise<Agent> {
    const response = await axiosInstance.get(`/agents/${id}`);
    return DataMapper.mapBackendAgent(response.data);
  },

  async getAgentHeartbeats(id: string, params?: AgentHeartbeatsParams): Promise<any[]> {
    const response = await axiosInstance.get(`/agents/${id}/heartbeats`, { params });
    return response.data.items || response.data;
  },

  async updateAgentThresholds(id: string, thresholds: CustomThresholds): Promise<void> {
    await axiosInstance.put(`/agents/${id}/thresholds`, thresholds);
  },

  async revokeAgent(id: string): Promise<void> {
    await axiosInstance.put(`/agents/${id}/revoke`);
  },

  async deleteAgent(id: string): Promise<void> {
    await axiosInstance.delete(`/agents/${id}`);
  },

  async updateAgentLocation(id: string, location: string): Promise<void> {
    await axiosInstance.put(`/agents/${id}/location`, { location });
  },

  async updateAgentName(id: string, name: string): Promise<void> {
    await axiosInstance.put(`/agents/${id}/name`, { name });
  },
};
