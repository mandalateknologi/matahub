/**
 * Training API
 */
import client from './client';
import type { TrainingJob, TrainingStart } from '@/lib/types';

export const trainingAPI = {
  async start(data: TrainingStart): Promise<TrainingJob> {
    const response = await client.post<TrainingJob>('/training/start', data);
    return response.data;
  },

  async get(id: number): Promise<TrainingJob> {
    const response = await client.get<TrainingJob>(`/training/${id}`);
    return response.data;
  },

  async list(projectId?: number, skip = 0, limit = 100): Promise<TrainingJob[]> {
    const params: any = { skip, limit };
    if (projectId) {
      params.project_id = projectId;
    }
    const response = await client.get<TrainingJob[]>('/training', { params });
    return response.data;
  },

  async getLogs(id: number): Promise<{ logs: string[]; current_epoch: number; total_epochs: number }> {
    const response = await client.get(`/training/${id}/logs`);
    return response.data;
  },
};
