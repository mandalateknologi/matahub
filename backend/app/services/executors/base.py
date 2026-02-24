"""
Base Executor Class
Provides base functionality for all workflow node executors.
"""
from typing import Dict, Any

from app.schemas.workflow_nodes import validate_node_config


class NodeExecutorBase:
    """Base class for node executors."""
    
    def __init__(self, node_type: str):
        self.node_type = node_type
    
    def validate_config(self, config: Dict[str, Any]) -> Any:
        """Validate node configuration."""
        return validate_node_config(self.node_type, config)
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute node logic.
        
        Args:
            node_id: Node ID
            config: Node configuration
            context: Workflow execution context
        
        Returns:
            Node output data
        """
        raise NotImplementedError("Subclasses must implement execute()")
