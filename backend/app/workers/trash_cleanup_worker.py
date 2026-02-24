"""
Trash Cleanup Worker - Automatically deletes old files from trash
"""
import threading
import time

from app.db import SessionLocal
from app.services.file_storage_service import FileStorageService


class TrashCleanupWorker:
    """Worker for automatically cleaning up old files from trash."""
    
    def __init__(self, check_interval: int = 86400):  # 24 hours
        """
        Initialize trash cleanup worker.
        
        Args:
            check_interval: How often to check for old trash files (seconds, default: 24 hours)
        """
        self.check_interval = check_interval
        self._running = False
        self._thread = None
    
    def start(self):
        """Start the cleanup worker thread."""
        if self._running:
            print("Trash cleanup worker already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"✓ Trash cleanup worker started (check every {self.check_interval / 3600:.1f} hours)")
    
    def stop(self):
        """Stop the cleanup worker thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("Trash cleanup worker stopped")
    
    def _run(self):
        """Main worker loop."""
        while self._running:
            try:
                self._cleanup_old_trash()
            except Exception as e:
                print(f"Error in trash cleanup worker: {e}")
            
            # Sleep for check interval
            time.sleep(self.check_interval)
    
    def _cleanup_old_trash(self):
        """Clean up old files from trash."""
        db = SessionLocal()
        
        try:
            file_service = FileStorageService(db)
            deleted_count = file_service.cleanup_old_trash()
            
            if deleted_count > 0:
                print(f"✓ Trash cleanup: permanently deleted {deleted_count} old files")
        except Exception as e:
            print(f"Error during trash cleanup: {e}")
        finally:
            db.close()


# Create global instance
trash_cleanup_worker = TrashCleanupWorker()
