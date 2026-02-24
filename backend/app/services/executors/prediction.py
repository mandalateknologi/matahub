"""
Detection Executor
Handles object detection workflow nodes.
"""
import logging
import time
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.executors.base import NodeExecutorBase
from app.services.executors.utils import resolve_fm_path_to_absolute
from app.workers.prediction_worker import prediction_worker
from app.db import SessionLocal
from app.models.prediction_job import PredictionJob, PredictionMode, PredictionStatus
from app.models.prediction_result import PredictionResult
from app.models.model import Model
from app.config import settings
from app.utils.file_handler import save_prediction_image

logger = logging.getLogger(__name__)


class PredictionExecutor(NodeExecutorBase):
    """Executor for Prediction nodes."""
    
    def __init__(self, node_type: str):
        super().__init__(node_type)
    
    def _handle_post_processing(
        self,
        db: Session,
        post_action: str,
        input_sources: list,
        successful_files: list,
        output_folder: Optional[str],
        creator_id: int,
        workflow_id: int
    ):
        """
        Handle post-processing actions for folder scan mode.
        
        Args:
            db: Database session
            post_action: Action to perform ("move_to_output", "delete", "keep")
            input_sources: List of input file paths
            successful_files: List of successfully processed file names
            output_folder: Workflow output folder path (File Management relative, supports {workflow_id} placeholder)
            creator_id: User ID
            workflow_id: Workflow ID for path generation
        """
        if post_action == "keep":
            logger.info("Post-processing: Keeping files as is")
            return
        
        # Create set of successful filenames for quick lookup
        successful_set = set(successful_files)
        
        for source_path_str in input_sources:
            source_path = Path(source_path_str)
            filename = source_path.name
            
            # Only process files that were successfully detected
            if filename not in successful_set:
                logger.debug(f"Skipping {filename} - not in successful files")
                continue
            
            try:
                if post_action == "delete":
                    # Delete the source file
                    if source_path.exists():
                        source_path.unlink()
                        logger.info(f"Post-processing: Deleted {source_path}")
                    
                elif post_action == "move_to_output":
                    # Auto-generate output folder if not specified
                    if not output_folder:
                        output_folder = f"workflows/{workflow_id}/output"
                        logger.info(f"Post-processing: Auto-generated output folder: {output_folder}")
                    
                    # Replace {workflow_id} placeholder in output folder path
                    output_folder_resolved = output_folder.replace("{workflow_id}", str(workflow_id))
                    
                    # Move file to workflow output folder
                    dest_base = Path(settings.uploads_dir) / str(creator_id) / output_folder_resolved
                    dest_base.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_base / filename
                    
                    # Handle duplicate filenames
                    if dest_path.exists():
                        stem = dest_path.stem
                        suffix = dest_path.suffix
                        counter = 1
                        while dest_path.exists():
                            dest_path = dest_base / f"{stem}_{counter}{suffix}"
                            counter += 1
                    
                    # Move file
                    shutil.move(str(source_path), str(dest_path))
                    logger.info(f"Post-processing: Moved {source_path} -> {dest_path}")
                    
                    # Update File Management database
                    try:
                        from app.models.user_file import UserFile
                        
                        # Calculate relative path from source to match database entry format
                        source_file_path = None
                        try:
                            # Try relative to DATA_DIR
                            source_relative = source_path.relative_to(Path(settings.DATA_DIR))
                            source_file_path = str(source_relative).replace('\\', '/')
                            logger.info(f"Post-processing: Searching for file entry with path: {source_file_path}")
                        except ValueError:
                            # Try relative to user uploads dir
                            try:
                                source_relative = source_path.relative_to(Path(settings.uploads_dir) / str(creator_id))
                                source_file_path = f"uploads/{creator_id}/{str(source_relative).replace(chr(92), '/')}"
                                logger.info(f"Post-processing: Searching for file entry with path: {source_file_path}")
                            except ValueError:
                                logger.warning(f"Post-processing: Could not determine relative path for {source_path}")
                        
                        # Find existing file entry by exact path match
                        existing_file = None
                        if source_file_path:
                            existing_file = db.query(UserFile).filter(
                                UserFile.user_id == creator_id,
                                UserFile.file_path == source_file_path
                            ).first()
                            
                            if existing_file:
                                logger.info(f"Post-processing: Found existing entry by path for {filename}")
                        
                        # If not found by exact path, try finding by filename
                        if not existing_file:
                            logger.info(f"Post-processing: File entry not found by path, searching by filename: {filename}")
                            existing_file = db.query(UserFile).filter(
                                UserFile.user_id == creator_id,
                                UserFile.file_name == filename
                            ).order_by(UserFile.created_at.desc()).first()
                            
                            if existing_file:
                                logger.info(f"Post-processing: Found existing entry by filename: {existing_file.file_path}")
                        
                        # Calculate new file info
                        dest_relative = dest_path.relative_to(Path(settings.DATA_DIR))
                        dest_file_path = str(dest_relative).replace('\\', '/')
                        file_type = "image" if dest_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'] else "video"
                        file_size = dest_path.stat().st_size
                        
                        if existing_file:
                            # Update existing entry
                            logger.info(f"Post-processing: Updating entry {existing_file.id}: {existing_file.file_path} -> {dest_file_path}")
                            existing_file.file_path = dest_file_path
                            existing_file.folder_path = output_folder_resolved
                            existing_file.file_size = file_size
                            existing_file.file_type = file_type
                            logger.info(f"Post-processing: Successfully updated File Management entry for {filename}")
                        else:
                            # Create new entry if not found
                            logger.warning(f"Post-processing: No existing entry found, creating new one for {filename}")
                            user_file = UserFile(
                                user_id=creator_id,
                                file_path=dest_file_path,
                                file_name=dest_path.name,
                                file_type=file_type,
                                file_size=file_size,
                                folder_path=output_folder_resolved
                            )
                            db.add(user_file)
                            logger.info(f"Post-processing: Created new File Management entry for {filename}")
                        
                        db.commit()
                    except Exception as reg_error:
                        logger.error(f"Failed to update File Management for {filename}: {reg_error}", exc_info=True)
                        db.rollback()
                        
            except Exception as e:
                logger.error(f"Post-processing failed for {source_path}: {e}")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run object detection."""
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            # Get model
            model = db.query(Model).filter(Model.id == validated.model_id).first()
            if not model:
                raise ValueError(f"Model {validated.model_id} not found")
            
            # Get input sources from DIRECT parent nodes only
            input_data = []
            dependency_outputs = context.get('_dependency_outputs', {})
            
            for dep_id, dep_output in dependency_outputs.items():
                if 'input_sources' in dep_output:
                    parent_sources = dep_output['input_sources']
                    if isinstance(parent_sources, list):
                        input_data.extend(parent_sources)
                    else:
                        input_data.append(parent_sources)
            
            if not input_data:
                input_data = context.get('input_sources', [])
            
            if not input_data:
                raise ValueError("No input sources found from parent nodes or context")
            
            actual_context = context.get('_context', context)
            creator_id = actual_context.get('creator_id')

            campaign_id = None
            
            # Check for campaign_id from parent nodes
            for dep_id, dep_output in dependency_outputs.items():
                if 'campaign_id' in dep_output:
                    campaign_id = dep_output['campaign_id']
                    logger.info(f"Detection node {node_id}: Found campaign {campaign_id} from parent node {dep_id}")
                    break
            
            # Check global context
            if not campaign_id:
                if 'campaign_id' in actual_context:
                    campaign_id = actual_context['campaign_id']
                    logger.info(f"Detection node {node_id}: Found campaign {campaign_id} from global context")
            
            # Check campaign_mode configuration
            if not campaign_id:
                if validated.campaign_mode == "existing" and validated.campaign_id:
                    campaign_id = validated.campaign_id
                    from app.models.campaign import Campaign
                    existing_session = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                    if not existing_session:
                        logger.warning(f"Detection node {node_id}: Campaign {campaign_id} not found")
                        campaign_id = None
                
                elif validated.campaign_mode == "new":
                    playbook_id = actual_context.get('playbook_id')
                    from app.models.campaign import Campaign, CampaignStatus
                    campaign = Campaign(
                        name=validated.campaign_name or f"Workflow Session {datetime.now(timezone.utc).isoformat()}",
                        description=validated.campaign_description or "",
                        playbook_id=playbook_id,
                        creator_id=creator_id,
                        status=CampaignStatus.ACTIVE,
                        summary_json={}
                    )
                    db.add(campaign)
                    db.commit()
                    db.refresh(campaign)
                    campaign_id = campaign.id
                    logger.info(f"Detection node {node_id}: Created new campaign {campaign_id}")
            
            # Determine mode and source type
            mode = PredictionMode.BATCH if len(input_data) > 1 else PredictionMode.SINGLE
            source_type = "image"
            source_ref = input_data[0] if input_data else ""
            
            if source_ref:
                if source_ref.startswith("rtsp://"):
                    source_type = "rtsp"
                elif source_ref.startswith("webcam:"):
                    source_type = "webcam"
                elif source_ref.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    source_type = "video"
            
            # Create prediction job
            prediction_job = PredictionJob(
                model_id=model.id,
                mode=mode,
                source_type=source_type,
                source_ref=source_ref,
                status=PredictionStatus.PENDING,
                progress=0,
                summary_json={},
                campaign_id=campaign_id,
                creator_id=creator_id or 1
            )
            db.add(prediction_job)
            db.commit()
            db.refresh(prediction_job)
            
            logger.info(f"Detection node {node_id}: Created prediction job {prediction_job.id} with campaign_id={campaign_id}")

            # Copy input files to prediction job directory using reusable function
            image_paths = []
            for file_path_str in input_data:
                try:
                    copied_path = save_prediction_image(file_path_str, prediction_job.id)
                    image_paths.append(copied_path)
                    logger.info(f"Copied {Path(file_path_str).name} to prediction job directory")
                except (FileNotFoundError, ValueError) as e:
                    logger.warning(f"Skipping file {file_path_str}: {e}")
                    continue
            
            if not image_paths:
                raise ValueError("No valid input files found")
            
            # Start prediction
            prediction_worker.start_batch_prediction(
                job_id=prediction_job.id,
                model_path=model.artifact_path,
                image_paths=image_paths,
                task_type=validated.task_type.value,
                confidence=validated.confidence_threshold,
                class_filter=validated.class_filter
            )
            
            logger.info(f"Started prediction job {prediction_job.id} for node {node_id}")
            
            # Wait for completion
            max_wait_time = 300
            poll_interval = 0.5
            elapsed = 0
            
            while elapsed < max_wait_time:
                db.refresh(prediction_job)
                
                if prediction_job.status == PredictionStatus.COMPLETED.value:
                    results = db.query(PredictionResult).filter(
                        PredictionResult.prediction_job_id == prediction_job.id
                    ).all()
                    
                    # Build results
                    results_data = []
                    image_urls = []
                    total_detections = 0
                    class_counts = {}
                    
                    for result in results:
                        detection_count = len(result.boxes_json) if result.boxes_json else 0
                        total_detections += detection_count
                        
                        if result.class_names_json:
                            for class_name in result.class_names_json:
                                class_counts[class_name] = class_counts.get(class_name, 0) + 1
                        
                        image_url = f"/data/predictions/{prediction_job.id}/{result.file_name}"
                        image_urls.append(image_url)
                        
                        results_data.append({
                            "id": result.id,
                            "file_name": result.file_name,
                            "image_url": image_url,
                            "task_type": result.task_type,
                            "detection_count": detection_count,
                            "boxes": result.boxes_json or [],
                            "scores": result.scores_json or [],
                            "classes": result.classes_json or [],
                            "class_names": result.class_names_json or [],
                            "top_class": result.top_class,
                            "top_confidence": result.top_confidence
                        })
                    
                    # Handle post-processing
                    post_process_action = None
                    input_mode = None
                    output_folder = None
                    
                    for dep_id, dep_output in dependency_outputs.items():
                        if 'post_process_action' in dep_output and dep_output['post_process_action']:
                            post_process_action = dep_output['post_process_action']
                            input_mode = dep_output.get('input_mode')
                            output_folder = dep_output.get('output_folder')
                            break
                    
                    if post_process_action and input_mode in ["folder_images", "folder_videos"]:
                        workflow_id = actual_context.get('workflow_id')
                        if workflow_id:
                            self._handle_post_processing(
                                db=db,
                                post_action=post_process_action,
                                input_sources=input_data,
                                successful_files=[r.file_name for r in results],
                                output_folder=output_folder,
                                creator_id=creator_id,
                                workflow_id=workflow_id
                            )
                    
                    return {
                        "job_id": prediction_job.id,
                        "job_type": "prediction",
                        "model_id": model.id,
                        "campaign_id": prediction_job.campaign_id,
                        "mode": mode.value,
                        "status": "completed",
                        "result_count": len(results),
                        "results": results_data,
                        "image_urls": image_urls,
                        "summary": {
                            "total_detections": total_detections,
                            "class_distribution": class_counts,
                            "average_confidence": prediction_job.summary_json.get("average_confidence", 0) if prediction_job.summary_json else 0
                        }
                    }
                
                elif prediction_job.status == PredictionStatus.FAILED.value:
                    raise RuntimeError(f"Prediction job failed: {prediction_job.error_message}")
                
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            raise TimeoutError(f"Prediction job did not complete within {max_wait_time} seconds")
            
        except Exception as e:
            logger.error(f"Detection node {node_id} failed: {str(e)}")
            raise
        finally:
            db.close()
