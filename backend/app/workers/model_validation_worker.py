"""
Model Validation Worker - Background Model Validation Job Execution
"""
import threading
import traceback

from app.db import SessionLocal
from app.models.model import Model, ModelStatus
from app.services.yolo_service import yolo_service


class ModelValidationWorker:
    """Worker for validating uploaded models in background threads."""
    
    def __init__(self):
        self._active_validations: dict = {}
    
    def start_validation(
        self,
        model_id: int,
        model_path: str,
        dataset_path: str
    ) -> None:
        """
        Start a model validation job in a background thread.
        
        Args:
            model_id: Model ID to validate
            model_path: Path to the .pt model file
            dataset_path: Path to the dataset for validation
        """
        thread = threading.Thread(
            target=self._run_validation,
            args=(model_id, model_path, dataset_path),
            daemon=True
        )
        self._active_validations[model_id] = thread
        thread.start()
    
    def _run_validation(
        self,
        model_id: int,
        model_path: str,
        dataset_path: str
    ) -> None:
        """
        Execute model validation in background.
        
        Updates database with metrics and status.
        """
        db = SessionLocal()
        
        try:
            # Get model record
            model = db.query(Model).filter(Model.id == model_id).first()
            if not model:
                return
            
            # Update status to validating
            model.status = ModelStatus.VALIDATING.value
            model.validation_error = None
            db.commit()
            
            # Progress tracking (not stored, could be added to Model if needed)
            def progress_callback(progress: float):
                pass  # Could update model progress field if added
            
            # Extract metrics using YOLOService
            result = yolo_service.extract_metrics_from_model(
                model_path=model_path,
                dataset_path=dataset_path,
                progress_callback=progress_callback
            )
            
            # Update model with extracted metrics
            model.metrics_json = result.get("metrics", {})
            model.status = ModelStatus.READY.value
            model.validation_error = None
            db.commit()
            
            print(f"✅ Model {model_id} validation completed successfully")
            print(f"   Metrics: mAP50={result['metrics'].get('mAP50', 'N/A')}, "
                  f"mAP50-95={result['metrics'].get('mAP50-95', 'N/A')}")
            
        except Exception as e:
            # Update model status to failed with error message
            error_msg = str(e)[:500]  # Limit error message length
            
            try:
                model = db.query(Model).filter(Model.id == model_id).first()
                if model:
                    model.status = ModelStatus.FAILED.value
                    model.validation_error = error_msg
                    db.commit()
            except Exception as update_error:
                print(f"❌ Failed to update model status: {update_error}")
            
            print(f"❌ Model {model_id} validation failed: {error_msg}")
            traceback.print_exc()
            
        finally:
            db.close()
            # Remove from active validations
            if model_id in self._active_validations:
                del self._active_validations[model_id]
    
    def is_validating(self, model_id: int) -> bool:
        """
        Check if a model is currently being validated.
        
        Args:
            model_id: Model ID to check
            
        Returns:
            True if validation is in progress
        """
        return model_id in self._active_validations


# Global worker instance
model_validation_worker = ModelValidationWorker()
