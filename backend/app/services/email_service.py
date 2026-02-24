"""
Email Service - SMTP email sending with rate limiting
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging

from app.config import settings
from jinja2 import Template

logger = logging.getLogger(__name__)


class EmailRateLimiter:
    """Rate limiter for email sending per workflow."""
    
    def __init__(self, max_per_hour: int = 10):
        self.max_per_hour = max_per_hour
        self._send_times: Dict[int, List[datetime]] = defaultdict(list)
    
    def can_send(self, workflow_id: int) -> bool:
        """Check if email can be sent for workflow."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        
        # Clean old timestamps
        self._send_times[workflow_id] = [
            ts for ts in self._send_times[workflow_id] 
            if ts > cutoff
        ]
        
        return len(self._send_times[workflow_id]) < self.max_per_hour
    
    def record_send(self, workflow_id: int) -> None:
        """Record email send timestamp."""
        self._send_times[workflow_id].append(datetime.now(timezone.utc))
    
    def get_remaining(self, workflow_id: int) -> int:
        """Get remaining sends allowed in current hour."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        
        recent = [
            ts for ts in self._send_times[workflow_id]
            if ts > cutoff
        ]
        
        return max(0, self.max_per_hour - len(recent))


class EmailService:
    """Service for sending emails via SMTP."""
    
    def __init__(self):
        self.rate_limiter = EmailRateLimiter(settings.EMAIL_RATE_LIMIT)
    
    def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        workflow_id: Optional[int] = None,
        html: bool = False,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send email via SMTP.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Email body (text or HTML)
            workflow_id: Workflow ID for rate limiting
            html: Whether body is HTML
            attachments: Optional list of file paths to attach
        
        Returns:
            True if sent successfully
        
        Raises:
            ValueError: If rate limit exceeded
            RuntimeError: If SMTP error occurs
        """
        # Check rate limit
        if workflow_id and not self.rate_limiter.can_send(workflow_id):
            remaining = self.rate_limiter.get_remaining(workflow_id)
            raise ValueError(
                f"Email rate limit exceeded for workflow {workflow_id}. "
                f"{remaining} emails remaining in current hour."
            )
        
        # Validate SMTP configuration
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            raise RuntimeError("SMTP credentials not configured in .env")
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Attach body
            body_part = MIMEText(body, 'html' if html else 'plain')
            msg.attach(body_part)
            
            # Attach files
            if attachments:
                for file_path in attachments:
                    self._attach_file(msg, file_path)
            
            # Send via SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            # Record send for rate limiting
            if workflow_id:
                self.rate_limiter.record_send(workflow_id)
            
            logger.info(f"Email sent to {recipients}: {subject}")
            return True
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {str(e)}")
            raise RuntimeError(f"Failed to send email: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            raise
    
    def send_template_email(
        self,
        recipients: List[str],
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        workflow_id: Optional[int] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Send email using Jinja2 template.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            template_name: Template filename (without .html)
            context: Template context variables
            workflow_id: Workflow ID for rate limiting
            attachments: Optional list of file paths to attach
        
        Returns:
            True if sent successfully
        """
        # Load template
        template_path = Path(__file__).parent.parent / "templates" / "emails" / f"{template_name}.html"
        
        if not template_path.exists():
            raise ValueError(f"Email template not found: {template_name}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Render template
        template = Template(template_content)
        html_body = template.render(**context)
        
        # Send email
        return self.send_email(
            recipients=recipients,
            subject=subject,
            body=html_body,
            workflow_id=workflow_id,
            html=True,
            attachments=attachments
        )
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Attach file to email message."""
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"Attachment not found: {file_path}")
            return
        
        with open(path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={path.name}'
        )
        msg.attach(part)
    
    def render_template_string(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render template string with context."""
        template = Template(template_str)
        return template.render(**context)


# Singleton instance
email_service = EmailService()
