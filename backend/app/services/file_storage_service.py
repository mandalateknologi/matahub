"""
File Storage Service
Manages user file uploads, storage quota, and file organization.
"""
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import UploadFile, HTTPException, status

from app.config import settings
from app.models.user_file import UserFile
from app.models.user import User
from app.utils.file_handler import validate_image_file, validate_video_file, validate_file_size


class FileStorageService:
    """Service for managing user file storage and organization."""
    
    # System folder names (protected from deletion)
    SYSTEM_FOLDERS = ["workflows", "shared", "trash"]
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def normalize_path(path: Path | str) -> str:
        """
        Normalize path to use forward slashes regardless of OS.
        
        Args:
            path: Path object or string to normalize
            
        Returns:
            String path with forward slashes
        """
        return str(path).replace("\\", "/")
    
    def create_system_folders(self, user_id: int) -> None:
        """
        Create system folders for a new user (workflows, shared, trash).
        Called during user registration.
        
        Args:
            user_id: ID of the user
        """
        user_dir = Path(settings.uploads_dir) / str(user_id)
        
        for folder in self.SYSTEM_FOLDERS:
            folder_path = user_dir / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            
            # Check if folder already tracked in DB
            existing = self.db.query(UserFile).filter(
                UserFile.user_id == user_id,
                UserFile.folder_path == folder,
                UserFile.is_system_folder == True
            ).first()
            
            if not existing:
                # Create DB record for system folder
                system_folder = UserFile(
                    user_id=user_id,
                    file_path=self.normalize_path(folder_path.relative_to(settings.DATA_DIR)),
                    file_name=folder,
                    file_type="folder",
                    file_size=0,
                    folder_path=folder,
                    is_system_folder=True
                )
                self.db.add(system_folder)
        
        self.db.commit()
    
    def calculate_user_storage(self, user_id: int) -> int:
        """
        Calculate total storage used by a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Total storage in bytes
        """
        result = self.db.query(func.sum(UserFile.file_size)).filter(
            UserFile.user_id == user_id,
            UserFile.is_deleted == False,
            UserFile.file_type != "folder"  # Don't count folder entries
        ).scalar()
        
        return result or 0
    
    def validate_storage_quota(self, user_id: int, new_file_size: int) -> None:
        """
        Validate that adding a new file won't exceed user's storage quota.
        Uses transaction-level locking to prevent race conditions.
        
        Args:
            user_id: ID of the user
            new_file_size: Size of file to be added in bytes
            
        Raises:
            HTTPException: If quota would be exceeded
        """
        # Lock user row to prevent concurrent quota checks
        user = self.db.query(User).filter(User.id == user_id).with_for_update().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_usage = self.calculate_user_storage(user_id)
        max_storage = settings.MAX_USER_STORAGE_SIZE
        
        if current_usage + new_file_size > max_storage:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Storage quota exceeded. Used: {current_usage / 1024 / 1024 / 1024:.2f}GB, "
                       f"Available: {(max_storage - current_usage) / 1024 / 1024 / 1024:.2f}GB, "
                       f"Requested: {new_file_size / 1024 / 1024 / 1024:.2f}GB"
            )
    
    def list_user_files(
        self, 
        user_id: int, 
        folder_path: Optional[str] = None,
        include_deleted: bool = False
    ) -> List[UserFile]:
        """
        List files for a user, optionally filtered by folder.
        When folder_path is provided, returns files in that folder AND all subdirectories.
        
        Args:
            user_id: ID of the user
            folder_path: Optional folder path to filter by (includes subdirectories)
            include_deleted: Whether to include deleted files
            
        Returns:
            List of UserFile objects
        """
        query = self.db.query(UserFile).filter(UserFile.user_id == user_id)
        
        if folder_path is not None:
            # Match exact folder OR any subfolder (e.g., "workflows" matches "workflows/2")
            query = query.filter(
                or_(
                    UserFile.folder_path == folder_path,
                    UserFile.folder_path.like(f"{folder_path}/%")
                )
            )
        
        if not include_deleted:
            query = query.filter(UserFile.is_deleted == False)
        
        return query.order_by(UserFile.uploaded_at.desc()).all()
    
    def get_folder_tree(self, user_id: int) -> Dict:
        """
        Build hierarchical folder tree for user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Nested dictionary representing folder structure
        """
        files = self.list_user_files(user_id, include_deleted=False)
        
        tree = {
            "workflows": {"files": [], "subfolders": {}},
            "shared": {"files": [], "subfolders": {}},
            "trash": {"files": [], "subfolders": {}}
        }
        
        for file in files:
            if file.is_system_folder:
                continue
            
            parts = file.folder_path.split("/")
            root = parts[0]
            
            if root not in tree:
                continue
            
            # Navigate to correct subfolder
            current = tree[root]
            for part in parts[1:]:
                if part not in current["subfolders"]:
                    current["subfolders"][part] = {"files": [], "subfolders": {}}
                current = current["subfolders"][part]
            
            current["files"].append({
                "id": file.id,
                "name": file.file_name,
                "type": file.file_type,
                "size": file.file_size,
                "path": file.file_path,
                "uploaded_at": file.uploaded_at.isoformat()
            })
        
        return tree
    
    def upload_file(
        self,
        user_id: int,
        file: UploadFile,
        folder_path: str
    ) -> UserFile:
        """
        Upload a file for a user.
        
        Args:
            user_id: ID of the user
            file: The uploaded file
            folder_path: Destination folder path (must be under "shared" or "workflows")
            
        Returns:
            Created UserFile object
            
        Raises:
            HTTPException: If validation fails or quota exceeded
        """
        # Validate folder path (must be under "shared" or "workflows")
        if not (folder_path.startswith("shared") or folder_path.startswith("workflows")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Files can only be uploaded to 'shared' or 'workflows' folder"
            )
        
        # Validate file type
        filename = file.filename or "unnamed"
        is_image = validate_image_file(filename)
        is_video = validate_video_file(filename)
        
        if not is_image and not is_video:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image and video files are allowed"
            )
        
        file_type = "image" if is_image else "video"
        
        # Validate file size
        max_size = settings.MAX_IMAGE_SIZE if is_image else settings.MAX_VIDEO_SIZE
        validate_file_size(file, max_size)
        
        # Get actual file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        # Validate storage quota with locking
        self.validate_storage_quota(user_id, file_size)
        
        # Create destination path
        user_dir = Path(settings.uploads_dir) / str(user_id)
        dest_folder = user_dir / folder_path
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename if exists
        dest_path = dest_folder / filename
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_path = dest_folder / f"{stem}_{timestamp}{suffix}"
        
        # Save file
        try:
            with dest_path.open("wb") as f:
                shutil.copyfileobj(file.file, f)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # Create DB record
        user_file = UserFile(
            user_id=user_id,
            file_path=self.normalize_path(dest_path.relative_to(settings.DATA_DIR)),
            file_name=dest_path.name,
            file_type=file_type,
            file_size=file_size,
            folder_path=folder_path
        )
        self.db.add(user_file)
        self.db.commit()
        self.db.refresh(user_file)
        
        return user_file
    
    def delete_file(self, file_id: int, user_id: int) -> UserFile:
        """
        Soft delete a file (move to trash).
        
        Args:
            file_id: ID of the file
            user_id: ID of the user (for ownership validation)
            
        Returns:
            Updated UserFile object
            
        Raises:
            HTTPException: If file not found or permission denied
        """
        user_file = self.db.query(UserFile).filter(
            UserFile.id == file_id,
            UserFile.user_id == user_id
        ).first()
        
        if not user_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        if user_file.is_system_folder:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System folders cannot be deleted"
            )
        
        if user_file.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is already in trash"
            )
        
        # Soft delete
        user_file.is_deleted = True
        user_file.deleted_at = datetime.utcnow()
        user_file.folder_path = "trash"  # Move to trash folder
        
        self.db.commit()
        self.db.refresh(user_file)
        
        return user_file
    
    def permanent_delete(self, file_id: int, user_id: int) -> None:
        """
        Permanently delete a file from trash.
        
        Args:
            file_id: ID of the file
            user_id: ID of the user (for ownership validation)
            
        Raises:
            HTTPException: If file not found or not in trash
        """
        user_file = self.db.query(UserFile).filter(
            UserFile.id == file_id,
            UserFile.user_id == user_id
        ).first()
        
        if not user_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        if not user_file.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be in trash before permanent deletion"
            )
        
        # Delete physical file
        file_path = Path(settings.DATA_DIR) / user_file.file_path
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
            except Exception as e:
                # Log error but continue with DB deletion
                print(f"Warning: Failed to delete file {file_path}: {e}")
        
        # Delete DB record
        self.db.delete(user_file)
        self.db.commit()
    
    def restore_file(self, file_id: int, user_id: int, restore_folder: str = "shared") -> UserFile:
        """
        Restore a file from trash.
        
        Args:
            file_id: ID of the file
            user_id: ID of the user (for ownership validation)
            restore_folder: Folder to restore to (default: shared)
            
        Returns:
            Updated UserFile object
            
        Raises:
            HTTPException: If file not found or not in trash
        """
        user_file = self.db.query(UserFile).filter(
            UserFile.id == file_id,
            UserFile.user_id == user_id
        ).first()
        
        if not user_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        if not user_file.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is not in trash"
            )
        
        # Restore
        user_file.is_deleted = False
        user_file.deleted_at = None
        user_file.folder_path = restore_folder
        
        self.db.commit()
        self.db.refresh(user_file)
        
        return user_file
    
    def create_folder(self, user_id: int, folder_name: str, parent_path: str = "shared") -> UserFile:
        """
        Create a new folder under shared or workflows directory.
        
        Args:
            user_id: ID of the user
            folder_name: Name of the new folder
            parent_path: Parent folder path (must be under "shared" or "workflows")
            
        Returns:
            Created UserFile object representing folder
            
        Raises:
            HTTPException: If parent path is invalid
        """
        # Allow folders under "shared" or "workflows" directories
        if not (parent_path.startswith("shared") or parent_path.startswith("workflows")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Folders can only be created under 'shared' or 'workflows' directory"
            )
        
        # Sanitize folder name
        safe_name = "".join(c for c in folder_name if c.isalnum() or c in "._- ").strip()
        if not safe_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid folder name"
            )
        
        folder_path = f"{parent_path}/{safe_name}"
        
        # Check if folder already exists
        existing = self.db.query(UserFile).filter(
            UserFile.user_id == user_id,
            UserFile.folder_path == folder_path,
            UserFile.file_type == "folder"
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder already exists"
            )
        
        # Create physical folder
        user_dir = Path(settings.uploads_dir) / str(user_id)
        full_path = user_dir / folder_path
        full_path.mkdir(parents=True, exist_ok=True)
        
        # Create DB record
        folder_record = UserFile(
            user_id=user_id,
            file_path=str(full_path.relative_to(settings.DATA_DIR)),
            file_name=safe_name,
            file_type="folder",
            file_size=0,
            folder_path=parent_path  # Fixed: use parent_path, not folder_path (full path)
        )
        self.db.add(folder_record)
        self.db.commit()
        self.db.refresh(folder_record)
        
        return folder_record
    
    def migrate_existing_files(self, user_id: int) -> Dict[str, int]:
        """
        Migrate existing files and folders from filesystem to database.
        Scans data/uploads/{user_id} and creates DB records for untracked files and folders.
        Also ensures system folders exist.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with migration statistics
        """
        user_dir = Path(settings.uploads_dir) / str(user_id)
        
        # Create user directory if it doesn't exist
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure system folders exist in filesystem
        for folder in self.SYSTEM_FOLDERS:
            folder_path = user_dir / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Ensured system folder exists: {folder}")
        
        # Ensure system folders are in database
        self.create_system_folders(user_id)
        
        stats = {"files_found": 0, "files_migrated": 0, "files_skipped": 0, "folders_migrated": 0}
        
        # First, collect all unique folder paths from filesystem (including empty ones)
        folder_paths = set()
        
        # Scan all directories (not just parent dirs of files)
        for item_path in user_dir.rglob("*"):
            if item_path.is_dir():
                # This is a directory - add it
                folder_parts = item_path.relative_to(user_dir).parts
                if folder_parts:
                    folder_path = "/".join(folder_parts)
                    folder_paths.add(folder_path)
            elif item_path.is_file():
                # For files, add all parent directories up to user_dir
                parent = item_path.parent
                while parent != user_dir:
                    folder_parts = parent.relative_to(user_dir).parts
                    if folder_parts:
                        folder_path = "/".join(folder_parts)
                        folder_paths.add(folder_path)
                    parent = parent.parent
        
        # Create missing folder entries in database
        for folder_path in sorted(folder_paths):  # Sort to create parent folders first
            # Check if folder already tracked (improved check to prevent duplicates)
            existing = self.db.query(UserFile).filter(
                UserFile.user_id == user_id,
                UserFile.file_path == f"uploads/{user_id}/{folder_path}",
                UserFile.file_type == "folder"
            ).first()
            
            if not existing:
                # Determine parent folder path
                folder_parts = folder_path.split('/')
                parent_path = "/".join(folder_parts[:-1]) if len(folder_parts) > 1 else folder_parts[0].split('/')[0]
                
                # Create folder DB record
                folder_record = UserFile(
                    user_id=user_id,
                    file_path=f"uploads/{user_id}/{folder_path}",
                    file_name=folder_parts[-1],  # Last part is folder name
                    file_type="folder",
                    file_size=0,
                    folder_path=parent_path,
                    is_system_folder=False
                )
                self.db.add(folder_record)
                stats["folders_migrated"] += 1
                print(f"📁 Created folder entry: {folder_path} (parent: {parent_path})")
            else:
                print(f"📁 Skipped existing folder: {folder_path}")
        
        # Commit folder records first
        self.db.commit()
        
        # Now scan and migrate files
        for file_path in user_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            stats["files_found"] += 1
            
            # Get relative path and normalize
            rel_path = self.normalize_path(file_path.relative_to(settings.DATA_DIR))
            
            # Check if already tracked (use file_path for accurate duplicate detection)
            existing = self.db.query(UserFile).filter(
                UserFile.user_id == user_id,
                UserFile.file_path == rel_path
            ).first()
            
            if existing:
                stats["files_skipped"] += 1
                print(f"⏭️ Skipped existing file: {file_path.name}")
                continue
            
            # Determine file type
            if validate_image_file(file_path.name):
                file_type = "image"
            elif validate_video_file(file_path.name):
                file_type = "video"
            else:
                file_type = "other"
            
            # Determine folder path
            folder_parts = file_path.relative_to(user_dir).parent.parts
            if not folder_parts:
                folder_path = "shared"
            else:
                folder_path = "/".join(folder_parts)
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Create DB record
            user_file = UserFile(
                user_id=user_id,
                file_path=rel_path,  # Already normalized above
                file_name=file_path.name,
                file_type=file_type,
                file_size=file_size,
                folder_path=folder_path
            )
            self.db.add(user_file)
            stats["files_migrated"] += 1
            print(f"✅ Migrated file: {file_path.name}")
        
        self.db.commit()
        
        return stats
    
    def cleanup_old_trash(self) -> int:
        """
        Permanently delete files from trash older than TRASH_RETENTION_DAYS.
        Called by TrashCleanupWorker.
        
        Returns:
            Number of files deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=settings.TRASH_RETENTION_DAYS)
        
        old_files = self.db.query(UserFile).filter(
            UserFile.is_deleted == True,
            UserFile.deleted_at < cutoff_date
        ).all()
        
        count = 0
        for user_file in old_files:
            try:
                # Delete physical file
                file_path = Path(settings.DATA_DIR) / user_file.file_path
                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
                
                # Delete DB record
                self.db.delete(user_file)
                count += 1
            except Exception as e:
                print(f"Error deleting file {user_file.id}: {e}")
                continue
        
        self.db.commit()
        
        return count
    
    def move_file(self, user_id: int, file_id: int, new_folder_path: str) -> UserFile:
        """
        Move a file to a new folder path.
        
        Args:
            user_id: ID of the user
            file_id: ID of the file to move
            new_folder_path: Destination folder path
            
        Returns:
            Updated UserFile object
            
        Raises:
            HTTPException: If file not found, invalid destination, or permission denied
        """
        # Get file
        user_file = self.db.query(UserFile).filter(
            UserFile.id == file_id,
            UserFile.user_id == user_id
        ).first()
        
        if not user_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Validate destination
        if new_folder_path.startswith("workflows"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot move files to workflows folder"
            )
        
        if new_folder_path.startswith("trash"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Use delete endpoint to move files to trash"
            )
        
        if not new_folder_path.startswith("shared"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Destination must be under 'shared' folder"
            )
        
        # Don't move if already in destination
        if user_file.folder_path == new_folder_path:
            return user_file
        
        # Build new file path
        user_dir = Path(settings.uploads_dir) / str(user_id)
        old_path = Path(settings.DATA_DIR) / user_file.file_path
        new_path = user_dir / new_folder_path / user_file.file_name
        
        # Handle filename conflicts with auto-rename
        if new_path.exists():
            base_name = new_path.stem
            extension = new_path.suffix
            counter = 1
            while new_path.exists():
                new_path = user_dir / new_folder_path / f"{base_name} ({counter}){extension}"
                counter += 1
            # Update filename in DB if renamed
            user_file.file_name = new_path.name
        
        # Create destination directory if needed
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move physical file
        try:
            shutil.move(str(old_path), str(new_path))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to move file: {str(e)}"
            )
        
        # Update DB record
        user_file.folder_path = new_folder_path
        user_file.file_path = self.normalize_path(new_path.relative_to(settings.DATA_DIR))
        self.db.commit()
        self.db.refresh(user_file)
        
        return user_file
    
    def rename_file(self, user_id: int, file_id: int, new_name: str) -> UserFile:
        """
        Rename a file.
        
        Args:
            user_id: ID of the user
            file_id: ID of the file to rename
            new_name: New filename
            
        Returns:
            Updated UserFile object
            
        Raises:
            HTTPException: If file not found, system folder, or name conflict
        """
        # Get file
        user_file = self.db.query(UserFile).filter(
            UserFile.id == file_id,
            UserFile.user_id == user_id
        ).first()
        
        if not user_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Cannot rename system folders
        if user_file.is_system_folder:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot rename system folders"
            )
        
        # Sanitize new name
        safe_name = "".join(c for c in new_name if c.isalnum() or c in "._- ").strip()
        if not safe_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        # Check for name conflict in same folder
        conflict = self.db.query(UserFile).filter(
            UserFile.user_id == user_id,
            UserFile.folder_path == user_file.folder_path,
            UserFile.file_name == safe_name,
            UserFile.id != file_id
        ).first()
        
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A file with this name already exists in the folder"
            )
        
        # Build new file path
        old_path = Path(settings.DATA_DIR) / user_file.file_path
        new_path = old_path.parent / safe_name
        
        # Rename physical file
        try:
            old_path.rename(new_path)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to rename file: {str(e)}"
            )
        
        # Update DB record
        user_file.file_name = safe_name
        user_file.file_path = self.normalize_path(new_path.relative_to(settings.DATA_DIR))
        self.db.commit()
        self.db.refresh(user_file)
        
        return user_file
    
    def batch_delete_files(self, user_id: int, file_ids: List[int]) -> Dict[str, int]:
        """
        Batch delete files (move to trash).
        
        Args:
            user_id: ID of the user
            file_ids: List of file IDs to delete
            
        Returns:
            Dictionary with success and failure counts
        """
        stats = {"success": 0, "failed": 0, "errors": []}
        
        for file_id in file_ids:
            try:
                self.delete_file(file_id, user_id)  # Fixed parameter order
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"file_id": file_id, "error": str(e)})
                print(f"❌ Failed to delete file {file_id}: {str(e)}")
        
        return stats
    
    def batch_restore_files(self, user_id: int, file_ids: List[int], restore_to: str = "shared") -> Dict[str, int]:
        """
        Batch restore files from trash.
        
        Args:
            user_id: ID of the user
            file_ids: List of file IDs to restore
            restore_to: Destination folder path
            
        Returns:
            Dictionary with success and failure counts
        """
        stats = {"success": 0, "failed": 0, "errors": []}
        
        for file_id in file_ids:
            try:
                # Use keyword arguments to avoid parameter order confusion
                self.restore_file(file_id=file_id, user_id=user_id, restore_folder=restore_to)
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"file_id": file_id, "error": str(e)})
        
        return stats
