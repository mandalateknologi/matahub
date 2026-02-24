/**
 * campaign Types
 * TypeScript interfaces for prediction sessions
 */

export type CampaignStatus = 'active' | 'ended';

export type CampaignExportType = 'mega_report_pdf' | 'mega_data_zip';

export type CampaignExportStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Campaign {
  id: number;
  name: string;
  description?: string;
  playbook_id: number;
  playbook_name?: string;
  model_id: number;
  model_name?: string;
  model_version?: number;
  creator_id: number;
  creator_name?: string;
  status: CampaignStatus;
  summary_json: Record<string, any>;
  created_at: string;
  ended_at?: string;
  
  // Calculated fields
  jobs_count: number;
  last_activity?: string;
  running_jobs_count: number;
}

export interface CampaignStats {
  campaign_id: number;
  total_predictions: number;
  total_jobs: number;
  completed_jobs: number;
  running_jobs: number;
  failed_jobs: number;
  
  // Mode breakdown
  single_jobs: number;
  batch_jobs: number;
  video_jobs: number;
  rtsp_jobs: number;
  
  // Prediction statistics
  class_counts: Record<string, number>;
  average_confidence: number;
  min_confidence?: number;
  max_confidence?: number;
  
  // Temporal data
  first_prediction?: string;
  last_prediction?: string;
  
  // Cache metadata
  cached_at?: string;
}

export interface CampaignExport {
  id: number;
  campaign_id: number;
  export_type: CampaignExportType;
  status: CampaignExportStatus;
  file_path?: string;
  progress: number;
  config_json: Record<string, any>;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface CampaignCreateRequest {
  name: string;
  playbook_id: number;
  model_id: number;
  description?: string;
}

export interface CampaignUpdateRequest {
  name?: string;
  description?: string;
}

export interface CampaignExportRequest {
  export_type: CampaignExportType;
  config?: Record<string, any>;
}

export interface CampaignListFilters {
  playbook_id?: number;
  status?: CampaignStatus;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface CampaignFormFieldConfig {
  field_name: string;
  label: string;
  field_type: "text" | "textarea" | "number" | "email" | "date" | "select";
  data_type: "string" | "number" | "date" | "email";
  required: boolean;
  placeholder?: string;
  options?: string[];
  order: number;
}

export interface CampaignFormResponse {
  id: number;
  project_id: number;
  form_config: CampaignFormFieldConfig[];
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignFormCreate {
  form_config: CampaignFormFieldConfig[];
}
