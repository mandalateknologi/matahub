"""
Show Images Executor
Handles image gallery output workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase
from app.db import SessionLocal
from app.models.prediction_job import PredictionJob
from app.models.prediction_result import PredictionResult

logger = logging.getLogger(__name__)


class ShowImagesExecutor(NodeExecutorBase):
    """Executor for show images output nodes."""
    
    def __init__(self):
        super().__init__("show_images")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch and format prediction results for image gallery display."""
        if 'output_type' not in config:
            config['output_type'] = 'show_images'
        
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            job_id = None
            results_data = None
            dependency_outputs = context.get('_dependency_outputs', {})
            
            # Check parent nodes for results
            for dep_id, dep_output in dependency_outputs.items():
                if 'job_id' in dep_output:
                    job_id = dep_output['job_id']
                    break
                elif 'results' in dep_output:
                    results_data = dep_output['results']
                    break
            
            if not job_id and not results_data:
                job_id = context.get('job_id')
                results_data = context.get('results')
            
            if results_data:
                return {
                    "output_type": "show_images",
                    "gallery_mode": True,
                    "result_count": len(results_data),
                    "results": results_data,
                    "summary": context.get('summary', {})
                }
            
            if not job_id:
                raise ValueError("No prediction job or results found from parent nodes")
            
            # Fetch prediction job
            prediction_job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not prediction_job:
                raise ValueError(f"Prediction job {job_id} not found")
            
            # Fetch results
            results = db.query(PredictionResult).filter(
                PredictionResult.prediction_job_id == job_id
            ).all()
            
            # Build gallery data
            gallery_results = []
            total_detections = 0
            class_counts = {}
            task_type = None
            
            for result in results:
                if task_type is None:
                    task_type = result.task_type or "detect"
                
                detection_count = len(result.boxes_json) if result.boxes_json else 0
                total_detections += detection_count
                
                if result.class_names_json:
                    for class_name in result.class_names_json:
                        class_counts[class_name] = class_counts.get(class_name, 0) + 1
                
                result_data = {
                    "id": result.id,
                    "file_name": result.file_name,
                    "task_type": task_type,
                    "detection_count": detection_count
                }
                
                if task_type == "detect":
                    result_data.update({
                        "boxes": result.boxes_json or [],
                        "scores": result.scores_json or [],
                        "classes": result.classes_json or [],
                        "class_names": result.class_names_json or []
                    })
                elif task_type == "classify":
                    result_data.update({
                        "top_class": result.top_class,
                        "top_confidence": result.top_confidence,
                        "top_classes": result.top_classes_json or [],
                        "probabilities": result.probabilities_json or []
                    })
                
                gallery_results.append(result_data)
            
            summary = {
                "total_images": len(results),
                "total_detections": total_detections,
                "class_distribution": class_counts
            }
            
            if prediction_job.summary_json:
                summary["average_confidence"] = prediction_job.summary_json.get("average_confidence", 0)
            
            logger.info(f"Show images node {node_id} prepared {len(results)} results")
            
            return {
                "output_type": "show_images",
                "gallery_mode": True,
                "job_id": job_id,
                "task_type": task_type,
                "result_count": len(results),
                "results": gallery_results,
                "summary": summary,
                "include_statistics": validated.include_statistics
            }
            
        except Exception as e:
            logger.error(f"Show images node {node_id} failed: {str(e)}")
            raise
        finally:
            db.close()
