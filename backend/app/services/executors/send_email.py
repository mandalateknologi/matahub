"""
Send Email Executor
Handles email notification workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase

logger = logging.getLogger(__name__)


class SendEmailExecutor(NodeExecutorBase):
    """Executor for sending email notifications."""
    
    def __init__(self):
        super().__init__("send_email")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send email notification."""
        from app.services.email_service import email_service
        
        validated = self.validate_config(config)
        
        try:
            # Render template variables
            subject = email_service.render_template_string(validated.subject, context)
            body = email_service.render_template_string(validated.body, context)
            
            # Collect attachments
            attachments = []
            if validated.include_attachments:
                for key, value in context.items():
                    if key.startswith('node_') and isinstance(value, dict):
                        if 'file_path' in value:
                            attachments.append(value['file_path'])
            
            # Send email
            workflow_id = context.get('workflow_id')
            success = email_service.send_email(
                recipients=validated.recipients,
                subject=subject,
                body=body,
                workflow_id=workflow_id,
                html=True,
                attachments=attachments if attachments else None
            )
            
            logger.info(f"Email sent from node {node_id} to {validated.recipients}")
            
            return {
                "email_sent": success,
                "recipients": validated.recipients,
                "subject": subject,
                "attachments_count": len(attachments)
            }
            
        except Exception as e:
            logger.error(f"Email node {node_id} failed: {str(e)}")
            raise
