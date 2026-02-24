/**
 * Prediction/Inference Types
 */

export interface PredictionJob {
  id: number;
  model_id: number;
  campaign_id?: number;
  model_name?: string;
  campaign_name?: string;
  task_type?: string;  // detect, classify, segment (from model)
  mode: 'single' | 'batch' | 'video' | 'rtsp';
  source_type: string;
  source_ref: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  summary_json: Record<string, any>;
  error_message?: string;
  progress?: number;
  creator_id: number;
  created_at: string;
  completed_at?: string;
  results_count?: number;
}

export interface MaskData {
  instance_id: number;
  class_id: number;
  class_name: string;
  score: number;
  bbox: number[];  // [x_min, y_min, x_max, y_max]
  polygon: number[][];
  height: number;
  width: number;
}

// Per-result configuration snapshot (audit trail for dynamic config changes)
export interface ResultConfig {
  confidence: number;
  iou_threshold?: number;
  imgsz?: number;
  class_filter?: string[];
  prompts?: any[];  // SAM3 prompts for segmentation
  inference_type?: string;  // yolo, sam3, etc.
}

export interface PredictionResult {
  // Identity fields (context-dependent)
  id?: number;  // Database ID (present when retrieved from DB)
  job_id: number;
  result_id?: number;  // Links to stored result (real-time context)
  
  // File/frame metadata
  file_name: string;
  frame_number?: number;  // Frame index for video/RTSP
  frame_timestamp?: string;  // Video position like "00:10:01.5"
  frame_base64?: string;  // Base64-encoded frame image (RTSP capture only)
  task_type?: string;  // detect, classify, segment
  
  // Configuration snapshot (tracks dynamic config changes during manual sessions)
  config?: ResultConfig;
  
  // LLM/chat outputs (reserved for future use)
  chats?: any[];
  
  // Performance metric (real-time only)
  inference_time_ms?: number;
  
  // Detection fields
  boxes?: number[][];
  scores?: number[];
  classes?: number[];
  class_names?: string[];
  
  // Classification fields
  top_class?: string;
  top_confidence?: number;
  top_classes?: string[];
  probabilities?: number[];
  
  // Segmentation fields
  masks?: MaskData[];
}

// Full API response (unified for all inference modes)
export interface PredictionResponse extends PredictionResult {
  // PredictionResponse is now just an alias for PredictionResult
  // Kept for backward compatibility and semantic clarity
}

// Alias for clarity in gallery/display contexts
export type DetectionData = Omit<PredictionResult, 'id' | 'job_id' | 'result_id' | 'file_name' | 'frame_number' | 'frame_timestamp' | 'inference_time_ms'>;

// Alias for clarity (or keep as separate type if needed)
export type GalleryPredictionResponse = DetectionData;

// Gallery Image (used in capture page and MediaDisplay component)
export interface GalleryImage {
  original: string;
  annotated: string;
  fileName: string;
  timestamp?: number;
  detectionData?: PredictionResponse;
}

export interface PredictionResponseWithFrame {
  frame: string;  // Base64-encoded image frame
  predictions: PredictionResponse;
}

// Inference Configuration Types
export interface InferencePrompt {
  type: 'text' | 'point' | 'box';
  value?: string;  // For text prompts
  coords?: number[];  // For point [x, y] or box [x1, y1, x2, y2]
  label?: number;  // For point prompts: 1=foreground, 0=background
}

export interface InferenceConfig {
  modelId: number;
  confidence?: number;
  campaignId?: number;
  classFilter?: string[];
  prompts?: InferencePrompt[];  // For prompt-capable models (SAM3, future models)
  iouThreshold?: number;  // For future use
  imgsz?: number;  // For future use
  duration?: number;  // For video info
  fps?: number;  // For video info
}

export interface InferenceCapabilities {
  service: string;
  version: string;
  model_types: string[];
  endpoints: Record<string, string>;
  features: string[];
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  recommendations: string[];
}
