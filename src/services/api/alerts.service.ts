/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { Alert } from '../../types';
import { DataMapper } from '../mappers/data.mapper';

export interface AlertsListParams {
  page?: number;
  limit?: number;
  severity?: string;
  status?: string;
  agent_id?: string;
  search?: string;
}

export interface AcknowledgeAlertRequest {
  comment?: string;
  operator_name?: string;
}

export interface ResolveAlertRequest {
  comment?: string;
  operator_name?: string;
}

export const alertsService = {
  async getAlerts(params?: AlertsListParams): Promise<Alert[]> {
    const response = await axiosInstance.get('/alerts', { params });
    const backendAlerts = response.data.items || response.data;
    return backendAlerts.map(DataMapper.mapBackendAlert);
  },

  async getAlert(id: string): Promise<Alert> {
    const response = await axiosInstance.get(`/alerts/${id}`);
    return DataMapper.mapBackendAlert(response.data);
  },

  async acknowledgeAlert(id: string, comment?: string, operatorName?: string): Promise<void> {
    await axiosInstance.post(`/alerts/${id}/acknowledge`, {
      comment,
      operator_name: operatorName,
    });
  },

  async resolveAlert(id: string, comment?: string, operatorName?: string): Promise<void> {
    await axiosInstance.post(`/alerts/${id}/resolve`, {
      comment,
      operator_name: operatorName,
    });
  },
};
