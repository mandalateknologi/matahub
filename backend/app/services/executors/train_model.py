"""
Train Model Executor
Handles YOLO model training workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase
from app.workers.training_worker import training_worker
from app.db import SessionLocal
from app.models.training_job import TrainingJob, TrainingStatus
from app.models.model import Model
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)


class TrainModelExecutor(NodeExecutorBase):
    """Executor for training model nodes."""
    
    def __init__(self):
        super().__init__("train_model")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Train a YOLO model."""
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            # Get dataset and base model
            dataset = db.query(Dataset).filter(Dataset.id == validated.dataset_id).first()
            if not dataset:
                raise ValueError(f"Dataset {validated.dataset_id} not found")
            
            base_model = db.query(Model).filter(Model.id == validated.base_model_id).first()
            if not base_model:
                raise ValueError(f"Base model {validated.base_model_id} not found")
            
            # Get workflow-level context (project_id, creator_id are stored there)
            actual_context = context.get('_context', context)
            project_id = actual_context.get('project_id')
            creator_id = actual_context.get('creator_id')
            
            if not project_id:
                raise ValueError("project_id not found in workflow context")
            
            # Create model record
            model = Model(
                name=validated.model_name,
                project_id=project_id,
                base_model=base_model.name,
                dataset_id=validated.dataset_id,
                task_type=base_model.task_type,
                status="pending",
                created_by=creator_id
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            
            # Create training job
            training_job = TrainingJob(
                project_id=project_id,
                model_id=model.id,
                status=TrainingStatus.PENDING,
                progress=0.0,
                current_epoch=0,
                total_epochs=validated.epochs,
                metrics_json={}
            )
            db.add(training_job)
            db.commit()
            db.refresh(training_job)
            
            # Start training worker
            training_worker.start_training(
                job_id=training_job.id,
                project_id=project_id,
                model_id=model.id,
                dataset_path=dataset.yaml_path,
                output_dir=f"./runs/train/{model.id}",
                task_type=base_model.task_type,
                base_model=base_model.artifact_path,
                epochs=validated.epochs,
                batch_size=validated.batch_size,
                image_size=validated.image_size,
                learning_rate=validated.learning_rate
            )
            
            logger.info(f"Started training job {training_job.id} for node {node_id}")
            
            return {
                "job_id": training_job.id,
                "job_type": "training",
                "model_id": model.id,
                "status": "started"
            }
            
        except Exception as e:
            logger.error(f"Training node {node_id} failed: {str(e)}")
            raise
        finally:
            db.close()
