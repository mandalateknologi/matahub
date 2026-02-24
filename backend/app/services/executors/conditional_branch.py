"""
Conditional Branch Executor
Handles conditional logic workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase

logger = logging.getLogger(__name__)


class ConditionalBranchExecutor(NodeExecutorBase):
    """Executor for conditional branching."""
    
    def __init__(self):
        super().__init__("conditional_branch")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate conditional expressions."""
        validated = self.validate_config(config)
        
        try:
            from simpleeval import simple_eval
            
            results = []
            for condition in validated.conditions:
                variable = condition['variable']
                operator = condition['operator']
                value = condition['value']
                
                context_value = context.get(variable)
                if context_value is None:
                    logger.warning(f"Variable '{variable}' not found in context")
                    results.append(False)
                    continue
                
                if operator == 'contains':
                    result = value in str(context_value)
                elif operator == 'not_contains':
                    result = value not in str(context_value)
                else:
                    expr = f"{context_value} {operator} {value}"
                    result = simple_eval(expr, names={})
                
                results.append(result)
                logger.info(f"Condition {variable} {operator} {value} = {result}")
            
            all_passed = all(results)
            
            return {
                "conditions_met": all_passed,
                "results": results,
                "branch": "true" if all_passed else "false"
            }
            
        except Exception as e:
            logger.error(f"Conditional node {node_id} failed: {str(e)}")
            raise
