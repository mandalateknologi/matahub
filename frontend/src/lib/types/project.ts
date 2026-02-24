/**
 * Project Types
 */

import type { Dataset } from './dataset';
import type { Model } from './model';

export interface Project {
  id: number;
  name: string;
  dataset_id: number | null;
  task_type: string;
  status: 'created' | 'training' | 'trained' | 'failed';
  is_system?: boolean;
  created_at: string;
}

export interface ProjectDetail extends Project {
  dataset?: Dataset;
  models?: Model[];
}

// Delete Confirmation
export interface DeleteConfirmation {
  detail: string;
  models_count: number;
  jobs_count: number;
  requires_confirmation: boolean;
}

export interface ProjectMember {
  user_id: number;
  email: string;
  role: string;
  added_at: string;
  added_by: number;
}

export interface AddProjectMemberRequest {
  user_id: number;
}