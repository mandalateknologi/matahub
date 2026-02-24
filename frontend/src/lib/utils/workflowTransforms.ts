import type { Node, Edge } from '@xyflow/svelte';

// Backend workflow node structure
export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    config?: Record<string, any>;
  };
}

// Backend workflow edge structure
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

// Map node category to component type
const getCategoryForType = (nodeType: string): string => {
  const triggerTypes = ['manual_trigger', 'schedule_trigger', 'event_trigger', 'api_trigger'];
  const inputTypes = ['data_input', 'new_campaign'];
  const operationTypes = ['train_model', 'detection', 'recognition', 'export_results', 'conditional_branch'];
  const outputTypes = ['show_image_results', 'show_video_results', 'generate_detection_report', 'generate_campaign_report', 'api_response'];
  const notificationTypes = ['send_email', 'webhook'];

  if (triggerTypes.includes(nodeType)) return 'trigger';
  if (inputTypes.includes(nodeType)) return 'data_input';
  if (operationTypes.includes(nodeType)) return 'operation';
  if (outputTypes.includes(nodeType)) return 'data_output';
  if (notificationTypes.includes(nodeType)) return 'notification';
  
  return 'operation'; // default
};

/**
 * Convert backend workflow nodes to XYFlow format
 */
export const toXYFlowNodes = (workflowNodes: WorkflowNode[]): Node[] => {
  return workflowNodes.map(node => ({
    id: node.id,
    type: getCategoryForType(node.type), // 'trigger', 'input', 'operation', etc.
    position: node.position,
    data: {
      ...node.data,
      id: node.id,
      nodeType: node.type, // preserve original type for backend
      category: getCategoryForType(node.type)
    }
  }));
};

/**
 * Convert backend workflow edges to XYFlow format
 */
export const toXYFlowEdges = (workflowEdges: WorkflowEdge[]): Edge[] => {
  return workflowEdges.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    type: 'deletable', // XYFlow edge type - use deletable for custom edge component
    animated: false,
    markerEnd: {
      type: 'arrowclosed',
      width: 20,
      height: 20,
    },
  }));
};

/**
 * Convert XYFlow nodes back to backend format
 */
export const fromXYFlowNodes = (xyflowNodes: Node[]): WorkflowNode[] => {
  return xyflowNodes.map(node => ({
    id: node.id,
    type: node.data.nodeType || node.type, // restore original type
    position: node.position,
    data: {
      label: node.data.label,
      config: node.data.config || {}
    }
  }));
};

/**
 * Convert XYFlow edges back to backend format
 */
export const fromXYFlowEdges = (xyflowEdges: Edge[]): WorkflowEdge[] => {
  return xyflowEdges.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    ...(edge.label && { label: edge.label })
  }));
};
