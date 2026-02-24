"""
Workflow Node Executors Package
Modular executors for different workflow node types.
"""
from typing import Dict, Optional

from app.services.executors.base import NodeExecutorBase
from app.services.executors.train_model import TrainModelExecutor
from app.services.executors.prediction import PredictionExecutor
from app.services.executors.recognition import RecognitionExecutor
from app.services.executors.export_results import ExportResultsExecutor
from app.services.executors.conditional_branch import ConditionalBranchExecutor
from app.services.executors.new_campaign import NewCampaignExecutor
from app.services.executors.input import InputExecutor
from app.services.executors.send_email import SendEmailExecutor
from app.services.executors.webhook import WebhookExecutor
from app.services.executors.show_images import ShowImagesExecutor
from app.services.executors.api_response import ApiResponseExecutor

# Executor registry
EXECUTOR_REGISTRY: Dict[str, NodeExecutorBase] = {
    "train_model": TrainModelExecutor(),
    "detection": PredictionExecutor(node_type="detection"),
    "classification": PredictionExecutor(node_type="classification"),  # Classification uses same executor as detection
    "recognition": RecognitionExecutor(),
    "export_results": ExportResultsExecutor(),
    "conditional_branch": ConditionalBranchExecutor(),
    "data_input": InputExecutor(),
    "new_campaign": NewCampaignExecutor(),
    "send_email": SendEmailExecutor(),
    "webhook": WebhookExecutor(),
    "show_images": ShowImagesExecutor(),
    "show_image_results": ShowImagesExecutor(),  # Frontend node type
    "show_video_results": ShowImagesExecutor(),  # Video results use same executor
    "api_response": ApiResponseExecutor(),
}


def get_executor(node_type: str) -> Optional[NodeExecutorBase]:
    """Get executor for node type."""
    return EXECUTOR_REGISTRY.get(node_type)


__all__ = [
    'NodeExecutorBase',
    'TrainModelExecutor',
    'PredictionExecutor',
    'RecognitionExecutor',
    'ExportResultsExecutor',
    'ConditionalBranchExecutor',
    'NewCampaignExecutor',
    'InputExecutor',
    'SendEmailExecutor',
    'WebhookExecutor',
    'ShowImagesExecutor',
    'ApiResponseExecutor',
    'EXECUTOR_REGISTRY',
    'get_executor',
]
