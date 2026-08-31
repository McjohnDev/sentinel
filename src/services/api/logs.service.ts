/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';

export const logsService = {
  async search(params?: {
    q?: string;
    host?: string;
    severity?: string;
    source?: string;
    hours?: number;
    limit?: number;
  }): Promise<{
    status: string;
    result: Array<{
      ts: string;
      message: string;
      host?: string;
      severity?: string;
      agent_id?: string;
      source?: string;
      channel?: string;
    }>;
    error?: string;
  }> {
    const response = await axiosInstance.get('/logs/search', { params });
    return response.data;
  },
};
