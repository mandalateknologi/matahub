"""
ATVISION Configuration Settings
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "ATVISION"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql://atvision:atvision@localhost:5432/atvision"
    
    # Authentication
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # File Upload Limits (in bytes)
    MAX_DATASET_SIZE: int = 500 * 1024 * 1024  # 500MB
    MAX_IMAGE_SIZE: int = 100 * 1024 * 1024    # 100MB
    MAX_VIDEO_SIZE: int = 2 * 1024 * 1024 * 1024  # 2GB
    
    # User Storage Limits
    MAX_USER_STORAGE_SIZE: int = 50 * 1024 * 1024 * 1024  # 50GB per user (increased for workflow-heavy usage)
    
    # Storage Paths
    # Loaded from .env, fallback to computed path if not set
    DATA_DIR: str = ""
    
    def model_post_init(self, __context):
        """Called after model initialization to set defaults."""
        # If DATA_DIR not set in .env, compute it
        if not self.DATA_DIR:
            computed_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
            self.DATA_DIR = computed_path
        else:
            # Remove trailing slash if present
            self.DATA_DIR = self.DATA_DIR.rstrip('/\\')
    
    @property
    def datasets_dir(self) -> str:
        path = os.path.join(self.DATA_DIR, "datasets")
        os.makedirs(path, exist_ok=True)
        return path
    
    @property
    def models_dir(self) -> str:
        path = os.path.join(self.DATA_DIR, "models")
        os.makedirs(path, exist_ok=True)
        return path
    
    @property
    def predictions_dir(self) -> str:
        path = os.path.join(self.DATA_DIR, "predictions")
        os.makedirs(path, exist_ok=True)
        return path
    
    @property
    def uploads_dir(self) -> str:
        if not self.DATA_DIR:
            raise ValueError("DATA_DIR is not configured!")
        path = os.path.join(self.DATA_DIR, "uploads")
        os.makedirs(path, exist_ok=True)
        return path
    
    # YOLO Settings
    YOLO_BASE_MODELS: List[str] = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"]
    DEFAULT_YOLO_MODEL: str = "yolov8n"
    YOLO_DEVICE: str = "auto"  # "auto", "cpu", "0" (GPU 0), "1" (GPU 1), etc.
    
    # Cleanup Settings
    PREDICTION_RETENTION_DAYS: int = 30
    TRASH_RETENTION_DAYS: int = 30  # Days before permanent deletion from trash
    
    # Manual Session Management
    MANUAL_SESSION_TIMEOUT_MINUTES: int = 60  # Auto-cancel inactive manual sessions after 1 hour
    SESSION_HEARTBEAT_INTERVAL_SECONDS: int = 30  # Expected heartbeat interval from frontend
    CLEANUP_CHECK_INTERVAL_SECONDS: int = 300  # Check for inactive sessions every 5 minutes
    
    # Session Export Settings
    SESSION_EXPORT_TIMEOUT: int = 3600  # 1 hour for mega-report generation
    
    # Email/SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "ATVISION Workflows"
    SMTP_USE_TLS: bool = True
    EMAIL_RATE_LIMIT: int = 10  # Max emails per hour per workflow
    
    # Workflow Settings
    WORKFLOW_MAX_EXECUTION_TIME: int = 7200  # 2 hours max execution time
    WORKFLOW_POLL_INTERVAL: int = 2  # Seconds between status checks
    
    # Workflow API Rate Limiting
    WORKFLOW_API_RATE_LIMIT_PER_MINUTE: int = 60  # Max API calls per minute per workflow
    WORKFLOW_API_RATE_LIMIT_PER_HOUR: int = 500  # Max API calls per hour per workflow
    WORKFLOW_API_CONCURRENT_EXECUTIONS: int = 5  # Max concurrent workflow executions
    
    # External Inference API Rate Limiting
    EXTERNAL_INFERENCE_RATE_LIMIT_PER_HOUR: int = 100  # Max external API calls per hour per user
    
    # Scheduler Settings
    SCHEDULER_TIMEZONE: str = "UTC"
    SCHEDULER_JOBSTORE_URL: str = ""  # Optional: URL for persistent job store
    
    def get_device(self) -> str:
        """
        Get the device to use for YOLO operations.
        
        Returns:
            Device string: "0" for GPU, "cpu" for CPU
        """
        if self.YOLO_DEVICE == "auto":
            try:
                import torch
                return "0" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return self.YOLO_DEVICE
    
    class Config:
        # Look for .env in project root (one level up from backend/)
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        env_file_encoding = "utf-8"


settings = Settings()
