"""
Workflow Execution Engine
Handles topological sort execution, node registry, and context passing
"""
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Executes workflow nodes in topological order based on edges.
    Manages context passing between nodes and handles dependencies.
    """
    
    def __init__(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """
        Initialize workflow engine.
        
        Args:
            nodes: List of node definitions [{id, type, data}]
            edges: List of edge definitions [{id, source, target}]
        """
        self.nodes = {node['id']: node for node in nodes}
        self.edges = edges
        self.graph = self._build_graph()
        self.execution_order: List[str] = []
        
    def _build_graph(self) -> Dict[str, List[str]]:
        """
        Build adjacency list from edges.
        
        Returns:
            Graph as {node_id: [dependent_node_ids]}
        """
        graph = defaultdict(list)
        
        # Initialize all nodes in graph
        for node_id in self.nodes:
            if node_id not in graph:
                graph[node_id] = []
        
        # Add edges
        for edge in self.edges:
            source = edge['source']
            target = edge['target']
            graph[source].append(target)
        
        return dict(graph)
    
    def topological_sort(self) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm.
        
        Returns:
            List of node IDs in execution order
        
        Raises:
            ValueError: If graph contains cycles
        """
        # Calculate in-degrees
        in_degree = {node_id: 0 for node_id in self.nodes}
        for node_id, neighbors in self.graph.items():
            for neighbor in neighbors:
                in_degree[neighbor] += 1
        
        # Initialize queue with nodes having no dependencies
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        execution_order = []
        
        while queue:
            node_id = queue.popleft()
            execution_order.append(node_id)
            
            # Reduce in-degree for neighbors
            for neighbor in self.graph.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(execution_order) != len(self.nodes):
            raise ValueError("Workflow contains cycles - cannot execute")
        
        self.execution_order = execution_order
        logger.info(f"Topological sort completed: {execution_order}")
        return execution_order
    
    def get_node_dependencies(self, node_id: str) -> List[str]:
        """
        Get list of nodes that must execute before this node.
        
        Args:
            node_id: Target node ID
        
        Returns:
            List of prerequisite node IDs
        """
        dependencies = []
        for source, targets in self.graph.items():
            if node_id in targets:
                dependencies.append(source)
        return dependencies
    
    def get_node_dependents(self, node_id: str) -> List[str]:
        """
        Get list of nodes that depend on this node.
        
        Args:
            node_id: Source node ID
        
        Returns:
            List of dependent node IDs
        """
        return self.graph.get(node_id, [])
    
    def validate_workflow(self) -> Tuple[bool, Optional[str]]:
        """
        Validate workflow structure.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for trigger nodes
        trigger_types = {'manual_trigger', 'schedule_trigger', 'event_trigger', 'api_trigger'}
        has_trigger = any(
            node['type'] in trigger_types 
            for node in self.nodes.values()
        )
        if not has_trigger:
            return False, "Workflow must have at least one trigger node"
        
        # Check for orphaned nodes (no incoming or outgoing edges)
        connected_nodes = set()
        for edge in self.edges:
            connected_nodes.add(edge['source'])
            connected_nodes.add(edge['target'])
        
        trigger_nodes = {
            node_id for node_id, node in self.nodes.items()
            if node['type'] in trigger_types
        }
        
        orphaned = set(self.nodes.keys()) - connected_nodes - trigger_nodes
        if orphaned:
            return False, f"Orphaned nodes detected: {', '.join(orphaned)}"
        
        # Check for cycles
        try:
            self.topological_sort()
        except ValueError as e:
            return False, str(e)
        
        # Validate edge references
        for edge in self.edges:
            if edge['source'] not in self.nodes:
                return False, f"Edge references unknown source node: {edge['source']}"
            if edge['target'] not in self.nodes:
                return False, f"Edge references unknown target node: {edge['target']}"
        
        return True, None
    
    def get_execution_plan(self) -> List[Dict[str, Any]]:
        """
        Generate execution plan with node details.
        
        Returns:
            List of execution steps with metadata
        """
        if not self.execution_order:
            self.topological_sort()
        
        plan = []
        for idx, node_id in enumerate(self.execution_order):
            node = self.nodes[node_id]
            plan.append({
                'step': idx + 1,
                'node_id': node_id,
                'node_type': node['type'],
                'node_label': node['data'].get('label', node_id),
                'dependencies': self.get_node_dependencies(node_id),
                'dependents': self.get_node_dependents(node_id)
            })
        
        return plan
    
    def should_skip_node(
        self, 
        node_id: str, 
        context: Dict[str, Any], 
        failed_nodes: Set[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if a node should be skipped based on context and failures.
        
        Args:
            node_id: Node to check
            context: Current execution context
            failed_nodes: Set of node IDs that have failed
        
        Returns:
            Tuple of (should_skip, reason)
        """
        # Skip if any dependency failed
        dependencies = self.get_node_dependencies(node_id)
        failed_deps = set(dependencies) & failed_nodes
        if failed_deps:
            return True, f"Dependencies failed: {', '.join(failed_deps)}"
        
        # Check conditional logic for conditional_branch nodes
        node = self.nodes[node_id]
        if node['type'] == 'conditional_branch':
            # Conditional evaluation handled by node executor
            # Engine doesn't skip, but executor may choose paths
            pass
        
        return False, None
    
    def merge_context(
        self, 
        context: Dict[str, Any], 
        node_output: Dict[str, Any], 
        node_id: str
    ) -> Dict[str, Any]:
        """
        Merge node output into execution context.
        
        Args:
            context: Current context
            node_output: Output from executed node
            node_id: ID of executed node
        
        Returns:
            Updated context
        """
        # Store node-specific output
        context[f'node_{node_id}'] = node_output
        
        # Merge global outputs (prefixed keys)
        for key, value in node_output.items():
            if not key.startswith('_'):  # Underscore prefix = node-local only
                context[key] = value
        
        # Special handling for common outputs
        if 'model_id' in node_output:
            context['latest_model_id'] = node_output['model_id']
        
        if 'detection_results' in node_output:
            context['latest_detection_results'] = node_output['detection_results']
        
        if 'job_id' in node_output:
            context['latest_job_id'] = node_output['job_id']
        
        return context
    
    def get_node_input(
        self, 
        node_id: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare input data for a node from context and dependencies.
        
        Args:
            node_id: Target node ID
            context: Current execution context
        
        Returns:
            Input data dictionary for node
        """
        node = self.nodes[node_id]
        node_config = node['data'].get('config', {})
        
        # Start with node's configuration
        input_data = {**node_config}
        
        # Add context variables
        input_data['_context'] = context
        
        # Add outputs from direct dependencies
        dependencies = self.get_node_dependencies(node_id)
        input_data['_dependency_outputs'] = {
            dep_id: context.get(f'node_{dep_id}', {})
            for dep_id in dependencies
        }
        
        return input_data


class ContextManager:
    """Manages workflow execution context with scoping and isolation."""
    
    def __init__(self, initial_context: Optional[Dict[str, Any]] = None):
        """Initialize context manager."""
        self.context = initial_context or {}
        self.history: List[Dict[str, Any]] = []
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get context value."""
        return self.context.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set context value."""
        self.context[key] = value
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Batch update context."""
        self.context.update(updates)
    
    def snapshot(self) -> Dict[str, Any]:
        """Create snapshot of current context."""
        snapshot = self.context.copy()
        self.history.append(snapshot)
        return snapshot
    
    def rollback(self) -> None:
        """Rollback to previous snapshot."""
        if self.history:
            self.context = self.history.pop()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export context as dictionary."""
        return self.context.copy()
