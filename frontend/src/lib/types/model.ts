/**
 * Model Types
 */

export interface BaseModelInfo {
  name: string;
  description: string;
  parameters: string;
  speed: string;
  accuracy: string;
}

export interface Model {
  id: number;
  name: string;
  base_type: string;
  inference_type: string;  // yolo, sam3
  task_type: string;  // detect, classify, segment
  requires_prompts?: boolean;  // Whether model requires prompts (SAM3, future prompt-capable models)
  project_id: number;
  status: 'pending' | 'training' | 'validating' | 'ready' | 'failed';
  metrics_json: Record<string, any>;
  validation_error?: string;
  created_at: string;
}

export interface ModelDetail extends Model {
  artifact_path?: string;
}

export interface ModelInfo {
  id: number;
  name: string;
  base_type: string;
  task_type: string;
  project_id: number;
  created_at: string;
}
