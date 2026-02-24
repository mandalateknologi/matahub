"""
Workflow API Rate Limiter - In-memory token bucket implementation
"""
from collections import defaultdict
from datetime import datetime, timedelta
import threading
from typing import Dict, List
import os


class WorkflowRateLimiter:
    """
    In-memory rate limiter for workflow API calls.
    Uses token bucket algorithm with automatic cleanup.
    """
    
    def __init__(self):
        self._calls: Dict[int, List[datetime]] = defaultdict(list)  # user_id -> [timestamps]
        self._lock = threading.Lock()
        self._cleanup_interval = timedelta(minutes=5)
        self._last_cleanup = datetime.utcnow()
    
    def check_limit(
        self,
        user_id: int,
        limit_per_minute: int = None,
        limit_per_hour: int = None
    ) -> tuple[bool, dict]:
        """
        Check if user has exceeded rate limits.
        
        Args:
            user_id: User ID to check
            limit_per_minute: Max calls per minute (defaults to env)
            limit_per_hour: Max calls per hour (defaults to env)
        
        Returns:
            (allowed: bool, headers: dict) - Allowed status and rate limit headers
        """
        with self._lock:
            now = datetime.utcnow()
            
            # Get limits from env if not provided
            if limit_per_minute is None:
                limit_per_minute = int(os.getenv("WORKFLOW_API_RATE_LIMIT_PER_MINUTE", "60"))
            if limit_per_hour is None:
                limit_per_hour = int(os.getenv("WORKFLOW_API_RATE_LIMIT_PER_HOUR", "500"))
            
            # Clean old entries for this user
            minute_cutoff = now - timedelta(minutes=1)
            hour_cutoff = now - timedelta(hours=1)
            
            self._calls[user_id] = [
                ts for ts in self._calls[user_id] if ts > hour_cutoff
            ]
            
            # Count recent calls
            calls_last_minute = sum(1 for ts in self._calls[user_id] if ts > minute_cutoff)
            calls_last_hour = len(self._calls[user_id])
            
            # Check limits
            minute_remaining = max(0, limit_per_minute - calls_last_minute)
            hour_remaining = max(0, limit_per_hour - calls_last_hour)
            
            allowed = calls_last_minute < limit_per_minute and calls_last_hour < limit_per_hour
            
            # Add timestamp if allowed
            if allowed:
                self._calls[user_id].append(now)
            
            # Prepare headers
            headers = {
                "X-RateLimit-Limit-Minute": str(limit_per_minute),
                "X-RateLimit-Limit-Hour": str(limit_per_hour),
                "X-RateLimit-Remaining-Minute": str(minute_remaining),
                "X-RateLimit-Remaining-Hour": str(hour_remaining),
            }
            
            if not allowed:
                # Calculate retry-after based on oldest call in minute window
                if calls_last_minute >= limit_per_minute:
                    oldest_in_minute = min(ts for ts in self._calls[user_id] if ts > minute_cutoff)
                    retry_after = int((oldest_in_minute + timedelta(minutes=1) - now).total_seconds())
                else:
                    # Hour limit exceeded
                    oldest_in_hour = min(self._calls[user_id])
                    retry_after = int((oldest_in_hour + timedelta(hours=1) - now).total_seconds())
                
                headers["Retry-After"] = str(max(1, retry_after))
            
            # Periodic cleanup
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_old_entries()
                self._last_cleanup = now
            
            return allowed, headers
    
    def _cleanup_old_entries(self):
        """Remove entries older than 1 hour (must be called with lock)."""
        hour_cutoff = datetime.utcnow() - timedelta(hours=1)
        
        # Remove old timestamps
        for user_id in list(self._calls.keys()):
            self._calls[user_id] = [
                ts for ts in self._calls[user_id] if ts > hour_cutoff
            ]
            # Remove user if no recent calls
            if not self._calls[user_id]:
                del self._calls[user_id]
    
    def reset_user(self, user_id: int):
        """Reset rate limit for a specific user (for testing/admin)."""
        with self._lock:
            if user_id in self._calls:
                del self._calls[user_id]
    
    def get_stats(self, user_id: int = None) -> dict:
        """
        Get rate limiter statistics.
        
        Args:
            user_id: Specific user ID, or None for global stats
        
        Returns:
            Dict with statistics
        """
        with self._lock:
            if user_id is not None:
                now = datetime.utcnow()
                minute_cutoff = now - timedelta(minutes=1)
                hour_cutoff = now - timedelta(hours=1)
                
                user_calls = self._calls.get(user_id, [])
                
                return {
                    "user_id": user_id,
                    "calls_last_minute": sum(1 for ts in user_calls if ts > minute_cutoff),
                    "calls_last_hour": sum(1 for ts in user_calls if ts > hour_cutoff),
                    "total_tracked_calls": len(user_calls)
                }
            else:
                return {
                    "total_users_tracked": len(self._calls),
                    "total_calls_tracked": sum(len(calls) for calls in self._calls.values())
                }


# Global singleton instance
workflow_rate_limiter = WorkflowRateLimiter()
