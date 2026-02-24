"""
Utility Functions for Executors
Shared helper functions used across multiple executors.
"""
from pathlib import Path

from app.config import settings


def resolve_fm_path_to_absolute(fm_path: str, user_id: int) -> Path:
    """
    Resolve File Management relative path to absolute filesystem path.
    
    Args:
        fm_path: File Management path (relative like "workflows/5/image.jpg" or absolute)
        user_id: User ID for path construction
    
    Returns:
        Absolute Path object
    
    Examples:
        "workflows/5/image.jpg" -> "/path/to/data/uploads/{user_id}/workflows/5/image.jpg"
        "shared/folder/file.jpg" -> "/path/to/data/uploads/{user_id}/shared/folder/file.jpg"
        "uploads/1/shared/file.jpg" -> "/path/to/data/uploads/1/shared/file.jpg" (already includes user_id)
    """
    # Check if already absolute path (backward compatibility)
    fm_path_obj = Path(fm_path)
    if fm_path_obj.is_absolute():
        return fm_path_obj
    
    # Normalize path separators (convert backslashes to forward slashes)
    fm_path = fm_path.replace('\\', '/')
    
    # Check if path already includes uploads/{user_id} prefix (old format)
    if fm_path.startswith(f"uploads/{user_id}/"):
        # Path already includes user_id, resolve from data root
        return Path(settings.DATA_DIR) / fm_path
    elif fm_path.startswith("uploads/"):
        # Path has uploads/ but different user_id, use as-is from data root
        return Path(settings.DATA_DIR) / fm_path
    
    # File Management relative path - construct full path
    base_dir = Path(settings.uploads_dir) / str(user_id)
    absolute_path = base_dir / fm_path
    
    return absolute_path
