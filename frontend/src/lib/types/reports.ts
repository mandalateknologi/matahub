/**
 * Reports & Analytics Types
 */

export interface ClassificationMetrics {
  total_classifications: number;
  top_k_accuracy?: number;
  per_class_accuracy?: Record<string, number>;
  confusion_matrix?: number[][];
  average_top_confidence: number;
  class_distribution: Array<{
    class_name: string;
    count: number;
  }>;
}

export interface PredictionSummary {
  total_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  single_jobs: number;
  batch_jobs: number;
  video_jobs: number;
  rtsp_jobs: number;
  total_predictions: number;
  average_confidence: number;
  class_distribution?: Array<{
    class_name: string;
    count: number;
  }>;
  prediction_frequency?: any[];
  recent_jobs: any[];
  task_type_breakdown?: Record<string, number>;
  classification_metrics?: ClassificationMetrics;
}
