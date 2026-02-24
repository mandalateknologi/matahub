"""
Scheduler Service - APScheduler integration for workflow cron triggers
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled workflow executions."""
    
    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
    
    def start(self):
        """Start the scheduler."""
        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler already running")
            return
        
        # Configure jobstore
        jobstores = {
            'default': MemoryJobStore()
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=settings.SCHEDULER_TIMEZONE
        )
        
        self.scheduler.start()
        logger.info(f"✅ Scheduler started (timezone: {settings.SCHEDULER_TIMEZONE})")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    
    def add_workflow_schedule(
        self,
        workflow_id: int,
        cron_expression: str,
        timezone: Optional[str] = None
    ) -> str:
        """
        Add scheduled workflow execution.
        
        Args:
            workflow_id: Workflow ID
            cron_expression: Cron expression (e.g., "0 0 * * *")
            timezone: Optional timezone override
        
        Returns:
            Job ID for cleanup
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not started")
        
        # Parse cron expression
        # Format: minute hour day month day_of_week
        parts = cron_expression.strip().split()
        if len(parts) not in [5, 6]:
            raise ValueError("Invalid cron expression")
        
        # Create trigger
        trigger = CronTrigger.from_crontab(
            cron_expression,
            timezone=timezone or settings.SCHEDULER_TIMEZONE
        )
        
        # Add job
        job = self.scheduler.add_job(
            func=self._execute_scheduled_workflow,
            trigger=trigger,
            args=[workflow_id],
            id=f"workflow_{workflow_id}",
            replace_existing=True,
            name=f"Workflow {workflow_id}"
        )
        
        logger.info(f"Added schedule for workflow {workflow_id}: {cron_expression}")
        return job.id
    
    def remove_workflow_schedule(self, job_id: str) -> bool:
        """
        Remove scheduled workflow.
        
        Args:
            job_id: Job ID from add_workflow_schedule
        
        Returns:
            True if removed, False if not found
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed schedule: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove schedule {job_id}: {str(e)}")
            return False
    
    def update_workflow_schedule(
        self,
        workflow_id: int,
        old_job_id: Optional[str],
        cron_expression: str,
        timezone: Optional[str] = None
    ) -> str:
        """
        Update workflow schedule.
        
        Args:
            workflow_id: Workflow ID
            old_job_id: Previous job ID (if exists)
            cron_expression: New cron expression
            timezone: Optional timezone
        
        Returns:
            New job ID
        """
        # Remove old schedule
        if old_job_id:
            self.remove_workflow_schedule(old_job_id)
        
        # Add new schedule
        return self.add_workflow_schedule(workflow_id, cron_expression, timezone)
    
    def _execute_scheduled_workflow(self, workflow_id: int):
        """
        Execute workflow on schedule.
        
        Args:
            workflow_id: Workflow ID to execute
        """
        from app.db import SessionLocal
        from app.models.workflow import Workflow, WorkflowExecution, WorkflowStatus, WorkflowTriggerType
        from app.workers.workflow_worker import workflow_worker
        
        db = SessionLocal()
        try:
            # Load workflow
            workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                logger.error(f"Scheduled workflow {workflow_id} not found")
                return
            
            # Check if active
            if not workflow.is_active:
                logger.info(f"Skipping inactive workflow {workflow_id}")
                return
            
            # Create execution
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                status=WorkflowStatus.PENDING,
                trigger_type=WorkflowTriggerType.SCHEDULE,
                trigger_data={"scheduled": True},
                context={},
                progress=0
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)
            
            # Start execution
            workflow_worker.start_execution(
                execution_id=execution.id,
                workflow_id=workflow_id,
                trigger_data={"scheduled": True},
                creator_id=workflow.creator_id,
                project_id=workflow.project_id
            )
            
            logger.info(f"Triggered scheduled execution {execution.id} for workflow {workflow_id}")
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled workflow {workflow_id}: {str(e)}")
        finally:
            db.close()
    
    def restore_schedules(self):
        """
        Restore schedules from database on startup.
        Should be called after scheduler.start()
        """
        from app.db import SessionLocal
        from app.models.workflow import Workflow, WorkflowTriggerType
        
        db = SessionLocal()
        try:
            # Find all scheduled workflows
            scheduled_workflows = db.query(Workflow).filter(
                Workflow.is_active == True,
                Workflow.trigger_type == WorkflowTriggerType.SCHEDULE
            ).all()
            
            restored_count = 0
            for workflow in scheduled_workflows:
                try:
                    # Get cron expression from trigger_config
                    cron_expr = workflow.trigger_config.get('cron_expression')
                    timezone = workflow.trigger_config.get('timezone', settings.SCHEDULER_TIMEZONE)
                    
                    if not cron_expr:
                        logger.warning(f"Workflow {workflow.id} has no cron expression")
                        continue
                    
                    # Add schedule
                    job_id = self.add_workflow_schedule(
                        workflow_id=workflow.id,
                        cron_expression=cron_expr,
                        timezone=timezone
                    )
                    
                    # Update scheduler_job_id in database
                    workflow.scheduler_job_id = job_id
                    db.commit()
                    
                    restored_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to restore schedule for workflow {workflow.id}: {str(e)}")
            
            logger.info(f"✅ Restored {restored_count} workflow schedules")
            
        except Exception as e:
            logger.error(f"Failed to restore schedules: {str(e)}")
        finally:
            db.close()
    
    def get_job_info(self, job_id: str) -> Optional[dict]:
        """Get information about a scheduled job."""
        if not self.scheduler:
            return None
        
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time,
                    'trigger': str(job.trigger)
                }
        except Exception as e:
            logger.warning(f"Failed to get job info for {job_id}: {str(e)}")
        
        return None


# Singleton instance
scheduler_service = SchedulerService()
