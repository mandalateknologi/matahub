"""
Webhook Executor
Handles webhook notification workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase

logger = logging.getLogger(__name__)


class WebhookExecutor(NodeExecutorBase):
    """Executor for webhook notifications."""
    
    def __init__(self):
        super().__init__("webhook")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send webhook notification."""
        from app.services.webhook_service import webhook_service
        
        validated = self.validate_config(config)
        
        try:
            execution_data = {
                "workflow_id": context.get('workflow_id'),
                "execution_id": context.get('execution_id'),
                "status": "running",
                "node_id": node_id
            }
            
            if validated.include_execution_data:
                execution_data["context"] = {
                    k: v for k, v in context.items()
                    if not k.startswith('_') and k not in ['trigger_data']
                }
            
            success = webhook_service.send_workflow_webhook(
                url=validated.url,
                execution_data=execution_data,
                custom_payload=validated.custom_payload,
                method=validated.method,
                headers=validated.headers
            )
            
            logger.info(f"Webhook sent from node {node_id} to {validated.url}")
            
            return {
                "webhook_sent": success,
                "url": validated.url,
                "method": validated.method
            }
            
        except Exception as e:
            logger.error(f"Webhook node {node_id} failed: {str(e)}")
            raise
