/**
 * Training Types
 */

export interface TrainingJob {
  id: number;
  project_id: number;
  model_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_epoch: number;
  total_epochs: number;
  metrics_json: Record<string, any>;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface TrainingStart {
  project_id: number;
  model_name: string;
  base_model_id: number;
  epochs: number;
  batch_size: number;
  image_size: number;
  learning_rate: number;
}

export interface TrainingSummary {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  running_jobs: number;
  average_epochs: number;
  best_model?: {
    id: number;
    name: string;
    mAP: number;
  };
  recent_jobs: any[];
  metrics_over_time: any[];
}
