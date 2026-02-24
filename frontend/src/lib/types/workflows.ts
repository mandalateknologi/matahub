// Types
export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    config: Record<string, any>;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface Workflow {
  id: number;
  name: string;
  description: string | null;
  creator_id: number;
  trigger_type: 'manual' | 'schedule' | 'event';
  trigger_config: Record<string, any>;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  is_active: boolean;
  is_template: boolean;
  template_category: string | null;
  scheduler_job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListItem {
  id: number;
  name: string;
  description: string | null;
  trigger_type: 'manual' | 'schedule' | 'event';
  trigger_config: Record<string, any>;
  nodes_count: number;
  is_active: boolean;
  is_template: boolean;
  created_at: string;
  updated_at: string;
  last_execution_status?: string | null;
  last_execution_at?: string | null;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  trigger_type: 'manual' | 'schedule' | 'event';
  trigger_config?: Record<string, any>;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  is_active?: boolean;
  is_template?: boolean;
  template_category?: string;
}

export interface WorkflowUpdate {
  name?: string;
  description?: string;
  trigger_type?: 'manual' | 'schedule' | 'event';
  trigger_config?: Record<string, any>;
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
  is_active?: boolean;
}

export interface WorkflowExecution {
  id: number;
  workflow_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  trigger_type: 'manual' | 'schedule' | 'event';
  trigger_data: Record<string, any>;
  context: Record<string, any>;
  error_message: string | null;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface WorkflowStepExecution {
  id: number;
  execution_id: number;
  node_id: string;
  node_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  training_job_id: number | null;
  detection_job_id: number | null;
  export_job_id: number | null;
}

export interface WorkflowExecutionDetail {
  execution: WorkflowExecution;
  steps: WorkflowStepExecution[];
  workflow_name: string;
}