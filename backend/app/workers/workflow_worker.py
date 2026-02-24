"""
Workflow Worker - Background Workflow Execution
Executes workflows using threading pattern consistent with existing workers
"""
import threading
import traceback
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.workflow import (
    Workflow, WorkflowExecution, WorkflowStepExecution,
    WorkflowStatus, StepStatus
)
from app.models.user_file import UserFile
from app.services.workflow_engine import WorkflowEngine, ContextManager
from app.services.executors import get_executor
from app.services.file_storage_service import FileStorageService
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class WorkflowWorker:
    """Worker for executing workflows in background threads."""
    
    def __init__(self):
        self._active_executions: Dict[int, threading.Thread] = {}
        self._execution_contexts: Dict[int, ContextManager] = {}
    
    def start_execution(
        self,
        execution_id: int,
        workflow_id: int,
        trigger_data: Dict[str, Any],
        creator_id: int,
    ) -> None:
        """
        Start workflow execution in background thread.
        
        Args:
            execution_id: WorkflowExecution ID
            workflow_id: Workflow ID
            trigger_data: Data from trigger
            creator_id: User who triggered execution
        """
        if execution_id in self._active_executions:
            logger.warning(f"Execution {execution_id} already running")
            return
        
        thread = threading.Thread(
            target=self._run_workflow,
            args=(execution_id, workflow_id, trigger_data, creator_id),
            daemon=True
        )
        self._active_executions[execution_id] = thread
        thread.start()
        logger.info(f"Started workflow execution {execution_id}")
    
    def cancel_execution(self, execution_id: int) -> bool:
        """
        Cancel running execution.
        
        Args:
            execution_id: WorkflowExecution ID
        
        Returns:
            True if cancellation initiated, False if not running
        """
        if execution_id not in self._active_executions:
            return False
        
        # Mark as cancelled in database
        db = SessionLocal()
        try:
            execution = db.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).first()
            if execution:
                execution.status = WorkflowStatus.CANCELLED
                execution.completed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Cancelled workflow execution {execution_id}")
                return True
        finally:
            db.close()
        
        return False
    
    def _run_workflow(
        self,
        execution_id: int,
        workflow_id: int,
        trigger_data: Dict[str, Any],
        creator_id: int,
    ) -> None:
        """
        Execute workflow in background.
        
        Args:
            execution_id: WorkflowExecution ID
            workflow_id: Workflow ID
            trigger_data: Data from trigger
            creator_id: User who triggered
        """
        db = SessionLocal()
        start_time = time.time()
        
        try:
            # Load workflow
            workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            # Update execution status
            execution = db.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).first()
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
            
            execution.status = WorkflowStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            db.commit()
            
            # Create execution output folder in File Management
            output_folder = None
            try:
                file_storage = FileStorageService(db)
                # Ensure workflows/{workflow_id}/executions/ parent folder exists
                try:
                    file_storage.create_folder(
                        user_id=creator_id,
                        folder_name="executions",
                        parent_path=f"workflows/{workflow_id}"
                    )
                except Exception:
                    # Parent folder may already exist, ignore
                    pass
                
                # Create workflows/{workflow_id}/executions/{execution_id}/ folder
                file_storage.create_folder(
                    user_id=creator_id,
                    folder_name=str(execution_id),
                    parent_path=f"workflows/{workflow_id}/executions"
                )
                output_folder = f"workflows/{workflow_id}/executions/{execution_id}"
                logger.info(f"Created execution output folder: {output_folder}")
            except Exception as folder_error:
                # Log but don't fail execution if folder creation fails
                logger.warning(f"Failed to create execution output folder: {folder_error}")
            
            # Initialize context
            context_mgr = ContextManager({
                'creator_id': creator_id,
                'workflow_id': workflow_id,
                'execution_id': execution_id,
                'trigger_data': trigger_data,
                'output_folder': output_folder  # Add output folder to context
            })
            self._execution_contexts[execution_id] = context_mgr
            
            # Initialize workflow engine
            engine = WorkflowEngine(workflow.nodes, workflow.edges)
            
            # Validate workflow
            is_valid, error_msg = engine.validate_workflow()
            if not is_valid:
                raise ValueError(f"Invalid workflow: {error_msg}")
            
            # Get execution order
            execution_order = engine.topological_sort()
            total_steps = len(execution_order)
            completed_steps = 0
            failed_nodes: Set[str] = set()
            
            logger.info(f"Executing workflow {workflow_id} with {total_steps} steps")
            
            # Execute nodes in order
            for node_id in execution_order:
                # Check for cancellation
                db.refresh(execution)
                if execution.status == WorkflowStatus.CANCELLED:
                    logger.info(f"Execution {execution_id} cancelled by user")
                    break
                
                # Check timeout
                if time.time() - start_time > settings.WORKFLOW_MAX_EXECUTION_TIME:
                    raise TimeoutError(f"Execution exceeded {settings.WORKFLOW_MAX_EXECUTION_TIME}s limit")
                
                # Check if node should be skipped
                should_skip, skip_reason = engine.should_skip_node(
                    node_id, 
                    context_mgr.to_dict(), 
                    failed_nodes
                )
                
                node = engine.nodes[node_id]
                node_type = node['type']
                
                # Create step execution record
                step_execution = WorkflowStepExecution(
                    execution_id=execution_id,
                    node_id=node_id,
                    node_type=node_type,
                    status=StepStatus.SKIPPED if should_skip else StepStatus.PENDING,
                    input_data={},
                    output_data={}
                )
                db.add(step_execution)
                db.commit()
                db.refresh(step_execution)
                
                if should_skip:
                    logger.info(f"Skipping node {node_id}: {skip_reason}")
                    completed_steps += 1
                    continue
                
                # Execute node
                try:
                    self._execute_node(
                        db=db,
                        step_execution=step_execution,
                        engine=engine,
                        node_id=node_id,
                        context_mgr=context_mgr
                    )
                    completed_steps += 1
                    
                except Exception as node_error:
                    logger.error(f"Node {node_id} failed: {str(node_error)}")
                    failed_nodes.add(node_id)
                    
                    # Update step execution
                    step_execution.status = StepStatus.FAILED
                    step_execution.error_message = str(node_error)
                    step_execution.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    # Check if workflow should continue
                    # For now, fail entire workflow on any node failure
                    raise
                
                # Update progress
                progress = int((completed_steps / total_steps) * 100)
                execution.progress = progress
                execution.context = context_mgr.to_dict()
                db.commit()
            
            # Mark execution as completed
            execution.status = WorkflowStatus.COMPLETED
            execution.progress = 100
            execution.completed_at = datetime.now(timezone.utc)
            execution.context = context_mgr.to_dict()
            db.commit()
            
            logger.info(f"Workflow execution {execution_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Workflow execution {execution_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            try:
                execution = db.query(WorkflowExecution).filter(
                    WorkflowExecution.id == execution_id
                ).first()
                if execution:
                    execution.status = WorkflowStatus.FAILED
                    execution.error_message = str(e)
                    execution.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to update execution status: {str(commit_error)}")
        
        finally:
            db.close()
            if execution_id in self._active_executions:
                del self._active_executions[execution_id]
            if execution_id in self._execution_contexts:
                del self._execution_contexts[execution_id]
    
    def _execute_node(
        self,
        db: Session,
        step_execution: WorkflowStepExecution,
        engine: WorkflowEngine,
        node_id: str,
        context_mgr: ContextManager
    ) -> None:
        """
        Execute a single workflow node.
        
        Args:
            db: Database session
            step_execution: Step execution record
            engine: Workflow engine
            node_id: Node ID to execute
            context_mgr: Context manager
        """
        node = engine.nodes[node_id]
        node_type = node['type']
        node_config = node['data'].get('config', {})
        
        # Update step status
        step_execution.status = StepStatus.RUNNING
        step_execution.started_at = datetime.now(timezone.utc)
        
        # Get node input with dependency outputs
        node_input = engine.get_node_input(node_id, context_mgr.to_dict())
        step_execution.input_data = node_input
        db.commit()
        
        logger.info(f"Executing node {node_id} (type: {node_type})")
        
        # Get executor for node type
        executor = get_executor(node_type)
        if not executor:
            # Node types without executors (triggers, output) just pass through
            logger.info(f"No executor for {node_type}, skipping")
            step_execution.status = StepStatus.COMPLETED
            step_execution.output_data = {"status": "skipped"}
            step_execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        
        # Execute node with full input data (includes _dependency_outputs)
        output_data = executor.execute(
            node_id=node_id,
            config=node_config,
            context=node_input  # Pass node_input instead of raw context
        )
        
        # Handle async operations (training, detection, export)
        if 'job_id' in output_data and 'job_type' in output_data:
            job_id = output_data['job_id']
            job_type = output_data['job_type']
            
            # Store job reference
            step_execution.job_id = job_id
            step_execution.job_type = job_type
            db.commit()
            
            # Wait for job completion
            self._wait_for_job_completion(db, job_id, job_type, step_execution)
        
        # Update step execution
        step_execution.status = StepStatus.COMPLETED
        step_execution.output_data = output_data
        step_execution.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        # Merge output into context
        context_mgr.update(engine.merge_context(
            context_mgr.to_dict(),
            output_data,
            node_id
        ))
        
        logger.info(f"Node {node_id} completed successfully")
    
    def _wait_for_job_completion(
        self,
        db: Session,
        job_id: int,
        job_type: str,
        step_execution: WorkflowStepExecution
    ) -> None:
        """
        Wait for async job to complete.
        
        Args:
            db: Database session
            job_id: Job ID
            job_type: Job type (training, detection, export)
            step_execution: Step execution record
        """
        from app.models.training_job import TrainingJob, TrainingStatus
        from app.models.prediction_job import PredictionJob as DetectionJob, PredictionStatus as DetectionStatus
        from app.models.export_job import ExportJob, ExportStatus
        
        logger.info(f"Waiting for {job_type} job {job_id} to complete")
        
        # Poll job status
        max_wait_time = settings.WORKFLOW_MAX_EXECUTION_TIME
        poll_interval = 5  # 5 seconds
        waited = 0
        
        while waited < max_wait_time:
            time.sleep(poll_interval)
            waited += poll_interval
            
            # Refresh database connection
            db.expire_all()
            
            # Check job status
            job = None
            is_complete = False
            is_failed = False
            
            if job_type == "training":
                job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
                if job:
                    is_complete = job.status == TrainingStatus.COMPLETED
                    is_failed = job.status == TrainingStatus.FAILED
            
            elif job_type == "prediction":
                job = db.query(DetectionJob).filter(DetectionJob.id == job_id).first()
                if job:
                    is_complete = job.status == DetectionStatus.COMPLETED
                    is_failed = job.status == DetectionStatus.FAILED
            
            elif job_type == "export":
                job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
                if job:
                    is_complete = job.status == ExportStatus.COMPLETED
                    is_failed = job.status == ExportStatus.FAILED
            
            if is_complete:
                logger.info(f"{job_type} job {job_id} completed")
                return
            
            if is_failed:
                error_msg = getattr(job, 'error_message', 'Unknown error')
                raise RuntimeError(f"{job_type} job {job_id} failed: {error_msg}")
            
            # Log progress
            if job and hasattr(job, 'progress'):
                logger.debug(f"{job_type} job {job_id} progress: {job.progress}")
        
        raise TimeoutError(f"{job_type} job {job_id} did not complete within {max_wait_time}s")
    
    def get_execution_status(self, execution_id: int) -> Optional[Dict[str, Any]]:
        """Get current execution status."""
        if execution_id not in self._active_executions:
            return None
        
        context = self._execution_contexts.get(execution_id)
        return {
            "is_running": True,
            "context": context.to_dict() if context else {}
        }
    
    def cleanup_old_execution_folders(
        self,
        workflow_id: int,
        user_id: int,
        retention_count: int = 30
    ) -> Dict[str, Any]:
        """
        Clean up old execution folders, keeping only the most recent ones.
        Moves old folders to trash instead of permanent deletion.
        
        Args:
            workflow_id: Workflow ID to clean up
            user_id: User ID for file operations
            retention_count: Number of recent execution folders to keep (default: 30)
            
        Returns:
            Dictionary with cleanup statistics
        """
        db = SessionLocal()
        try:
            file_storage = FileStorageService(db, user_id)
            
            # Get all execution folders for this workflow
            executions_parent = f"workflows/{workflow_id}/executions"
            try:
                parent_folder = file_storage.get_file(executions_parent)
                if not parent_folder:
                    return {"deleted": 0, "kept": 0, "message": "No execution folders found"}
                
                # List all execution subfolders
                all_files = db.query(UserFile).filter(
                    UserFile.user_id == user_id,
                    UserFile.folder_path.like(f"{executions_parent}/%"),
                    UserFile.file_type == "folder",
                    UserFile.deleted_at.is_(None)
                ).all()
                
                # Filter to only direct children (execution_id folders)
                execution_folders = [
                    f for f in all_files
                    if f.folder_path.count("/") == executions_parent.count("/") + 1
                ]
                
                # Sort by created_at descending (newest first)
                execution_folders.sort(key=lambda x: x.created_at, reverse=True)
                
                # Keep retention_count most recent, delete the rest
                folders_to_keep = execution_folders[:retention_count]
                folders_to_delete = execution_folders[retention_count:]
                
                deleted_count = 0
                for folder in folders_to_delete:
                    try:
                        # Soft delete (move to trash)
                        file_storage.delete_file(folder.folder_path, permanent=False)
                        deleted_count += 1
                        logger.info(f"Moved old execution folder to trash: {folder.folder_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete folder {folder.folder_path}: {str(e)}")
                
                return {
                    "deleted": deleted_count,
                    "kept": len(folders_to_keep),
                    "message": f"Cleaned up {deleted_count} old execution folders, kept {len(folders_to_keep)}"
                }
                
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
                return {"deleted": 0, "kept": 0, "error": str(e)}
                
        finally:
            db.close()


# Singleton instance
workflow_worker = WorkflowWorker()
