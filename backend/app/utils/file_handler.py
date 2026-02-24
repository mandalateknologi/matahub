"""
File Handler Utilities - Upload, Validation, Storage
"""
import shutil
import zipfile
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from fastapi import UploadFile, HTTPException, status

from app.config import settings


class YOLOFormatError(Exception):
    """Exception raised for YOLO format validation errors."""
    pass


def validate_file_size(file: UploadFile, max_size: int) -> None:
    """
    Validate file size against maximum allowed.
    
    Args:
        file: The uploaded file
        max_size: Maximum allowed size in bytes
        
    Raises:
        HTTPException: If file exceeds maximum size
    """
    # Read file to check size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed ({max_size / 1024 / 1024:.2f}MB)"
        )


def validate_image_file(filename: str) -> bool:
    """Check if file is a valid image format."""
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    return Path(filename).suffix.lower() in valid_extensions


def validate_video_file(filename: str) -> bool:
    """Check if file is a valid video format."""
    valid_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    return Path(filename).suffix.lower() in valid_extensions


def validate_yolo_label(label_path: Path, task_type: str = "detect") -> Tuple[bool, List[str]]:
    """
    Validate YOLO format label file.
    prediction format: class_id x_center y_center width height (normalized 0-1)
    Segmentation format: class_id x1 y1 x2 y2 x3 y3 ... (normalized 0-1, variable polygon points)
    
    Args:
        label_path: Path to the label file
        task_type: Task type ("detect" or "segment")
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    try:
        with open(label_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            parts = line.split()
            
            if task_type == "segment":
                # Segmentation: class_id followed by polygon coordinates (at least 6 values: class + 3 points)
                if len(parts) < 7:  # class_id + at least 3 points (6 coordinates)
                    errors.append(f"Line {i}: Expected at least 7 values (class_id + 3 polygon points), got {len(parts)}")
                    continue
                # Check if number of coordinates is even (pairs of x,y)
                if (len(parts) - 1) % 2 != 0:
                    errors.append(f"Line {i}: Expected even number of coordinates after class_id, got {len(parts) - 1}")
                    continue
            else:
                # prediction: exactly 5 values
                if len(parts) != 5:
                    errors.append(f"Line {i}: Expected 5 values (class_id x_center y_center width height), got {len(parts)}")
                    continue
            
            try:
                class_id = int(parts[0])
                if class_id < 0:
                    errors.append(f"Line {i}: class_id must be >= 0")
            except ValueError:
                errors.append(f"Line {i}: class_id must be an integer")
            
            # Validate coordinates based on task type
            if task_type == "segment":
                # For segmentation, validate all coordinate pairs
                for j in range(1, len(parts)):
                    try:
                        value = float(parts[j])
                        if not (0 <= value <= 1):
                            coord_name = "x" if (j - 1) % 2 == 0 else "y"
                            errors.append(f"Line {i}: coordinate {coord_name} at position {j} must be between 0 and 1, got {value}")
                    except ValueError:
                        errors.append(f"Line {i}: coordinate at position {j} must be a float")
            else:
                # For prediction, validate bounding box coordinates
                for j, name in enumerate(['x_center', 'y_center', 'width', 'height'], 1):
                    try:
                        value = float(parts[j])
                        if not (0 <= value <= 1):
                            errors.append(f"Line {i}: {name} must be between 0 and 1")
                    except ValueError:
                        errors.append(f"Line {i}: {name} must be a float")
    
    except Exception as e:
        errors.append(f"Failed to read file: {str(e)}")
    
    return len(errors) == 0, errors


def extract_dataset_classes(labels_dir: Path) -> List[int]:
    """
    Extract unique class IDs from label files.
    Supports both flat structure and train/val/test subdirectories.
    
    Args:
        labels_dir: Path to the labels directory
        
    Returns:
        Sorted list of unique class IDs
    """
    class_ids = set()
    
    # Check for subdirectories (train/val/test)
    subdirs = [labels_dir / "train", labels_dir / "val", labels_dir / "test"]
    search_dirs = [d for d in subdirs if d.exists()] or [labels_dir]
    
    for search_dir in search_dirs:
        for label_file in search_dir.glob("*.txt"):
            try:
                with open(label_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            parts = line.split()
                            if parts:
                                class_ids.add(int(parts[0]))
            except (ValueError, IOError):
                continue
    
    return sorted(list(class_ids))


def create_empty_dataset_structure(dataset_id: int, task_type: str = "detect") -> Dict[str, Any]:
    """
    Create empty dataset directory structure with train/val/test splits.
    
    Structure for detect/segment:
    {dataset_id}/
        images/
            train/
            val/
            test/
        labels/
            train/
            val/
            test/
    
    Structure for classify:
    {dataset_id}/
        train/
        val/
        test/
    
    Args:
        dataset_id: The dataset ID
        task_type: Task type (detect, segment, classify)
        
    Returns:
        Empty dict (directory created at {DATA_DIR}/datasets/{dataset_id})
        
    Raises:
        HTTPException: If directory creation fails
    """
    try:
        dataset_dir = Path(settings.datasets_dir) / str(dataset_id)
        
        if task_type == "classify":
            # For classification: only create train/val/test folders
            (dataset_dir / "train").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "val").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "test").mkdir(parents=True, exist_ok=True)
        else:
            # For detect/segment: create images and labels structure
            # Create image subdirectories
            (dataset_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "images" / "test").mkdir(parents=True, exist_ok=True)
            
            # Create label subdirectories
            (dataset_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)
            (dataset_dir / "labels" / "test").mkdir(parents=True, exist_ok=True)
        
        return {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create dataset structure: {str(e)}"
        )


def create_class_folders(dataset_path: Path, class_name: str, splits: List[str] = None) -> Dict[str, Any]:
    """
    Create class folder in each split directory for classification datasets.
    
    Args:
        dataset_path: Path to the dataset directory
        class_name: Name of the class to create
        splits: List of splits to create folders in (default: ["train", "val", "test"])
        
    Returns:
        Dict with created paths and status
    """
    if splits is None:
        splits = ["train", "val", "test"]
    
    created_paths = {}
    
    for split in splits:
        split_dir = dataset_path / split
        if split_dir.exists():
            class_dir = split_dir / class_name
            class_dir.mkdir(exist_ok=True)
            created_paths[split] = str(class_dir)
    
    return {
        "created": True,
        "paths": created_paths
    }


def delete_class_folders(dataset_path: Path, class_name: str, splits: List[str] = None) -> Dict[str, Any]:
    """
    Delete class folder from all split directories for classification datasets.
    Checks if folders contain files and counts them.
    
    Args:
        dataset_path: Path to the dataset directory
        class_name: Name of the class to delete
        splits: List of splits to delete folders from (default: ["train", "val", "test"])
        
    Returns:
        Dict with deletion status, warnings, and file counts
    """
    if splits is None:
        splits = ["train", "val", "test"]
    
    warnings = []
    file_counts = {}
    deleted = False
    
    for split in splits:
        class_dir = dataset_path / split / class_name
        if class_dir.exists():
            # Count files in the folder
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                image_files.extend(class_dir.glob(ext))
                image_files.extend(class_dir.glob(ext.upper()))
            
            file_count = len(image_files)
            if file_count > 0:
                file_counts[split] = file_count
                warnings.append(f"Split '{split}' had {file_count} file(s)")
            
            # Delete the folder
            shutil.rmtree(class_dir, ignore_errors=True)
            deleted = True
    
    return {
        "deleted": deleted,
        "warnings": warnings,
        "file_counts": file_counts
    }


def rename_class_folders(dataset_path: Path, old_name: str, new_name: str, splits: List[str] = None) -> Dict[str, Any]:
    """
    Rename class folder across all split directories for classification datasets.
    Checks for files in old folders.
    
    Args:
        dataset_path: Path to the dataset directory
        old_name: Current name of the class
        new_name: New name for the class
        splits: List of splits to rename folders in (default: ["train", "val", "test"])
        
    Returns:
        Dict with rename status, warnings, and file counts
    """
    if splits is None:
        splits = ["train", "val", "test"]
    
    warnings = []
    file_counts = {}
    renamed = False
    
    for split in splits:
        old_dir = dataset_path / split / old_name
        new_dir = dataset_path / split / new_name
        
        if old_dir.exists():
            # Count files in the old folder
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                image_files.extend(old_dir.glob(ext))
                image_files.extend(old_dir.glob(ext.upper()))
            
            file_count = len(image_files)
            if file_count > 0:
                file_counts[split] = file_count
            
            # Rename the folder
            old_dir.rename(new_dir)
            renamed = True
    
    if file_counts:
        total_files = sum(file_counts.values())
        warnings.append(f"Renamed class with {total_files} total file(s) across splits")
    
    return {
        "renamed": renamed,
        "warnings": warnings,
        "file_counts": file_counts
    }


def validate_yolo_dataset(dataset_path: Path, task_type: str = None) -> Dict[str, Any]:
    """
    Validate a YOLO format dataset directory structure.
    Supports prediction/segmentation and classification structures.
    
    prediction/Segmentation structure:
    - images/ (flat or with train/val/test subdirs)
    - labels/ (flat or with train/val/test subdirs)
    
    Classification structure:
    - train/<class_folders>/
    - val/<class_folders>/
    - test/<class_folders>/
    
    Args:
        dataset_path: Path to the dataset directory
        task_type: Optional task type hint ("detect", "segment", "classify"). 
                   If not provided, will attempt to detect from structure or yaml.
        
    Returns:
        Dict with validation results and stats
        
    Raises:
        YOLOFormatError: If dataset structure is invalid
    """
    result = {
        "valid": False,
        "images_count": 0,
        "labels_count": 0,
        "classes": [],
        "errors": [],
        "warnings": [],
        "has_splits": False,
        "task_type": None
    }
    
    # Check if it's a classification structure
    split_dirs = ["train", "val", "test"]
    has_classification_structure = False
    
    # Check for classification: train/val/test folders at root with class subfolders
    existing_splits = [d for d in split_dirs if (dataset_path / d).exists()]
    if existing_splits:
        # Check if these are class folders (classification) or images/labels folders (prediction)
        first_split = dataset_path / existing_splits[0]
        subdirs = [d for d in first_split.iterdir() if d.is_dir()]
        
        # If there are subdirectories, check if they contain images (classification)
        if subdirs:
            # Check first subdir for images
            first_subdir = subdirs[0]
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                image_files.extend(first_subdir.glob(ext))
                if image_files:
                    break
            
            if image_files:
                has_classification_structure = True
    
    if has_classification_structure:
        # Validate classification structure
        result["task_type"] = "classify"
        result["has_splits"] = True
        
        class_names = set()
        
        for split in existing_splits:
            split_dir = dataset_path / split
            class_folders = [d for d in split_dir.iterdir() if d.is_dir()]
            
            for class_folder in class_folders:
                class_names.add(class_folder.name)
                
                # Count images in this class folder
                image_files_set = set()
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                    for f in class_folder.glob(ext):
                        image_files_set.add(f.resolve())
                    for f in class_folder.glob(ext.upper()):
                        image_files_set.add(f.resolve())
                result["images_count"] += len(image_files_set)
        
        # For classification, extract class names from folder names
        # Convert to numbered format for consistency
        sorted_classes = sorted(list(class_names))
        result["classes"] = list(range(len(sorted_classes)))  # [0, 1, 2, ...]
        
        if result["images_count"] == 0:
            result["errors"].append("No image files found in class folders")
            raise YOLOFormatError("No image files found in class folders")
        
        result["valid"] = True
        return result
    
    else:
        # Validate prediction/segmentation structure
        # Use provided task_type, or try to determine from data.yaml, or default to "detect"
        detected_task_type = task_type  # Use parameter if provided
        
        if not detected_task_type:
            # Try to determine from data.yaml if it exists
            yaml_path = dataset_path / "data.yaml"
            if yaml_path.exists():
                try:
                    import yaml
                    with open(yaml_path, 'r') as f:
                        yaml_data = yaml.safe_load(f)
                        if yaml_data and 'task' in yaml_data:
                            detected_task_type = yaml_data['task']
                except:
                    pass  # Continue with None
        
        # Default to "detect" if still not determined
        if not detected_task_type:
            detected_task_type = "detect"
        
        result["task_type"] = detected_task_type
        
        images_dir = dataset_path / "images"
        labels_dir = dataset_path / "labels"
        
        # Check directory structure
        if not images_dir.exists():
            result["errors"].append("Missing 'images' directory")
        if not labels_dir.exists():
            result["errors"].append("Missing 'labels' directory")
        
        if result["errors"]:
            raise YOLOFormatError("; ".join(result["errors"]))
        
        # Check if using train/val/test splits
        has_image_splits = any((images_dir / split).exists() for split in split_dirs)
        has_label_splits = any((labels_dir / split).exists() for split in split_dirs)
        
        if has_image_splits or has_label_splits:
            result["has_splits"] = True
            # Validate split structure
            image_search_dirs = [images_dir / split for split in split_dirs if (images_dir / split).exists()]
            label_search_dirs = [labels_dir / split for split in split_dirs if (labels_dir / split).exists()]
        else:
            # Flat structure
            image_search_dirs = [images_dir]
            label_search_dirs = [labels_dir]
        
        # Count and validate images
        image_files = []
        unique_images = set()
        for search_dir in image_search_dirs:
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                for f in search_dir.glob(ext):
                    resolved = f.resolve()
                    if resolved not in unique_images:
                        unique_images.add(resolved)
                        image_files.append(f)
                for f in search_dir.glob(ext.upper()):
                    resolved = f.resolve()
                    if resolved not in unique_images:
                        unique_images.add(resolved)
                        image_files.append(f)
        
        result["images_count"] = len(image_files)
        
        if result["images_count"] == 0:
            result["errors"].append("No image files found in 'images' directory")
            raise YOLOFormatError("No image files found in 'images' directory")
        
        # Count and validate labels
        label_files = []
        for search_dir in label_search_dirs:
            label_files.extend(search_dir.glob("*.txt"))
        
        result["labels_count"] = len(label_files)
        
        # Validate label format (sample check on first few files)
        sample_size = min(10, len(label_files))
        for label_file in label_files[:sample_size]:
            is_valid, errors = validate_yolo_label(label_file, detected_task_type)
            if not is_valid:
                result["errors"].extend([f"{label_file.name}: {e}" for e in errors[:3]])
        
        if result["errors"]:
            raise YOLOFormatError("; ".join(result["errors"][:5]))
        
        # Extract classes
        result["classes"] = extract_dataset_classes(labels_dir)
        
        # Warnings for missing labels
        image_stems = {f.stem for f in image_files}
        label_stems = {f.stem for f in label_files}
        
        missing_labels = image_stems - label_stems
        if missing_labels:
            result["warnings"].append(f"{len(missing_labels)} images without corresponding label files")
        
        result["valid"] = True
        return result


async def save_uploaded_dataset(
    file: UploadFile,
    dataset_id: int,
    name: str
) -> Dict[str, Any]:
    """
    Save and extract an uploaded dataset ZIP file.
    
    Args:
        file: The uploaded ZIP file
        dataset_id: The dataset ID (dataset saved to {DATA_DIR}/datasets/{dataset_id})
        name: The dataset name
        
    Returns:
        Dict with dataset info (yaml_path, images_count, labels_count, classes)
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate file size
    validate_file_size(file, settings.MAX_DATASET_SIZE)
    
    # Create dataset directory
    dataset_dir = Path(settings.datasets_dir) / str(dataset_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # Save ZIP file temporarily
    temp_zip = dataset_dir / "temp.zip"
    try:
        with open(temp_zip, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        # Extract ZIP
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(dataset_dir)
        
        # Remove temp ZIP
        temp_zip.unlink()
        
        # Check if there's a nested directory (common in ZIPs)
        subdirs = [d for d in dataset_dir.iterdir() if d.is_dir()]
        if len(subdirs) == 1 and not (dataset_dir / "images").exists():
            # Move contents up one level
            nested_dir = subdirs[0]
            for item in nested_dir.iterdir():
                shutil.move(str(item), str(dataset_dir / item.name))
            nested_dir.rmdir()
        
        # Validate YOLO format
        validation = validate_yolo_dataset(dataset_dir)
        
        # Determine task_type from validation
        task_type = validation.get("task_type", "detect")
        
        # Generate class dict from class IDs
        class_dict = {str(class_id): f"class_{class_id}" for class_id in validation["classes"]}
        
        # Create data.yaml for YOLO training (only for detect/segment)
        yaml_path = create_yolo_yaml(
            dataset_dir, 
            name, 
            class_dict,
            validation.get("has_splits", False),
            task_type
        )
        
        return {
            "yaml_path": str(yaml_path) if yaml_path else None,
            "images_count": validation["images_count"],
            "labels_count": validation["labels_count"],
            "classes": validation["classes"],
            "has_splits": validation.get("has_splits", False),
            "task_type": task_type
        }
        
    except YOLOFormatError as e:
        # Cleanup on error
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid YOLO dataset format: {str(e)}"
        )
    except zipfile.BadZipFile:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ZIP file"
        )
    except Exception as e:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dataset: {str(e)}"
        )


