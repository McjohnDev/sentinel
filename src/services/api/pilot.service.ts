/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

export type PilotHost = {
  id: string;
  hostname: string;
  agent_id?: string;
  os?: string;
  location?: string;
  checklist: {
    enroll?: boolean;
    first_metrics?: boolean;
    heartbeat_ok?: boolean;
    alerts_visible?: boolean;
  };
  status: string;
  notes?: string;
};

export type UatCase = {
  id: string;
  family: number;
  case_id: string;
  title: string;
  requirement_refs: string;
  status: string;
  evidence?: string;
  tester?: string;
  tested_at?: string;
};

export const pilotService = {
  async listHosts(): Promise<PilotHost[]> {
    const res = await axiosInstance.get('/pilot/hosts');
    return res.data.data || [];
  },
  async createHost(body: { hostname: string; agent_id?: string; os?: string; location?: string }) {
    const res = await axiosInstance.post('/pilot/hosts', body);
    return res.data;
  },
  async updateHost(
    id: string,
    body: {
      enroll: boolean;
      first_metrics: boolean;
      heartbeat_ok: boolean;
      alerts_visible: boolean;
      status?: string;
      notes?: string;
      agent_id?: string;
    }
  ) {
    const res = await axiosInstance.patch(`/pilot/hosts/${id}`, body);
    return res.data;
  },
  async deleteHost(id: string) {
    await axiosInstance.delete(`/pilot/hosts/${id}`);
  },
  async listUat(family?: number): Promise<{ data: UatCase[]; summary: Record<string, unknown> }> {
    const res = await axiosInstance.get('/uat/cases', { params: family ? { family } : {} });
    return res.data;
  },
  async updateUat(caseId: string, body: { status: string; evidence?: string; tester?: string }) {
    const res = await axiosInstance.patch(`/uat/cases/${caseId}`, body);
    return res.data;
  },
  async getAcceptancePack() {
    const res = await axiosInstance.get('/acceptance/pack');
    return res.data;
  },
  async listSignoffs() {
    const res = await axiosInstance.get('/acceptance/signoffs');
    return res.data.data || [];
  },
  async createSignoff(body: { role: string; name: string; decision: string; comment?: string }) {
    const res = await axiosInstance.post('/acceptance/signoffs', body);
    return res.data;
  },
  async setCoverageStatus(checkId: string, status: string, notes?: string) {
    const res = await axiosInstance.patch(`/coverage/checks/${checkId}`, { status, notes });
    return res.data;
  },
  async bulkVerify() {
    const res = await axiosInstance.post('/coverage/checks/bulk-verify');
    return res.data;
  },
  async bulkDecommission() {
    const res = await axiosInstance.post('/coverage/checks/bulk-decommission');
    return res.data;
  },
};
