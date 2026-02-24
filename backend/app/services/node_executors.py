"""
Workflow Node Executors
Wraps existing workers and services to execute workflow nodes.

This module provides backward compatibility by re-exporting executors
from the modular executors package.
"""
from typing import Dict, Any, Optional

# Import from modular executors package
from app.services.executors import (
    NodeExecutorBase,
    EXECUTOR_REGISTRY,
    get_executor,
    TrainModelExecutor,
    PredictionExecutor,
    RecognitionExecutor,
    ExportResultsExecutor,
    ConditionalBranchExecutor,
    NewCampaignExecutor,
    InputExecutor,
    SendEmailExecutor,
    WebhookExecutor,
    ShowImagesExecutor,
    ApiResponseExecutor,
)

# Import utility function for backward compatibility
from app.services.executors.utils import resolve_fm_path_to_absolute

# Re-export all for backward compatibility
__all__ = [
    'NodeExecutorBase',
    'EXECUTOR_REGISTRY',
    'get_executor',
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
    'resolve_fm_path_to_absolute',
]
