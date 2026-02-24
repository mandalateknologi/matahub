"""
Export Results Executor  
Handles result export workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase
from app.workers.export_worker import export_worker
from app.db import SessionLocal
from app.models.export_job import ExportJob, ExportStatus, ExportType
from app.models.prediction_job import PredictionJob

logger = logging.getLogger(__name__)


class ExportResultsExecutor(NodeExecutorBase):
    """Executor for export results nodes."""
    
    def __init__(self):
        super().__init__("export_results")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export prediction results."""
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            # Get prediction job from context
            prediction_job_id = context.get('latest_job_id')
            if not prediction_job_id:
                raise ValueError("No prediction job found in context")
            
            prediction_job = db.query(PredictionJob).filter(PredictionJob.id == prediction_job_id).first()
            if not prediction_job:
                raise ValueError(f"Prediction job {prediction_job_id} not found")
            
            # Map format to export type
            format_map = {
                "json": ExportType.JSON,
                "csv": ExportType.CSV,
                "pdf": ExportType.REPORT_PDF,
                "zip": ExportType.DATA_ZIP
            }
            export_type = format_map.get(validated.format.value, ExportType.JSON)
            
            # Create export job
            export_job = ExportJob(
                prediction_job_id=prediction_job_id,
                export_type=export_type,
                status=ExportStatus.PENDING,
                progress=0.0,
                options_json={
                    "include_images": validated.include_images,
                    "include_metadata": validated.include_metadata
                }
            )
            db.add(export_job)
            db.commit()
            db.refresh(export_job)
            
            # Start export worker
            export_worker.start_export(export_job.id)
            
            logger.info(f"Started export job {export_job.id} for node {node_id}")
            
            return {
                "job_id": export_job.id,
                "job_type": "export",
                "export_type": export_type.value,
                "status": "started"
            }
            
        except Exception as e:
            logger.error(f"Export node {node_id} failed: {str(e)}")
            raise
        finally:
            db.close()
