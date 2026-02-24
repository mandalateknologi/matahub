"""
Training Worker - Background Training Job Execution
"""
import threading
import traceback
import gc
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.training_job import TrainingJob, TrainingStatus
from app.models.model import Model, ModelStatus
from app.models.project import Project, ProjectStatus
from app.services.yolo_service import yolo_service

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil not available - memory monitoring disabled")


class TrainingWorker:
    """Worker for running training jobs in background threads."""
    
    def __init__(self):
        self._active_jobs: dict = {}
    
    def start_training(
        self,
        job_id: int,
        project_id: int,
        model_id: int,
        dataset_path: str,
        output_dir: str,
        task_type: str = "detect",
        base_model: str = "yolov8n",
        epochs: int = 100,
        batch_size: int = 16,
        image_size: int = 640,
        learning_rate: float = 0.01
    ) -> None:
        """
        Start a training job in a background thread.
        
        Args:
            job_id: Training job ID
            project_id: Project ID
            model_id: Model ID
            dataset_path: Path to the dataset
            output_dir: Path for training outputs
            base_model: Base YOLO model type
            epochs: Number of epochs
            batch_size: Batch size
            image_size: Image size
            learning_rate: Learning rate
        """
        thread = threading.Thread(
            target=self._run_training,
            args=(
                job_id, project_id, model_id, dataset_path, output_dir,
                task_type, base_model, epochs, batch_size, image_size, learning_rate
            ),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def _run_training(
        self,
        job_id: int,
        project_id: int,
        model_id: int,
        dataset_path: str,
        output_dir: str,
        task_type: str,
        base_model: str,
        epochs: int,
        batch_size: int,
        image_size: int,
        learning_rate: float
    ) -> None:
        """
        Execute training job in background.
        
        Updates database with progress and results.
        """
        db = SessionLocal()
        
        # Memory monitoring: log initial state
        initial_memory_mb = 0
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                initial_memory_mb = process.memory_info().rss / 1024 / 1024
                print(f"📊 Memory before training: {initial_memory_mb:.1f} MB")
            except Exception:
                pass
        
        try:
            # Update job status to running
            job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
            if not job:
                return
            
            job.status = TrainingStatus.RUNNING.value
            job.started_at = datetime.now(timezone.utc)
            job.progress = 0.0
            db.commit()
            
            # Update project and model status
            project = db.query(Project).filter(Project.id == project_id).first()
            model = db.query(Model).filter(Model.id == model_id).first()
            
            if project:
                project.status = ProjectStatus.TRAINING.value
            if model:
                model.status = ModelStatus.TRAINING.value
            db.commit()
            
            # Create progress callback
            def update_progress(epoch: int, total_epochs: int, metrics: dict = None):
                nonlocal db, job
                try:
                    # Refresh session
                    db.refresh(job)
                    job.current_epoch = epoch
                    job.total_epochs = total_epochs
                    job.progress = (epoch / total_epochs) * 100
                    if metrics:
                        job.metrics_json = metrics
                    db.commit()
                except Exception:
                    db.rollback()
            
            # Run training
            result = yolo_service.train(
                dataset_path=dataset_path,
                output_dir=output_dir,
                task_type=task_type,
                base_model=base_model,
                epochs=epochs,
                batch_size=batch_size,
                image_size=image_size,
                learning_rate=learning_rate,
                progress_callback=update_progress
            )
            
            # Memory monitoring: log state after training
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    after_training_mb = process.memory_info().rss / 1024 / 1024
                    print(f"📊 Memory after training: {after_training_mb:.1f} MB (delta: +{after_training_mb - initial_memory_mb:.1f} MB)")
                except Exception:
                    pass
            
            # Update job as completed
            db.refresh(job)
            job.status = TrainingStatus.COMPLETED.value
            job.progress = 100.0
            job.current_epoch = epochs
            job.metrics_json = result.get("metrics", {})
            job.completed_at = datetime.now(timezone.utc)
            
            # Update model with artifact path and metrics
            if model:
                model.status = ModelStatus.READY.value
                model.artifact_path = result.get("model_path")
                model.metrics_json = result.get("metrics", {})
            
            # Update project status
            if project:
                db.refresh(project)
                project.status = ProjectStatus.TRAINED.value
            
            db.commit()
            
        except Exception as e:
            # Handle error
            db.rollback()
            
            try:
                job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
                if job:
                    job.status = TrainingStatus.FAILED.value
                    job.error_message = str(e)[:1000]
                    job.completed_at = datetime.now(timezone.utc)
                
                model = db.query(Model).filter(Model.id == model_id).first()
                if model:
                    model.status = ModelStatus.FAILED.value
                
                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.status = ProjectStatus.FAILED.value
                
                db.commit()
            except Exception:
                db.rollback()
            
            # Log error
            print(f"Training job {job_id} failed: {str(e)}")
            traceback.print_exc()
            
        finally:
            # CRITICAL: Fallback memory cleanup (even if training failed)
            try:
                # Delete local references to ensure cleanup
                if 'result' in locals():
                    del result
                
                # Clear CUDA cache if available
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                
                # Force garbage collection
                gc.collect()
                
                # Memory monitoring: log final state
                if PSUTIL_AVAILABLE:
                    try:
                        process = psutil.Process()
                        final_memory_mb = process.memory_info().rss / 1024 / 1024
                        print(f"📊 Memory after cleanup: {final_memory_mb:.1f} MB (total delta: {final_memory_mb - initial_memory_mb:+.1f} MB)")
                        if final_memory_mb - initial_memory_mb > 100:
                            print(f"⚠️  Warning: {final_memory_mb - initial_memory_mb:.1f} MB memory may still be held by Python/PyTorch")
                    except Exception:
                        pass
                
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup error in finally block (non-fatal): {cleanup_error}")
            
            # Close database and cleanup job tracking
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def is_job_running(self, job_id: int) -> bool:
        """Check if a training job is currently running."""
        return job_id in self._active_jobs and self._active_jobs[job_id].is_alive()
    
    def get_active_jobs(self) -> list:
        """Get list of active job IDs."""
        return [jid for jid, thread in self._active_jobs.items() if thread.is_alive()]


# Global worker instance
training_worker = TrainingWorker()
