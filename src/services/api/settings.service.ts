/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import axiosInstance from './axios.config';
import { GlobalThresholds, EmailNotificationConfig, DataRetentionConfig, EnrollmentToken } from '../../types';

export const settingsService = {
  async getGlobalThresholds(): Promise<GlobalThresholds> {
    const response = await axiosInstance.get('/settings/thresholds');
    return response.data;
  },

  async updateGlobalThresholds(thresholds: GlobalThresholds): Promise<void> {
    await axiosInstance.put('/settings/thresholds', thresholds);
  },

  async getEmailConfig(): Promise<EmailNotificationConfig> {
    const response = await axiosInstance.get('/settings/email');
    return response.data;
  },

  async updateEmailConfig(config: EmailNotificationConfig): Promise<void> {
    await axiosInstance.put('/settings/email', config);
  },

  async getRetentionConfig(): Promise<DataRetentionConfig> {
    const response = await axiosInstance.get('/settings/retention');
    return response.data;
  },

  async updateRetentionConfig(config: DataRetentionConfig): Promise<void> {
    await axiosInstance.put('/settings/retention', config);
  },

  async getEnrollmentTokens(): Promise<EnrollmentToken[]> {
    const response = await axiosInstance.get('/settings/tokens');
    return response.data;
  },

  async generateEnrollmentToken(): Promise<EnrollmentToken> {
    const response = await axiosInstance.post('/settings/tokens');
    return response.data;
  },
};
