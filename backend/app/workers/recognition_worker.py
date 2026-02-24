"""
Recognition Worker - Background Embedding Generation
"""
import threading
import traceback
from datetime import datetime, timezone
from typing import List
from pathlib import Path

from app.db import SessionLocal
from app.models.recognition import RecognitionJob, RecognitionImage, RecognitionLabel, RecognitionCatalog
from app.services.recognition_service import get_recognition_service
from app.config import settings


class RecognitionWorker:
    """Worker for running embedding generation jobs in background threads."""
    
    def __init__(self):
        self._active_jobs: dict = {}
        self._recognition_service = get_recognition_service()
    
    def start_embedding_job(
        self,
        job_id: int,
        catalog_id: int,
        label_id: int,
        image_ids: List[int]
    ) -> None:
        """
        Start an embedding generation job in background thread.
        
        Args:
            job_id: Recognition job ID
            catalog_id: Catalog ID
            label_id: Label ID (which label these images belong to)
            image_ids: List of image IDs to process
        """
        thread = threading.Thread(
            target=self._run_embedding_generation,
            args=(job_id, catalog_id, label_id, image_ids),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def _run_embedding_generation(
        self,
        job_id: int,
        catalog_id: int,
        label_id: int,
        image_ids: List[int]
    ) -> None:
        """
        Execute embedding generation in background.
        
        Updates database with progress and results.
        """
        db = SessionLocal()
        
        try:
            # Update job status to processing
            job = db.query(RecognitionJob).filter(RecognitionJob.id == job_id).first()
            if not job:
                print(f"❌ Job {job_id} not found")
                return
            
            job.status = "processing"
            job.total_images = len(image_ids)
            job.processed_images = 0
            job.failed_images = 0
            db.commit()
            
            print(f"🔄 Starting embedding generation for job {job_id}: {len(image_ids)} images")
            
            # Process images in batches
            batch_size = 10  # Process 10 images at a time
            for i in range(0, len(image_ids), batch_size):
                batch_ids = image_ids[i:i + batch_size]
                
                # Fetch images
                images = db.query(RecognitionImage).filter(
                    RecognitionImage.id.in_(batch_ids),
                    RecognitionImage.is_processed == False
                ).all()
                
                if not images:
                    continue
                
                # Build absolute paths
                image_paths = []
                image_objects = []
                
                for img in images:
                    abs_path = Path(settings.DATA_DIR) / img.image_path
                    if abs_path.exists():
                        image_paths.append(str(abs_path))
                        image_objects.append(img)
                    else:
                        print(f"⚠️  Image not found: {abs_path}")
                        job.failed_images += 1
                
                # Generate embeddings in batch
                try:
                    embeddings = self._recognition_service.generate_embeddings_batch(image_paths)
                    
                    # Update database with embeddings
                    for img_obj, embedding in zip(image_objects, embeddings):
                        img_obj.embedding = embedding
                        img_obj.is_processed = True
                        job.processed_images += 1
                    
                    db.commit()
                    
                    print(f"✅ Processed batch {i // batch_size + 1}: {len(embeddings)} embeddings")
                    
                except Exception as e:
                    print(f"❌ Batch processing error: {e}")
                    job.failed_images += len(image_objects)
                    db.commit()
            
            # Update job status to completed
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            # Update label and catalog image counts
            label = db.query(RecognitionLabel).filter(RecognitionLabel.id == label_id).first()
            if label:
                processed_count = db.query(RecognitionImage).filter(
                    RecognitionImage.label_id == label_id,
                    RecognitionImage.is_processed == True
                ).count()
                label.image_count = processed_count
            
            catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
            if catalog:
                total_images = db.query(RecognitionImage).join(RecognitionLabel).filter(
                    RecognitionLabel.catalog_id == catalog_id,
                    RecognitionImage.is_processed == True
                ).count()
                catalog.image_count = total_images
            
            db.commit()
            
            print(f"✅ Job {job_id} completed: {job.processed_images} processed, {job.failed_images} failed")
            
        except Exception as e:
            print(f"❌ Error in embedding generation job {job_id}: {e}")
            traceback.print_exc()
            
            # Update job status to failed
            try:
                job = db.query(RecognitionJob).filter(RecognitionJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except:
                pass
            
        finally:
            db.close()
            # Remove from active jobs
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def get_active_jobs(self) -> List[int]:
        """Get list of active job IDs."""
        return list(self._active_jobs.keys())
    
    def is_job_running(self, job_id: int) -> bool:
        """Check if a job is currently running."""
        return job_id in self._active_jobs


# Global worker instance
recognition_worker = RecognitionWorker()
