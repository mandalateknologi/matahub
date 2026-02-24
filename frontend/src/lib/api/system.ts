/**
 * System API
 */
import client from './client';

export const systemAPI = {
  async health(): Promise<{ status: string; app_name: string; version: string }> {
    const response = await client.get('/system/health');
    return response.data;
  },

  async status(): Promise<any> {
    const response = await client.get('/system/status');
    return response.data;
  },

  async cleanup(retentionDays?: number): Promise<{ status: string; directories_cleaned: number }> {
    const response = await client.post('/system/cleanup', null, {
      params: { retention_days: retentionDays },
    });
    return response.data;
  },
};