def create_yolo_yaml(
    dataset_dir: Path, 
    name: str, 
    class_dict: Dict[str, str],
    has_splits: bool = False,
    task_type: str = "detect"
) -> Optional[Path]:
    """
    Create a data.yaml file for YOLO training.
    
    Args:
        dataset_dir: Path to the dataset directory
        name: Dataset name
        class_dict: Dict mapping class IDs to names (e.g., {'0': 'helmet', '1': 'vest'})
        has_splits: Whether dataset has train/val/test splits
        task_type: Task type (detect, segment, classify)
        
    Returns:
        Path to the created YAML file
    """
    yaml_path = dataset_dir / "data.yaml"
    
    # Determine paths based on task type and structure
    if task_type == "classify":
        # Classification: use train/val/test folders directly (containing class subfolders)
        train_path = "train"
        val_path = "val"
        test_path = "test"
    else:
        # prediction/Segmentation: use images/labels structure
        if has_splits:
            train_path = "images/train"
            val_path = "images/val"
            test_path = "images/test"
        else:
            train_path = "images"
            val_path = "images"
            test_path = None
    
    # Generate class names list in order
    class_ids = sorted([int(k) for k in class_dict.keys()])
    class_names = [class_dict[str(i)] for i in class_ids]
    
    yaml_content = f"""# ATVISION Dataset: {name}
path: {dataset_dir}
train: {train_path}
val: {val_path}
"""
    
    if test_path and (dataset_dir / test_path).exists():
        yaml_content += f"test: {test_path}\n"
    
    yaml_content += f"""
# Classes
nc: {len(class_ids)}
names: {class_names}
"""
    
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    
    return yaml_path


