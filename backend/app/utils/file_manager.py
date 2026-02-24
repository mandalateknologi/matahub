"""
File Management Utilities
Handles file uploads, validation, and path management for workflows
"""
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

# Maximum file size: 100MB for images, 500MB for videos
MAX_IMAGE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove directory paths
    filename = os.path.basename(filename)
    
    # Remove any dangerous characters, keep only alphanumeric, dots, dashes, underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Prevent hidden files
    if filename.startswith('.'):
        filename = 'file_' + filename
    
    # Ensure filename is not empty
    if not filename or filename == '.':
        filename = 'unnamed_file'
    
    return filename


def get_file_extension(filename: str) -> str:
    """
    Get file extension in lowercase.
    
    Args:
        filename: Filename with extension
    
    Returns:
        Lowercase extension including dot (e.g., '.jpg')
    """
    return Path(filename).suffix.lower()


def validate_file_type(filename: str, allowed_extensions: Optional[List[str]] = None) -> bool:
    """
    Validate file type based on extension.
    
    Args:
        filename: Filename to validate
        allowed_extensions: List of allowed extensions (e.g., ['.jpg', '.png'])
                          If None, uses default ALLOWED_EXTENSIONS
    
    Returns:
        True if file type is allowed
    """
    ext = get_file_extension(filename)
    
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    else:
        allowed_extensions = {e.lower() for e in allowed_extensions}
    
    return ext in allowed_extensions


def is_image_file(filename: str) -> bool:
    """Check if file is an image."""
    return get_file_extension(filename) in ALLOWED_IMAGE_EXTENSIONS


def is_video_file(filename: str) -> bool:
    """Check if file is a video."""
    return get_file_extension(filename) in ALLOWED_VIDEO_EXTENSIONS


def validate_file_size(file_size: int, filename: str) -> bool:
    """
    Validate file size based on type.
    
    Args:
        file_size: Size in bytes
        filename: Filename to determine type
    
    Returns:
        True if size is acceptable
    """
    if is_image_file(filename):
        return file_size <= MAX_IMAGE_SIZE
    elif is_video_file(filename):
        return file_size <= MAX_VIDEO_SIZE
    else:
        return file_size <= MAX_IMAGE_SIZE


def generate_unique_filename(filename: str, destination_dir: Path) -> str:
    """
    Generate unique filename by adding timestamp if file exists.
    
    Args:
        filename: Original filename
        destination_dir: Directory where file will be saved
    
    Returns:
        Unique filename
    """
    sanitized = sanitize_filename(filename)
    file_path = destination_dir / sanitized
    
    # If file doesn't exist, use original
    if not file_path.exists():
        return sanitized
    
    # Add timestamp to make unique
    name_part = Path(sanitized).stem
    ext_part = Path(sanitized).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    unique_name = f"{name_part}_{timestamp}{ext_part}"
    return unique_name


def ensure_upload_directory(user_id: int, workflow_id: int) -> Path:
    """
    Create and return upload directory path for workflow.
    
    Args:
        user_id: User ID
        workflow_id: Workflow ID
    
    Returns:
        Path object for upload directory
    """
    # Structure: {DATA_DIR}/uploads/<user_id>/workflows/<workflow_id>/
    base_dir = Path(settings.DATA_DIR) if settings.DATA_DIR else Path("data")
    upload_dir = base_dir / "uploads" / str(user_id) / "workflows" / str(workflow_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Ensured upload directory exists: {upload_dir}")
    return upload_dir


def get_upload_path(user_id: int, workflow_id: int, filename: str) -> Tuple[Path, str]:
    """
    Get full upload path and relative path for file.
    
    Args:
        user_id: User ID
        workflow_id: Workflow ID
        filename: Original filename
    
    Returns:
        Tuple of (full_path, relative_path)
    """
    upload_dir = ensure_upload_directory(user_id, workflow_id)
    unique_filename = generate_unique_filename(filename, upload_dir)
    
    full_path = upload_dir / unique_filename
    relative_path = str(full_path).replace(os.sep, '/')  # Normalize to forward slashes
    
    return full_path, relative_path


def resolve_file_path(path: str, base_dir: str = ".") -> Path:
    """
    Resolve file path to absolute path.
    
    Args:
        path: Relative or absolute path
        base_dir: Base directory for relative paths
    
    Returns:
        Absolute Path object
    """
    file_path = Path(path)
    
    # If already absolute, return as-is
    if file_path.is_absolute():
        return file_path
    
    # Otherwise resolve relative to base_dir
    resolved = (Path(base_dir) / file_path).resolve()
    return resolved


def validate_file_exists(path: str) -> bool:
    """
    Check if file exists at given path.
    
    Args:
        path: File path to check
    
    Returns:
        True if file exists
    """
    try:
        file_path = Path(path)
        return file_path.exists() and file_path.is_file()
    except Exception as e:
        logger.error(f"Error checking file existence: {e}")
        return False


def delete_workflow_uploads(user_id: int, workflow_id: int) -> bool:
    """
    Delete all uploaded files for a workflow.
    
    Args:
        user_id: User ID
        workflow_id: Workflow ID
    
    Returns:
        True if deletion successful
    """
    try:
        base_dir = Path(settings.DATA_DIR) if settings.DATA_DIR else Path("data")
        upload_dir = base_dir / "uploads" / str(user_id) / "workflows" / str(workflow_id)
        
        if not upload_dir.exists():
            return True
        
        # Delete all files in directory
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
        
        # Remove directory
        upload_dir.rmdir()
        
        logger.info(f"Deleted workflow uploads: {upload_dir}")
        return True
    except Exception as e:
        logger.error(f"Error deleting workflow uploads: {e}")
        return False
