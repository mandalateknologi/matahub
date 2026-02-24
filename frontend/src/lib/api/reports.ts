/**
 * Reports API
 */
import client from './client';
import type { TrainingSummary, PredictionSummary } from '@/lib/types';

export const reportsAPI = {
  async getTrainingSummary(startDate?: string, endDate?: string): Promise<TrainingSummary> {
    const response = await client.get<TrainingSummary>('/reports/training/summary', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  async getPredictionSummary(startDate?: string, endDate?: string): Promise<PredictionSummary> {
    const response = await client.get<PredictionSummary>('/reports/prediction/summary', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