def save_prediction_image(
    source_path: str,
    job_id: int
) -> str:
    """
    Copy an existing image file to prediction job directory.
    
    Args:
        source_path: Path to the source image file
        job_id: The prediction job ID
        
    Returns:
        Path to the copied image in job directory
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If file is not a valid image format
    """
    source = Path(source_path)
    
    if not source.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")
    
    if not validate_image_file(source.name):
        raise ValueError(f"Invalid image format: {source.name}")
    
    # Create job directory
    job_dir = Path(settings.predictions_dir) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy image to job directory
    dest_path = job_dir / source.name
    shutil.copy2(str(source), str(dest_path))
    
    return str(dest_path)


async def save_uploaded_image(
    file: UploadFile,
    job_id: int
) -> str:
    """
    Save an uploaded image for prediction.
    
    Args:
        file: The uploaded image file
        job_id: The prediction job ID
        
    Returns:
        Path to the saved image
    """
    validate_file_size(file, settings.MAX_IMAGE_SIZE)
    
    if not validate_image_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Supported: jpg, jpeg, png, bmp, tiff, webp"
        )
    
    # Create job directory
    job_dir = Path(settings.predictions_dir) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save image
    image_path = job_dir / file.filename
    with open(image_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
    
    return str(image_path)


async def save_uploaded_video(
    file: UploadFile,
    job_id: int
) -> str:
    """
    Save an uploaded video for prediction.
    
    Args:
        file: The uploaded video file
        job_id: The prediction job ID
        
    Returns:
        Path to the saved video
    """
    validate_file_size(file, settings.MAX_VIDEO_SIZE)
    
    if not validate_video_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video format. Supported: mp4, avi, mov, mkv, webm"
        )
    
    # Create job directory
    job_dir = Path(settings.predictions_dir) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save video
    video_path = job_dir / file.filename
    with open(video_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
    
    return str(video_path)


def cleanup_old_predictions(retention_days: int = None) -> int:
    """
    Clean up old prediction job directories.
    
    Args:
        retention_days: Number of days to retain prediction data
        
    Returns:
        Number of directories cleaned up
    """
    if retention_days is None:
        retention_days = settings.PREDICTION_RETENTION_DAYS
    
    from datetime import datetime, timedelta
    
    predictions_dir = Path(settings.predictions_dir)
    if not predictions_dir.exists():
        return 0
    
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    cleaned = 0
    
    for job_dir in predictions_dir.iterdir():
        if job_dir.is_dir():
            # Check directory modification time
            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
            if mtime < cutoff_time:
                shutil.rmtree(job_dir, ignore_errors=True)
                cleaned += 1
    
    return cleaned


def distribute_classification_images(
    dataset_dir: Path,
    classes_json: Dict[str, str],
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """
    Redistribute classification dataset images across train/val/test splits.
    Uses per-class stratified distribution with hardcoded 80/10/10 ratio.
    
    Args:
        dataset_dir: Path to dataset directory
        classes_json: Dict mapping class IDs to class names
        seed: Optional seed for reproducible shuffling
        
    Returns:
        Dict with distribution results, warnings, and moved image count
    """
    import random
    
    # Hardcoded ratios: 80% train, 10% val, 10% test
    TRAIN_RATIO = 0.8
    VAL_RATIO = 0.1
    TEST_RATIO = 0.1
    MIN_IMAGES_WARNING_THRESHOLD = 10
    
    if seed is not None:
        random.seed(seed)
    
    warnings = []
    classes_processed = 0
    total_moved = 0
    
    # Final distribution counts
    final_distribution = {"train": 0, "val": 0, "test": 0}
    
    # Process each class
    for class_id, class_name in classes_json.items():
        # Collect all images from all splits for this class
        all_images = []
        
        for split in ["train", "val", "test"]:
            class_dir = dataset_dir / split / class_name
            if class_dir.exists() and class_dir.is_dir():
                # Collect image files with deduplication
                image_set = set()
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                    for img_path in class_dir.glob(ext):
                        image_set.add(img_path.resolve())
                    for img_path in class_dir.glob(ext.upper()):
                        image_set.add(img_path.resolve())
                
                all_images.extend(list(image_set))
        
        if not all_images:
            continue
        
        # Warning for classes with few images
        if len(all_images) < MIN_IMAGES_WARNING_THRESHOLD:
            warnings.append(f"Class '{class_name}' has only {len(all_images)} images (recommended: at least 10)")
        
        # Shuffle images
        random.shuffle(all_images)
        
        # Calculate split indices
        total_images = len(all_images)
        train_count = int(total_images * TRAIN_RATIO)
        val_count = int(total_images * VAL_RATIO)
        # test_count gets remainder to ensure all images are included
        
        # Ensure minimum 1 image per split if possible
        if total_images >= 3:
            if train_count == 0:
                train_count = 1
            if val_count == 0:
                val_count = 1
            # Adjust test to get remainder
            test_count = total_images - train_count - val_count
            if test_count < 1:
                test_count = 1
                val_count = total_images - train_count - test_count
        else:
            # Too few images, distribute as best as possible
            test_count = total_images - train_count - val_count
        
        # Split images into three groups
        train_images = all_images[:train_count]
        val_images = all_images[train_count:train_count + val_count]
        test_images = all_images[train_count + val_count:]
        
        # Create target directories
        for split in ["train", "val", "test"]:
            target_dir = dataset_dir / split / class_name
            target_dir.mkdir(parents=True, exist_ok=True)
        
        # Move images to correct splits
        for img_path in train_images:
            target_path = dataset_dir / "train" / class_name / img_path.name
            if img_path != target_path.resolve():
                shutil.move(str(img_path), str(target_path))
                total_moved += 1
        
        for img_path in val_images:
            target_path = dataset_dir / "val" / class_name / img_path.name
            if img_path != target_path.resolve():
                shutil.move(str(img_path), str(target_path))
                total_moved += 1
        
        for img_path in test_images:
            target_path = dataset_dir / "test" / class_name / img_path.name
            if img_path != target_path.resolve():
                shutil.move(str(img_path), str(target_path))
                total_moved += 1
        
        # Update final distribution counts
        final_distribution["train"] += len(train_images)
        final_distribution["val"] += len(val_images)
        final_distribution["test"] += len(test_images)
        
        classes_processed += 1
    
    return {
        "distribution": final_distribution,
        "warnings": warnings,
        "classes_processed": classes_processed,
        "moved_images": total_moved
    }
