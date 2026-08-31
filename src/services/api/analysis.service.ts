/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

export const analysisService = {
  async listDashboards() {
    const res = await axiosInstance.get('/dashboards');
    return res.data.data || [];
  },
  async createDashboard(body: { name: string; widgets: unknown[]; shared?: boolean }) {
    const res = await axiosInstance.post('/dashboards', body);
    return res.data;
  },
  async updateDashboard(id: string, body: { name: string; widgets: unknown[]; shared?: boolean }) {
    const res = await axiosInstance.put(`/dashboards/${id}`, body);
    return res.data;
  },
  async deleteDashboard(id: string) {
    await axiosInstance.delete(`/dashboards/${id}`);
  },
  async listNetworkDevices() {
    const res = await axiosInstance.get('/network/devices');
    return res.data.data || [];
  },
  async createNetworkDevice(body: {
    name: string;
    host: string;
    snmp_community?: string;
  }) {
    const res = await axiosInstance.post('/network/devices', body);
    return res.data;
  },
  async probeDevice(id: string) {
    const res = await axiosInstance.post(`/network/devices/${id}/probe`);
    return res.data;
  },
  async probeAllDevices() {
    const res = await axiosInstance.post('/network/probe-all');
    return res.data;
  },
  async deleteDevice(id: string) {
    await axiosInstance.delete(`/network/devices/${id}`);
  },
  async listConnectors() {
    const res = await axiosInstance.get('/connectors');
    return res.data.data || [];
  },
  async createConnector(body: { name: string; kind?: string; endpoint?: string }) {
    const res = await axiosInstance.post('/connectors', body);
    return res.data;
  },
  async probeConnector(id: string) {
    const res = await axiosInstance.post(`/connectors/${id}/probe`);
    return res.data;
  },
  async listReportSchedules() {
    const res = await axiosInstance.get('/reports/schedules');
    return res.data.data || [];
  },
  async createReportSchedule(body: {
    name: string;
    format: string;
    cron?: string;
    enabled?: boolean;
  }) {
    const res = await axiosInstance.post('/reports/schedules', body);
    return res.data;
  },
  async downloadReport(format: 'csv' | 'pdf') {
    const res = await axiosInstance.get('/reports/generate', {
      params: { format },
      responseType: 'blob',
      // generate is POST in API — use post
    });
    return res.data as Blob;
  },
  async generateReport(format: 'csv' | 'pdf') {
    const res = await axiosInstance.post(`/reports/generate?format=${format}`, null, {
      responseType: 'blob',
    });
    return res.data as Blob;
  },
};
