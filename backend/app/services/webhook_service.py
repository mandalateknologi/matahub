"""
Webhook Service - Send HTTP webhooks with retry logic
"""
import requests
import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for sending webhooks with retry logic."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ) -> bool:
        """
        Send webhook with exponential backoff retry.
        
        Args:
            url: Webhook URL
            payload: JSON payload
            method: HTTP method (POST, PUT, PATCH)
            headers: Optional custom headers
            timeout: Request timeout in seconds
        
        Returns:
            True if successful, False otherwise
        """
        if headers is None:
            headers = {}
        
        # Set default headers
        headers.setdefault('Content-Type', 'application/json')
        headers.setdefault('User-Agent', 'ATVISION-Workflow/1.0')
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Sending webhook to {url} (attempt {attempt + 1}/{self.max_retries})")
                
                # Send request
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                # Check status
                response.raise_for_status()
                
                logger.info(f"Webhook sent successfully to {url}: {response.status_code}")
                return True
                
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout: {str(e)}"
                logger.warning(f"Webhook timeout on attempt {attempt + 1}: {str(e)}")
            
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text}"
                logger.warning(f"Webhook HTTP error on attempt {attempt + 1}: {str(e)}")
                
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error, not retrying: {last_error}")
                    return False
            
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                logger.warning(f"Webhook request error on attempt {attempt + 1}: {str(e)}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = self.backoff_factor ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        logger.error(f"Webhook failed after {self.max_retries} attempts. Last error: {last_error}")
        return False
    
    def send_workflow_webhook(
        self,
        url: str,
        execution_data: Dict[str, Any],
        custom_payload: Optional[Dict[str, Any]] = None,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send workflow execution webhook.
        
        Args:
            url: Webhook URL
            execution_data: Workflow execution data
            custom_payload: Optional custom payload to merge
            method: HTTP method
            headers: Optional custom headers
        
        Returns:
            True if successful
        """
        # Build payload
        payload = {
            "event": "workflow.execution",
            "timestamp": time.time(),
            "data": execution_data
        }
        
        # Merge custom payload
        if custom_payload:
            payload.update(custom_payload)
        
        return self.send_webhook(url, payload, method, headers)


# Singleton instance
webhook_service = WebhookService()
