/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { Alert } from '../../types';
import { DataMapper } from '../mappers/data.mapper';
import { BackendAlert } from '../types/api.types';
import { unwrapList } from './agents.service';

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

/** Évènement de chronologie tel qu'émis par GET /alerts/{id}/timeline. */
export interface AlertTimelineEvent {
  id: string;
  action: string;
  actor?: string | null;
  comment?: string | null;
  created_at: string;
}

export const alertsService = {
  async getAlerts(params?: AlertsListParams): Promise<Alert[]> {
    const response = await axiosInstance.get('/alerts', { params });
    const backendAlerts = unwrapList<BackendAlert>(response.data);
    return backendAlerts.map((alert) => DataMapper.mapBackendAlert(alert));
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

  /**
   * Chronologie réelle d'une alerte (ALR-005).
   *
   * Le tiroir d'alerte fabriquait auparavant sa chronologie côté client, avec
   * des entrées « Mail CBC » et « Webhook n8n » systématiquement en succès.
   * Cet appel expose les évènements réellement enregistrés par le serveur.
   */
  async getAlertTimeline(id: string): Promise<AlertTimelineEvent[]> {
    const response = await axiosInstance.get(`/alerts/${id}/timeline`);
    const events = response.data?.events;
    return Array.isArray(events) ? events : [];
  },

  /**
   * Prise en charge (point 9). `userId` à null rend l'alerte à personne.
   *
   * Distinct de l'acquittement : savoir qu'un incident est réel ne dit pas
   * qui le traite, et une alerte validée sans responsable reste ouverte
   * pendant que chacun suppose qu'un autre s'en occupe.
   */
  async assign(alertId: string, userId: string | null): Promise<void> {
    await axiosInstance.post(`/alerts/${alertId}/assign`, { user_id: userId });
  },

  /**
   * Délai de relance de cette alerte, en heures.
   *
   * `null` la rend au réglage du parc ; `0` coupe la relance pour elle
   * seule — un incident connu dont on attend une intervention planifiée
   * n'a pas besoin d'être rappelé toutes les trois heures d'ici là.
   */
  async setReminder(alertId: string, hours: number | null): Promise<void> {
    await axiosInstance.put(`/alerts/${alertId}/reminder`, { hours });
  },
};
