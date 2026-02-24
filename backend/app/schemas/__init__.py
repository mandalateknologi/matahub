"""
ATVISION Pydantic Schemas
"""
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token, TokenData
from app.schemas.dataset import DatasetCreate, DatasetResponse, DatasetDetail
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectDetail
from app.schemas.model import ModelCreate, ModelResponse, ModelDetail, BaseModelInfo
from app.schemas.training import TrainingStart, TrainingJobResponse, TrainingLogs
from app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    PredictionJobResponse,
    BatchPredictionRequest,
)
from app.schemas.reports import TrainingSummary, PredictionSummary

__all__ = [
    # User
    "UserCreate",
    "UserResponse",
    "UserLogin",
    "Token",
    "TokenData",
    # Dataset
    "DatasetCreate",
    "DatasetResponse",
    "DatasetDetail",
    # Project
    "ProjectCreate",
    "ProjectResponse",
    "ProjectDetail",
    # Model
    "ModelCreate",
    "ModelResponse",
    "ModelDetail",
    "BaseModelInfo",
    # Training
    "TrainingStart",
    "TrainingJobResponse",
    "TrainingLogs",
    # Prediction
    "PredictionRequest",
    "PredictionResponse",
    "PredictionJobResponse",
    "BatchPredictionRequest",
    # Reports
    "TrainingSummary",
    "PredictionSummary",
]
