"""
New Campaign Executor
Handles campaign creation workflow nodes.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timezone

from app.services.executors.base import NodeExecutorBase
from app.db import SessionLocal
from app.utils.campaign_tags import replace_tags

logger = logging.getLogger(__name__)


class NewCampaignExecutor(NodeExecutorBase):
    """Executor for new campaign nodes."""
    
    def __init__(self):
        super().__init__("new_campaign")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new campaign or use an existing one."""
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            actual_context = context.get('_context', context)
            creator_id = actual_context.get('creator_id')
            playbook_id = validated.playbook_id
            
            from app.models.campaign import Campaign, CampaignStatus
            from app.models.playbook import Playbook, PlaybookMember
            
            # Validate playbook exists and user has access
            playbook = db.query(Playbook).filter(Playbook.id == playbook_id).first()
            if not playbook:
                raise ValueError(f"Playbook {playbook_id} not found")
            
            is_creator = playbook.creator_id == creator_id
            is_member = db.query(PlaybookMember).filter(
                PlaybookMember.playbook_id == playbook_id,
                PlaybookMember.user_id == creator_id
            ).first() is not None
            
            if not (is_creator or is_member):
                raise ValueError(f"User {creator_id} does not have access to playbook {playbook_id}")
            
            # Check campaign mode
            if validated.campaign_mode == "existing":
                if not validated.campaign_id:
                    raise ValueError("campaign_id is required when campaign_mode is 'existing'")
                
                campaign = db.query(Campaign).filter(
                    Campaign.id == validated.campaign_id,
                    Campaign.playbook_id == playbook_id
                ).first()
                
                if not campaign:
                    raise ValueError(f"Campaign {validated.campaign_id} not found in playbook {playbook_id}")
                
                if campaign.status != CampaignStatus.ACTIVE:
                    raise ValueError(f"Campaign {validated.campaign_id} is not active")
                
                logger.info(f"Using existing campaign {campaign.id} from node {node_id}")
                
                return {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "status": "existing"
                }
            
            else:
                # Create new campaign
                campaign_name_template = validated.campaign_name or f"Campaign {datetime.now(timezone.utc).isoformat()}"
                campaign_desc_template = validated.campaign_description or ""
                
                campaign_name = replace_tags(campaign_name_template)
                campaign_description = replace_tags(campaign_desc_template) if campaign_desc_template else ""
                
                summary_json = {}
                if validated.form_fields:
                    summary_json = {"custom_fields": validated.form_fields}
                
                campaign = Campaign(
                    name=campaign_name,
                    description=campaign_description,
                    playbook_id=playbook_id,
                    creator_id=creator_id or 1,
                    status=CampaignStatus.ACTIVE,
                    summary_json=summary_json
                )
                db.add(campaign)
                db.commit()
                db.refresh(campaign)
                
                logger.info(f"Created new campaign {campaign.id} from node {node_id}")
                
                return {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "status": "created"
                }
            
        except Exception as e:
            logger.error(f"New campaign node {node_id} failed: {str(e)}")
            raise
        finally:
            db.close()
