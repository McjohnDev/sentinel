/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

export type ActionTask = {
  id: string;
  agent_id: string;
  plugin: string;
  input: Record<string, unknown>;
  dry_run: boolean;
  status: string;
  requested_by?: string;
  approval_ref?: string;
  result?: Record<string, unknown> | null;
  rejection_reason?: string;
  audit_trail?: Array<{ at: string; actor: string; action: string; note?: string }>;
  created_at?: string;
};

export type ApprovalRow = {
  id: string;
  task_id: string;
  status: string;
  requested_by?: string;
  decided_by?: string;
  comment?: string;
  created_at?: string;
  task?: ActionTask | null;
};

export const actionsService = {
  async listPlugins() {
    const res = await axiosInstance.get('/actions/plugins');
    return res.data.data || [];
  },
  async listTasks(params?: { status?: string; agent_id?: string }) {
    const res = await axiosInstance.get('/actions/tasks', { params });
    return (res.data.data || []) as ActionTask[];
  },
  async createTask(body: {
    agent_id: string;
    plugin: string;
    input?: Record<string, unknown>;
    dry_run?: boolean;
    force_approval?: boolean;
  }) {
    const res = await axiosInstance.post('/actions/tasks', body);
    return res.data;
  },
  async listApprovals(status = 'pending') {
    const res = await axiosInstance.get('/approvals', { params: { status } });
    return (res.data.data || []) as ApprovalRow[];
  },
  async decide(approvalId: string, decision: 'approved' | 'denied', comment?: string) {
    const res = await axiosInstance.post(`/approvals/${approvalId}/decide`, { decision, comment });
    return res.data;
  },
  async setCapability(agentId: string, capability_level: 'L0' | 'L1') {
    const res = await axiosInstance.put(`/agents/${agentId}/capability`, { capability_level });
    return res.data;
  },
};
