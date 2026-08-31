/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

/** Une ligne de la piste d'audit, telle que le serveur l'a écrite. */
export interface AuditEntry {
  id: string;
  created_at: string;
  event_type: string;
  user_id: string | null;
  username: string | null;
  ip_address: string | null;
  target: string | null;
  status: string;
  details: string | null;
}

export interface AuditListParams {
  skip?: number;
  limit?: number;
  event_type?: string;
  user_id?: string;
  status?: string;
}

export const auditService = {
  async list(params?: AuditListParams): Promise<{
    data: AuditEntry[];
    pagination: { skip: number; limit: number; total: number };
  }> {
    const response = await axiosInstance.get('/audit', { params });
    return {
      data: Array.isArray(response.data?.data) ? response.data.data : [],
      pagination: response.data?.pagination ?? { skip: 0, limit: 0, total: 0 },
    };
  },

  /**
   * Télécharge l'export CSV produit par le serveur.
   *
   * Le fichier était auparavant assemblé dans le navigateur à partir de
   * lignes reconstituées ; il est désormais généré à partir des lignes
   * persistées, et l'export est lui-même journalisé.
   */
  async downloadExport(): Promise<void> {
    const response = await axiosInstance.get('/audit/export', { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement('a');
      link.href = url;
      link.download = 'cbc-audit-cobac.csv';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } finally {
      URL.revokeObjectURL(url);
    }
  },
};
