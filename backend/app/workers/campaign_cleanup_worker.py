"""
campaign Cleanup Worker - Monitors and manages inactive video sessions
"""
import threading
import time
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.prediction_job import PredictionJob as DetectionJob, PredictionStatus as DetectionStatus, PredictionMode as DetectionMode


class CampaignCleanupWorker:
    """Worker for monitoring and cleaning up inactive video sessions."""
    
    def __init__(self, check_interval: int = 60, inactivity_threshold: int = 600):
        """
        Initialize campaign cleanup worker.
        
        Args:
            check_interval: How often to check for inactive sessions (seconds)
            inactivity_threshold: Mark campaign inactive after this many seconds (default: 10 minutes)
        """
        self.check_interval = check_interval
        self.inactivity_threshold = inactivity_threshold
        self._running = False
        self._thread = None
    
    def start(self):
        """Start the cleanup worker thread."""
        if self._running:
            print("campaign cleanup worker already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"✓ campaign cleanup worker started (check every {self.check_interval}s, timeout after {self.inactivity_threshold}s)")
    
    def stop(self):
        """Stop the cleanup worker thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("campaign cleanup worker stopped")
    
    def _run(self):
        """Main worker loop."""
        while self._running:
            try:
                self._check_inactive_sessions()
            except Exception as e:
                print(f"Error in campaign cleanup worker: {e}")
            
            # Sleep for check interval
            time.sleep(self.check_interval)
    
    def _check_inactive_sessions(self):
        """Check for and mark inactive video sessions."""
        db = SessionLocal()
        
        try:
            # Find all running manual video sessions
            active_sessions = db.query(DetectionJob).filter(
                DetectionJob.status == DetectionStatus.RUNNING,
                DetectionJob.mode == DetectionMode.VIDEO
            ).all()
            
            now = datetime.now(timezone.utc)
            inactive_count = 0
            
            for job in active_sessions:
                # Skip if not a manual capture campaign
                if not job.summary_json or job.summary_json.get("capture_mode") != "manual":
                    continue
                
                # Check last activity time
                last_activity_str = job.summary_json.get("last_activity")
                if not last_activity_str:
                    continue
                
                try:
                    last_activity = datetime.fromisoformat(last_activity_str)
                    
                    # Calculate inactivity duration
                    if last_activity.tzinfo is None:
                        last_activity = last_activity.replace(tzinfo=timezone.utc)
                    
                    inactive_duration = (now - last_activity).total_seconds()
                    
                    # Mark as inactive if threshold exceeded
                    if inactive_duration > self.inactivity_threshold:
                        # Set inactive flag (don't auto-complete, let user decide)
                        if not job.summary_json.get("inactive_warning_shown"):
                            job.summary_json["inactive_warning_shown"] = True
                            job.summary_json["inactive_since"] = now.isoformat()
                            db.commit()
                            inactive_count += 1
                            print(f"⚠️  Marked video campaign #{job.id} as inactive (idle for {inactive_duration:.0f}s)")
                        
                        # Auto-complete after 1 hour of total inactivity
                        if inactive_duration > 3600:
                            job.status = DetectionStatus.COMPLETED.value
                            job.completed_at = now
                            job.summary_json["auto_completed"] = True
                            job.summary_json["completion_reason"] = "Auto-completed due to prolonged inactivity (1 hour)"
                            db.commit()
                            print(f"✓ Auto-completed video campaign #{job.id} after 1 hour of inactivity")
                
                except (ValueError, TypeError) as e:
                    print(f"Error parsing last_activity for job {job.id}: {e}")
                    continue
            
            if inactive_count > 0:
                print(f"campaign cleanup: {inactive_count} campaign(s) marked inactive")
        
        except Exception as e:
            print(f"Error checking inactive sessions: {e}")
            db.rollback()
        finally:
            db.close()


# Global worker instance
campaign_cleanup_worker = CampaignCleanupWorker(
    check_interval=60,  # Check every 1 minute
    inactivity_threshold=600  # Mark inactive after 10 minutes
)

