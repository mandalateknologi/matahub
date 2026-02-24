"""
Datasets API Router
"""
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image

from app.db import get_db
from app.models.user import User
from app.models.dataset import Dataset, DatasetStatus
from app.schemas.dataset import DatasetResponse, DatasetDetail, SegmentationLabelRequest
from app.utils.auth import get_current_active_user, get_current_user_from_token_or_query
from app.utils.permissions import (
    require_project_admin_or_admin,
    check_dataset_ownership,
    filter_query_by_ownership
)
from app.utils.file_handler import (
    save_uploaded_dataset,
    create_empty_dataset_structure,
    validate_yolo_dataset,
    create_yolo_yaml,
    create_class_folders,
    delete_class_folders,
    rename_class_folders
)

router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

def normalize_classes_json(classes_data: Any) -> Dict[str, str]:
    """
    Normalize classes_json to a consistent dict format.
    
    Handles various formats:
    - List of dicts: [{'0': 'helmet'}, {'1': 'gloves'}] -> {'0': 'helmet', '1': 'gloves'}
    - List of integers: [0, 1, 2] -> {'0': 'class_0', '1': 'class_1', '2': 'class_2'}
    - List of strings: ['helmet', 'gloves'] -> {'0': 'helmet', '1': 'gloves'}
    - Dict: {'0': 'helmet'} -> {'0': 'helmet'} (ensures string keys)
    - String: '{"0": "helmet"}' -> {'0': 'helmet'}
    
    Args:
        classes_data: The classes data in any format
        
    Returns:
        Dict mapping class ID strings to class name strings
    """
    if classes_data is None:
        return {}
    
    # Handle string (JSON)
    if isinstance(classes_data, str):
        try:
            classes_data = json.loads(classes_data.replace("'", '"'))
        except:
            return {}
    
    # Handle list
    if isinstance(classes_data, list):
        # Empty list
        if not classes_data:
            return {}
        
        # List of dicts: [{'0': 'helmet'}, {'1': 'gloves'}]
        if isinstance(classes_data[0], dict):
            merged = {}
            for item in classes_data:
                merged.update(item)
            classes_data = merged
        # List of strings: ['helmet', 'gloves']
        elif isinstance(classes_data[0], str):
            return {str(i): name for i, name in enumerate(classes_data)}
        # List of integers: [0, 1, 2]
        else:
            return {str(i): f"class_{i}" for i in classes_data}
    
    # Handle dict - ensure string keys and values
    if isinstance(classes_data, dict):
        return {str(k): str(v) for k, v in classes_data.items()}
    
    # Fallback
    return {}

@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    dataset_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get list of datasets.
    PROJECT_ADMIN sees only their own datasets.
    ADMIN sees all datasets.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        dataset_id: Optional dataset ID to filter by
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        List of datasets
    """
    query = db.query(Dataset)
    query = filter_query_by_ownership(query, Dataset, current_user)
    
    # Filter by dataset_id if provided
    if dataset_id is not None:
        query = query.filter(Dataset.id == dataset_id)
    
    datasets = query.offset(skip).limit(limit).all()
    return datasets

@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    name: str = Form(...),
    description: str = Form(None),
    task_type: str = Form("detect"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Create a new dataset by uploading a ZIP file.
    Requires PROJECT_ADMIN or ADMIN role.
    
    Args:
        name: Dataset name
        description: Dataset description
        task_type: Task type (detect, segment, classify)
        file: ZIP file containing dataset in YOLO format
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Created dataset
    """
    # Create dataset record with creator
    new_dataset = Dataset(
        name=name,
        description=description,
        task_type=task_type,
        creator_id=current_user.id,
        images_count=0,
        labels_count=0,
        classes_json=[]
    )
    
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    
    try:
        # Save and validate uploaded dataset
        dataset_info = await save_uploaded_dataset(
            file=file,
            dataset_id=new_dataset.id,
            name=name
        )
        
        # Update dataset with info
        new_dataset.yaml_path = dataset_info.get("yaml_path")
        new_dataset.images_count = dataset_info["images_count"]
        new_dataset.labels_count = dataset_info["labels_count"]
        # Normalize classes_json to ensure consistent dict format
        raw_classes = {str(i): f"class_{i}" for i in dataset_info["classes"]}
        new_dataset.classes_json = normalize_classes_json(raw_classes)
        # Update task_type from detected structure if available
        if dataset_info.get("task_type"):
            new_dataset.task_type = dataset_info["task_type"]
        new_dataset.status = DatasetStatus.VALID
        
        db.commit()
        db.refresh(new_dataset)
        
        return new_dataset
        
    except Exception as e:
        # Rollback on error
        db.delete(new_dataset)
        db.commit()
        raise

@router.post("/empty", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_empty_dataset(
    name: str = Form(...),
    description: str = Form(None),
    task_type: str = Form("detect"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Create a new empty dataset with directory structure.
    Requires PROJECT_ADMIN or ADMIN role.
    
    Args:
        name: Dataset name
        description: Dataset description
        task_type: Task type (detect, segment, classify)
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Created empty dataset
    """
    # Create dataset record with creator
    new_dataset = Dataset(
        name=name,
        description=description,
        task_type=task_type,
        creator_id=current_user.id,
        status=DatasetStatus.EMPTY,
        yaml_path=None,
        images_count=0,
        labels_count=0,
        classes_json={}
    )
    
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    
    try:
        # Create empty directory structure
        dataset_info = create_empty_dataset_structure(new_dataset.id, task_type)
        
        db.commit()
        db.refresh(new_dataset)
        
        return new_dataset
        
    except Exception as e:
        # Rollback on error
        db.delete(new_dataset)
        db.commit()
        raise

@router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get detailed information about a specific dataset.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        dataset_id: Dataset ID
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Dataset details
    """
    dataset = check_dataset_ownership(dataset_id, current_user, db)
    return dataset

@router.put("/{dataset_id}", response_model=DatasetDetail)
async def update_dataset(
    dataset_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    classes_json: Optional[str] = Form(None),  # JSON string
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Update a dataset.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        dataset_id: Dataset ID
        name: New dataset name (optional)
        description: New description (optional)
        classes_json: JSON string of class mapping (optional)
        file: ZIP file to add/merge (optional)
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Updated dataset
    """
    dataset = check_dataset_ownership(dataset_id, current_user, db)
    
    warnings_list = []
    
    # Store old classes for comparison
    old_classes_json = dataset.classes_json.copy() if dataset.classes_json else {}
    
    # Update basic fields
    if name is not None:
        dataset.name = name
    if description is not None:
        dataset.description = description
    
    new_classes_json = None
    if classes_json is not None:
        try:
            new_classes_json = json.loads(classes_json)
            # Normalize to ensure consistent dict format
            dataset.classes_json = normalize_classes_json(new_classes_json)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format for classes_json"
            )
    
    # Handle file upload (add/merge to existing dataset)
    if file is not None:
        dataset_dir = dataset.get_dataset_path()
        
        if not dataset_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dataset directory not found. Cannot upload files to this dataset."
            )
        
        try:
            # Save uploaded dataset to temporary location
            dataset_info = await save_uploaded_dataset(
                file=file,
                dataset_id=dataset_id,
                name=dataset.name
            )
            
            # Update counts and status
            dataset.images_count = dataset_info["images_count"]
            dataset.labels_count = dataset_info["labels_count"]
            dataset.yaml_path = dataset_info.get("yaml_path")
            
            # Merge classes if not already set
            if not dataset.classes_json:
                raw_classes = {str(i): f"class_{i}" for i in dataset_info["classes"]}
                dataset.classes_json = normalize_classes_json(raw_classes)
            else:
                # Normalize existing classes_json
                dataset.classes_json = normalize_classes_json(dataset.classes_json)
            
            # Update status
            if dataset.images_count > 0 and dataset.labels_count > 0:
                dataset.status = DatasetStatus.VALID
            else:
                dataset.status = DatasetStatus.INCOMPLETE
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process uploaded file: {str(e)}"
            )
    
    # Handle classification class folder management
    if new_classes_json is not None and dataset.task_type == "classify":
        dataset_dir = dataset.get_dataset_path()
        
        # Detect added, deleted, and renamed classes
        old_class_map = {v: k for k, v in old_classes_json.items()}  # value -> key
        new_class_map = {v: k for k, v in new_classes_json.items()}  # value -> key
        
        old_names = set(old_classes_json.values())
        new_names = set(new_classes_json.values())
        
        added_names = new_names - old_names
        deleted_names = old_names - new_names
        
        # Detect renames: old value exists as new key, old key not in new keys
        renamed_pairs = []
        for old_val in old_classes_json.values():
            if old_val in new_classes_json:  # old value is now a key
                # Check if the old key for this value is different from new key
                old_key = old_class_map[old_val]
                new_key = new_classes_json[old_val]
                if old_key not in new_classes_json.values():
                    # This is a rename: old_val -> new_key
                    renamed_pairs.append((old_val, new_key))
        
        # Process deletions
        for class_name in deleted_names:
            if class_name not in [old for old, new in renamed_pairs]:  # Skip if it's a rename source
                result = delete_class_folders(dataset_dir, class_name)
                if result["deleted"] and result["warnings"]:
                    warning_msg = f"Deleted class '{class_name}': " + ", ".join(result["warnings"])
                    warnings_list.append(warning_msg)
        
        # Process renames
        for old_name, new_name in renamed_pairs:
            result = rename_class_folders(dataset_dir, old_name, new_name)
            if result["renamed"] and result["warnings"]:
                warning_msg = f"Renamed class '{old_name}' to '{new_name}': " + ", ".join(result["warnings"])
                warnings_list.append(warning_msg)
        
        # Process additions
        for class_name in added_names:
            if class_name not in [new for old, new in renamed_pairs]:  # Skip if it's a rename target
                create_class_folders(dataset_dir, class_name)
    
    # Regenerate data.yaml if classes were updated and dataset has files (not for classify)
    if new_classes_json is not None and dataset.images_count > 0:
        if dataset.task_type != "classify":
            try:
                dataset_dir = dataset.get_dataset_path()
                # Check if has splits
                has_splits = (dataset_dir / "images" / "train").exists()
                yaml_path = create_yolo_yaml(
                    dataset_dir,
                    dataset.name,
                    dataset.classes_json,
                    has_splits,
                    dataset.task_type
                )
                if yaml_path:
                    dataset.yaml_path = str(yaml_path)
            except Exception as e:
                # Non-fatal error, just log it
                pass
    
    db.commit()
    db.refresh(dataset)
    
    # Log warnings if any (could extend schema to include warnings in response)
    if warnings_list:
        print(f"Dataset update warnings: {warnings_list}")
    
    return dataset

@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Delete a dataset.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        dataset_id: Dataset ID
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
    """
    dataset = check_dataset_ownership(dataset_id, current_user, db)
    
    # Delete files from storage
    try:
        dataset_dir = dataset.get_dataset_path()
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir, ignore_errors=True)
    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Failed to delete dataset files: {str(e)}")
    
    # Delete from database
    db.delete(dataset)
    db.commit()

@router.get("/{dataset_id}/files", response_model=Dict[str, Any])
async def list_dataset_files(
    dataset_id: int,
    split: str = Query("train", description="Split: train, val, or test"),
    class_name: Optional[str] = Query(None, description="Class name for classification datasets"),
    search: Optional[str] = Query(None, description="Search term for filename"),
    sort_by: str = Query("name_asc", description="Sort by: name_asc, name_desc, size_asc, size_desc"),
    label_filter: str = Query("all", description="Filter by label status: all, labeled, unlabeled"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    List files in a dataset with pagination, search, and filtering.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        dataset_id: Dataset ID
        split: train, val, or test
        class_name: Class name for classification datasets (optional)
        search: Search term for filename
        sort_by: Sort order
        label_filter: Filter by label status
        limit: Maximum number of files to return
        skip: Number of files to skip (for pagination)
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Dict with files list, total count, and has_more flag
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get dataset directory path
    dataset_dir = dataset.get_dataset_path()
    
    # For classification without class selection, return available classes and total count
    if dataset.task_type == "classify" and not class_name:
        if not dataset_dir.exists():
            return {"files": [], "classes": [], "total": 0, "has_more": False, "split": split}
        
        split_dir = dataset_dir / split
        if not split_dir.exists():
            return {"files": [], "classes": [], "total": 0, "has_more": False, "split": split}
        
        classes = [d.name for d in split_dir.iterdir() if d.is_dir()]
        
        # Count total images across all classes
        total_images = 0
        for class_dir in split_dir.iterdir():
            if class_dir.is_dir():
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                    total_images += len(list(class_dir.glob(ext)))
                    total_images += len(list(class_dir.glob(ext.upper())))
        
        return {
            "files": [],
            "classes": sorted(classes),
            "total": total_images,
            "has_more": False,
            "split": split
        }
    
    # Check if dataset directory exists, return empty if not
    if not dataset_dir.exists():
        return {"files": [], "total": 0, "has_more": False, "split": split}
    
    # Determine file path based on task type and parameters
    if dataset.task_type == "classify":
        # Classification: {dataset_dir}/{split}/{class_name}/
        search_dir = dataset_dir / split / class_name
    else:
        # Detection: {dataset_dir}/images/{split}/
        search_dir = dataset_dir / "images" / split
    
    if not search_dir.exists():
        return {"files": [], "total": 0, "has_more": False, "split": split}
    
    # Collect all image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
        image_files.extend(search_dir.glob(ext))
        image_files.extend(search_dir.glob(ext.upper()))
    
    # Deduplicate files (Windows filesystem is case-insensitive, so glob may return duplicates)
    unique_files = {}
    for file_path in image_files:
        # Use resolved absolute path as key to eliminate duplicates
        unique_files[file_path.resolve()] = file_path
    
    image_files = list(unique_files.values())

    # Apply Search Filter
    if search:
        search_lower = search.lower()
        image_files = [f for f in image_files if search_lower in f.name.lower()]

    # Apply Label Filter (for detection and segmentation)
    if dataset.task_type in ["detect", "segment"] and label_filter != "all":
        label_dir = dataset_dir / "labels" / split
        filtered_files = []
        for f in image_files:
            label_path = label_dir / f"{f.stem}.txt"
            has_label = label_path.exists()
            
            if label_filter == "labeled" and has_label:
                filtered_files.append(f)
            elif label_filter == "unlabeled" and not has_label:
                filtered_files.append(f)
        image_files = filtered_files

    # Apply Sorting
    if sort_by == "boxes_desc" and dataset.task_type in ["detect", "segment"]:
        label_dir = dataset_dir / "labels" / split
        def get_box_count(file_path):
            label_path = label_dir / f"{file_path.stem}.txt"
            if not label_path.exists():
                return 0
            try:
                with open(label_path, 'r') as f:
                    # Count non-empty lines
                    return sum(1 for line in f if line.strip())
            except:
                return 0
        image_files.sort(key=get_box_count, reverse=True)
    elif sort_by == "name_desc":
        image_files.sort(key=lambda x: x.name, reverse=True)
    elif sort_by == "size_asc":
        image_files.sort(key=lambda x: x.stat().st_size)
    elif sort_by == "size_desc":
        image_files.sort(key=lambda x: x.stat().st_size, reverse=True)
    else: # name_asc (default)
        image_files.sort(key=lambda x: x.name)
    
    total = len(image_files)
    has_more = (skip + limit) < total
    
    # Paginate
    paginated_files = image_files[skip:skip + limit]
    
    # Build file info list
    files = []
    for file_path in paginated_files:
        # Get relative path from dataset directory
        relative_path = file_path.relative_to(dataset_dir)
        # Convert path to use forward slashes for URL compatibility
        path_str = str(relative_path).replace('\\', '/')
        files.append({
            "name": file_path.name,
            "path": path_str,
            "size": file_path.stat().st_size,
            "split": split,
            "class_name": class_name if dataset.task_type == "classify" else None
        })
    
    return {
        "files": files,
        "total": total,
        "has_more": has_more,
        "split": split,
        "class_name": class_name
    }

@router.get("/{dataset_id}/image/{filepath:path}")
async def serve_dataset_image(
    dataset_id: int,
    filepath: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_query)
):
    """
    Serve an individual image file from the dataset.
    
    Args:
        dataset_id: Dataset ID
        filepath: Relative path to the file within dataset directory
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        FileResponse with the image
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get dataset directory path
    dataset_dir = dataset.get_dataset_path()
    # Normalize filepath for cross-platform compatibility (handle both / and \)
    normalized_filepath = filepath.replace('/', '\\') if '\\' in str(dataset_dir) else filepath
    file_path = dataset_dir / normalized_filepath
    
    # Security: Ensure file is within dataset directory (prevent directory traversal)
    try:
        file_path = file_path.resolve()
        dataset_dir = dataset_dir.resolve()
        if not str(file_path).startswith(str(dataset_dir)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Validate file extension and determine media type
    extension = file_path.suffix.lower()
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.webp': 'image/webp'
    }
    
    if extension not in media_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )
    
    return FileResponse(
        file_path,
        media_type=media_types[extension],
        headers={"Cache-Control": "public, max-age=3600"}
    )

@router.post("/{dataset_id}/upload-images", response_model=Dict[str, Any])
async def upload_dataset_images(
    dataset_id: int,
    split: str = Form(..., description="Split: train, val, or test"),
    class_name: Optional[str] = Form(None, description="Class name for classification datasets"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Upload multiple images to a specific split/class in the dataset.
    Validates ownership (PROJECT_ADMIN) or allows access (ADMIN).
    
    Args:
        dataset_id: Dataset ID
        split: train, val, or test
        class_name: Class name for classification datasets (required for classify task type)
        files: List of image files to upload
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Dict with upload results
    """
    dataset = check_dataset_ownership(dataset_id, current_user, db)
    
    # Get dataset directory path
    dataset_dir = dataset.get_dataset_path()
    
    # Validate split
    if split not in ["train", "val", "test"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid split. Must be train, val, or test"
        )
    
    # For classification, class_name is required
    if dataset.task_type == "classify" and not class_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="class_name is required for classification datasets"
        )
    
    # Determine target directory
    if dataset.task_type == "classify":
        target_dir = dataset_dir / split / class_name
    else:
        target_dir = dataset_dir / "images" / split
    
    # Create directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Validate and upload files
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    
    uploaded = []
    errors = []
    
    for file in files:
        try:
            # Validate file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in valid_extensions:
                errors.append({
                    "filename": file.filename,
                    "error": f"Invalid file type. Allowed: {', '.join(valid_extensions)}"
                })
                continue
            
            # Read file content to check size
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning
            
            if file_size > MAX_IMAGE_SIZE:
                errors.append({
                    "filename": file.filename,
                    "error": f"File too large. Maximum size is 10MB"
                })
                continue
            
            # Save file
            file_path = target_dir / file.filename
            
            # If file exists, add number suffix
            counter = 1
            original_stem = file_path.stem
            while file_path.exists():
                file_path = target_dir / f"{original_stem}_{counter}{file_ext}"
                counter += 1
            
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file.file, f)
            
            uploaded.append({
                "filename": file.filename,
                "saved_as": file_path.name,
                "size": file_size
            })
            
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    # Update dataset image count
    try:
        validation = validate_yolo_dataset(dataset_dir, dataset.task_type)
        dataset.images_count = validation["images_count"]
        
        # Update status if it was empty
        if dataset.status == DatasetStatus.EMPTY and dataset.images_count > 0:
            if dataset.task_type == "classify":
                dataset.status = DatasetStatus.VALID
            else:
                # For detection, need both images and labels
                dataset.status = DatasetStatus.INCOMPLETE if validation["labels_count"] == 0 else DatasetStatus.VALID
        
        db.commit()
        db.refresh(dataset)
    except Exception as e:
        # Non-fatal error
        print(f"Warning: Failed to update dataset counts: {str(e)}")
    
    return {
        "uploaded": uploaded,
        "errors": errors,
        "total_uploaded": len(uploaded),
        "total_errors": len(errors)
    }

@router.delete("/{dataset_id}/files/{filepath:path}", response_model=Dict[str, Any])
async def delete_dataset_file(
    dataset_id: int,
    filepath: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an individual file from the dataset.
    
    Args:
        dataset_id: Dataset ID
        filepath: Relative path to the file within dataset directory
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dict with deletion status and warnings
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Get dataset directory path
    dataset_dir = dataset.get_dataset_path()
    file_path = dataset_dir / filepath
    
    # Security: Ensure file is within dataset directory (prevent directory traversal)
    try:
        file_path = file_path.resolve()
        dataset_dir = dataset_dir.resolve()
        if not str(file_path).startswith(str(dataset_dir)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    warnings = []
    
    # Check if this is the last file in class folder (for classification)
    if dataset.task_type == "classify":
        class_folder = file_path.parent
        remaining_images = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
            remaining_images.extend(class_folder.glob(ext))
            remaining_images.extend(class_folder.glob(ext.upper()))
        
        if len(remaining_images) == 1:  # This file is the last one
            warnings.append(f"This is the last image in class folder '{class_folder.name}'")
    
    # Delete the file
    try:
        file_path.unlink()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
    
    # Update dataset image count
    try:
        validation = validate_yolo_dataset(dataset_dir, dataset.task_type)
        dataset.images_count = validation["images_count"]
        
        # Update status if needed
        if dataset.images_count == 0:
            dataset.status = DatasetStatus.EMPTY
        elif dataset.task_type in ["detect", "segment"] and validation["labels_count"] == 0:
            dataset.status = DatasetStatus.INCOMPLETE
        
        db.commit()
        db.refresh(dataset)
    except Exception as e:
        # Non-fatal error
        print(f"Warning: Failed to update dataset counts: {str(e)}")
    
    return {
        "deleted": True,
        "filepath": filepath,
        "warnings": warnings
    }

@router.post("/{dataset_id}/recalculate", response_model=Dict[str, Any])
async def recalculate_dataset_stats(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Recalculate dataset statistics (image count, label count, status).
    Useful after fixing duplicate counting issues or manual file modifications.
    
    Args:
        dataset_id: Dataset ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated dataset statistics
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    dataset_dir = dataset.get_dataset_path()
    
    if not dataset_dir.exists():
        # Dataset directory doesn't exist, set counts to 0
        dataset.images_count = 0
        dataset.labels_count = 0
        dataset.status = DatasetStatus.EMPTY
    else:
        try:
            # Validate and recalculate statistics
            validation = validate_yolo_dataset(dataset_dir, dataset.task_type)
            dataset.images_count = validation["images_count"]
            dataset.labels_count = validation["labels_count"]
            
            # Update status based on counts
            if dataset.images_count == 0:
                dataset.status = DatasetStatus.EMPTY
            elif dataset.task_type in ["detect", "segment"] and validation["labels_count"] == 0:
                dataset.status = DatasetStatus.INCOMPLETE
            elif validation["labels_count"] < dataset.images_count:
                dataset.status = DatasetStatus.INCOMPLETE
            else:
                dataset.status = DatasetStatus.VALID
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to recalculate statistics: {str(e)}"
            )
    
    db.commit()
    db.refresh(dataset)
    
    return {
        "id": dataset.id,
        "images_count": dataset.images_count,
        "labels_count": dataset.labels_count,
        "status": dataset.status.value,
        "message": "Dataset statistics recalculated successfully"
    }

@router.get("/{dataset_id}/label/{image_path:path}")
async def get_image_labels(
    dataset_id: int,
    image_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_query)
):
    """
    Get bounding box labels for a specific image.
    Returns image dimensions and existing YOLO format labels.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if dataset.task_type not in ["detect", "segment"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Labeling is only supported for detection and segmentation tasks"
        )
    
    # Get full image path
    from app.config import settings
    # Normalize path for Windows (replace forward slashes with backslashes if needed)
    normalized_image_path = image_path.replace('/', '\\') if '\\' in str(Path(settings.DATA_DIR)) else image_path
    image_full_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id) / normalized_image_path
    
    if not image_full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found"
        )
    
    # Read image dimensions
    try:
        with Image.open(image_full_path) as img:
            image_width, image_height = img.size
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read image: {str(e)}"
        )
    
    # Get label file path (convert images/ to labels/, change extension to .txt)
    label_path = image_path.replace("images/", "labels/")
    label_path = str(Path(label_path).with_suffix(".txt"))
    label_full_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id) / label_path
    
    # Read existing labels if file exists
    boxes = []
    polygons = []
    
    if label_full_path.exists():
        try:
            with open(label_full_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 0:
                        continue
                    
                    class_id = int(parts[0])
                    
                    if dataset.task_type == "detect":
                        # Detection: expect 5 values (class_id + 4 coords)
                        if len(parts) == 5:
                            boxes.append({
                                "class_id": class_id,
                                "x_center": float(parts[1]),
                                "y_center": float(parts[2]),
                                "width": float(parts[3]),
                                "height": float(parts[4])
                            })
                    elif dataset.task_type == "segment":
                        # Segmentation: variable length (class_id + polygon points)
                        if len(parts) >= 7:  # At least 3 points (6 coords) + class_id
                            points = [float(p) for p in parts[1:]]
                            polygons.append({
                                "class_id": class_id,
                                "points": points
                            })
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read label file: {str(e)}"
            )
    
    response = {
        "image_width": image_width,
        "image_height": image_height,
        "task_type": dataset.task_type,
        "classes": dataset.classes_json
    }
    
    if dataset.task_type == "detect":
        response["boxes"] = boxes
    elif dataset.task_type == "segment":
        response["polygons"] = polygons
    
    return response

# IMPORTANT: Segmentation route MUST come BEFORE detection route
# because {image_path:path} is greedy and matches everything including "/segmentation"
@router.post("/{dataset_id}/label/{image_path:path}/segmentation")
async def save_segmentation_labels(
    dataset_id: int,
    image_path: str,
    request_data: SegmentationLabelRequest,
    delete_label: bool = Query(True, description="Delete label file when saving empty polygons"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Save polygon segmentation labels for an image in YOLO format.
    Validates polygon coordinates and creates/updates label file.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if dataset.task_type != "segment":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segmentation labeling is only supported for segmentation tasks"
        )
    
    # Normalize classes_json to ensure it's a proper dict
    normalized_classes = normalize_classes_json(dataset.classes_json)
    
    # Validate class_ids exist in dataset (Pydantic handles structure validation)
    for i, polygon in enumerate(request_data.polygons):
        class_id_str = str(polygon.class_id)
        if class_id_str not in normalized_classes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Polygon {i}: Invalid class_id {polygon.class_id}"
            )
    
    # Get label file path
    from app.config import settings
    label_path = image_path.replace("images/", "labels/")
    label_path = str(Path(label_path).with_suffix(".txt"))
    label_full_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id) / label_path
    
    # Create labels directory if it doesn't exist
    label_full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If no polygons and delete_label is True, delete the label file
    if len(request_data.polygons) == 0:
        if delete_label and label_full_path.exists():
            label_full_path.unlink()
            # Update dataset label count (just count files, skip validation)
            try:
                dataset_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id)
                labels_dir = dataset_path / "labels"
                label_count = 0
                if labels_dir.exists():
                    for split_dir in ["train", "val", "test"]:
                        split_path = labels_dir / split_dir
                        if split_path.exists():
                            label_count += len(list(split_path.glob("*.txt")))
                dataset.labels_count = label_count
                db.commit()
            except Exception:
                pass
            return {
                "success": True,
                "message": "Label file deleted (no polygons)",
                "polygons_saved": 0
            }
        return {
            "success": True,
            "message": "No polygons to save",
            "polygons_saved": 0
        }
    
    # Write YOLO segmentation format labels
    try:
        with open(label_full_path, 'w') as f:
            for polygon in request_data.polygons:
                points_str = ' '.join([f"{p:.6f}" for p in polygon.points])
                f.write(f"{polygon.class_id} {points_str}\n")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write label file: {str(e)}"
        )
    
    # Update dataset label count (just count files, skip validation)
    try:
        dataset_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id)
        labels_dir = dataset_path / "labels"
        label_count = 0
        if labels_dir.exists():
            for split_dir in ["train", "val", "test"]:
                split_path = labels_dir / split_dir
                if split_path.exists():
                    label_count += len(list(split_path.glob("*.txt")))
        dataset.labels_count = label_count
        db.commit()
    except Exception as e:
        print(f"Warning: Failed to update label count: {e}")
    
    return {
        "success": True,
        "message": "Segmentation labels saved successfully",
        "polygons_saved": len(request_data.polygons)
    }

@router.post("/{dataset_id}/label/{image_path:path}")
async def save_image_labels(
    dataset_id: int,
    image_path: str,
    boxes: List[Dict[str, float]],
    delete_label: bool = Query(True, description="Delete label file when saving empty boxes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Save bounding box labels for an image in YOLO format.
    Validates box coordinates and creates/updates label file.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if dataset.task_type != "detect":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Labeling is only supported for detection tasks"
        )
    
    # Validate all boxes
    for i, box in enumerate(boxes):
        required_fields = ["class_id", "x_center", "y_center", "width", "height"]
        for field in required_fields:
            if field not in box:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Box {i}: Missing required field '{field}'"
                )
        
        # Validate coordinates are within bounds
        if not (0 <= box["x_center"] <= 1 and 0 <= box["y_center"] <= 1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Box {i}: Center coordinates must be between 0 and 1"
            )
        
        if not (0 < box["width"] <= 1 and 0 < box["height"] <= 1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Box {i}: Width and height must be between 0 and 1"
            )
        
        # Check that box doesn't extend outside image
        half_w = box["width"] / 2
        half_h = box["height"] / 2
        if (box["x_center"] - half_w < 0 or box["x_center"] + half_w > 1 or
            box["y_center"] - half_h < 0 or box["y_center"] + half_h > 1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Box {i}: Bounding box extends outside image bounds"
            )
        
        # Validate class_id exists in dataset
        normalized_classes = normalize_classes_json(dataset.classes_json)
        class_id_str = str(int(box["class_id"]))
        if class_id_str not in normalized_classes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Box {i}: Invalid class_id {box['class_id']}"
            )
    
    # Get label file path
    from app.config import settings
    label_path = image_path.replace("images/", "labels/")
    label_path = str(Path(label_path).with_suffix(".txt"))
    label_full_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id) / label_path
    
    # Create labels directory if it doesn't exist
    label_full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If no boxes and delete_label is True, delete the label file
    if len(boxes) == 0:
        if delete_label and label_full_path.exists():
            label_full_path.unlink()
            # Update dataset label count
            try:
                dataset_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id)
                validation_result = validate_yolo_dataset(dataset_path, dataset.task_type)
                dataset.labels_count = validation_result.get("labels_count", 0)
                db.commit()
            except Exception:
                pass
            return {
                "success": True,
                "message": "Label file deleted (no boxes)",
                "boxes_saved": 0
            }
        return {
            "success": True,
            "message": "No boxes to save",
            "boxes_saved": 0
        }
    
    # Write YOLO format labels
    try:
        with open(label_full_path, 'w') as f:
            for box in boxes:
                f.write(f"{int(box['class_id'])} {box['x_center']:.6f} {box['y_center']:.6f} {box['width']:.6f} {box['height']:.6f}\n")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write label file: {str(e)}"
        )
    
    # Update dataset label count
    try:
        dataset_path = Path(settings.DATA_DIR) / "datasets" / str(dataset.id)
        validation_result = validate_yolo_dataset(dataset_path, dataset.task_type)
        dataset.labels_count = validation_result.get("labels_count", 0)
        db.commit()
    except Exception as e:
        # Don't fail the request if count update fails
        print(f"Warning: Failed to update label count: {e}")
    
    return {
        "success": True,
        "message": "Labels saved successfully",
        "boxes_saved": len(boxes)
    }

@router.post("/{dataset_id}/rescan-classes", response_model=Dict[str, Any])
async def rescan_classification_classes(
    dataset_id: int,
    splits: List[str] = Query(["train", "val", "test"], description="Splits to scan"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Rescan class folders in classification datasets and update classes_json.
    Scans the specified splits (train, val, test) and adds any folder names
    that aren't already in classes_json.
    
    Args:
        dataset_id: Dataset ID
        splits: List of splits to scan (train, val, test)
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Result with discovered classes and update status
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    if dataset.task_type != "classify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rescan classes is only available for classification datasets"
        )
    
    dataset_dir = dataset.get_dataset_path()
    
    if not dataset_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset directory does not exist"
        )
    
    # Get current classes (values only, not IDs)
    current_classes = set(dataset.classes_json.values()) if dataset.classes_json else set()
    
    # Discover class folders from filesystem
    discovered_classes = set()
    scanned_splits = []
    
    for split in splits:
        split_dir = dataset_dir / split
        if split_dir.exists() and split_dir.is_dir():
            scanned_splits.append(split)
            for item in split_dir.iterdir():
                if item.is_dir():
                    discovered_classes.add(item.name)
    
    # Find new classes that aren't in current classes_json
    new_classes = discovered_classes - current_classes
    
    if not new_classes:
        return {
            "success": True,
            "message": "No new classes found",
            "scanned_splits": scanned_splits,
            "discovered_classes": sorted(list(discovered_classes)),
            "new_classes": [],
            "total_classes": len(current_classes)
        }
    
    # Add new classes to classes_json
    # First normalize existing classes_json
    normalized_existing = normalize_classes_json(dataset.classes_json)
    
    # Find next available ID
    existing_ids = [int(k) for k in normalized_existing.keys()] if normalized_existing else []
    next_id = max(existing_ids) + 1 if existing_ids else 0
    
    updated_classes = dict(normalized_existing)
    added_classes = []
    
    for class_name in sorted(new_classes):
        updated_classes[str(next_id)] = class_name
        added_classes.append({"id": str(next_id), "name": class_name})
        next_id += 1
    
    # Update dataset with normalized classes
    dataset.classes_json = normalize_classes_json(updated_classes)
    db.commit()
    db.refresh(dataset)
    
    return {
        "success": True,
        "message": f"Added {len(new_classes)} new class(es)",
        "scanned_splits": scanned_splits,
        "discovered_classes": sorted(list(discovered_classes)),
        "new_classes": added_classes,
        "total_classes": len(updated_classes)
    }

@router.post("/{dataset_id}/distribute", response_model=Dict[str, Any])
async def distribute_classification_dataset(
    dataset_id: int,
    seed: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Redistribute classification dataset images across train/val/test splits.
    Uses hardcoded 80/10/10 ratio with per-class stratified distribution.
    Checks if dataset already meets target distribution before redistributing.
    
    Args:
        dataset_id: Dataset ID
        seed: Optional seed for reproducible shuffling
        db: Database session
        current_user: Current authenticated user (PROJECT_ADMIN or ADMIN)
        
    Returns:
        Distribution results with warnings
    """
    from app.utils.file_handler import distribute_classification_images
    
    dataset = check_dataset_ownership(dataset_id, current_user, db)
    
    if dataset.task_type != "classify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Distribution is only supported for classification datasets"
        )
    
    dataset_dir = dataset.get_dataset_path()
    
    if not dataset_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset directory does not exist"
        )
    
    if not dataset.classes_json or len(dataset.classes_json) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No classes defined. Please add classes before distributing."
        )
    
    # Calculate current distribution
    current_distribution = {"train": 0, "val": 0, "test": 0}
    
    for class_name in dataset.classes_json.values():
        for split in ["train", "val", "test"]:
            class_dir = dataset_dir / split / class_name
            if class_dir.exists() and class_dir.is_dir():
                # Count images with deduplication
                image_set = set()
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.webp']:
                    for img_path in class_dir.glob(ext):
                        image_set.add(img_path.resolve())
                    for img_path in class_dir.glob(ext.upper()):
                        image_set.add(img_path.resolve())
                current_distribution[split] += len(image_set)
    
    total_images = sum(current_distribution.values())
    
    if total_images == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot distribute empty dataset. Please add images first."
        )
    
    # Check if already optimal (within ±5% tolerance)
    current_train_ratio = current_distribution["train"] / total_images
    current_val_ratio = current_distribution["val"] / total_images
    current_test_ratio = current_distribution["test"] / total_images
    
    TOLERANCE = 0.05
    TARGET_TRAIN = 0.8
    TARGET_VAL = 0.1
    TARGET_TEST = 0.1
    
    is_optimal = (
        abs(current_train_ratio - TARGET_TRAIN) <= TOLERANCE and
        abs(current_val_ratio - TARGET_VAL) <= TOLERANCE and
        abs(current_test_ratio - TARGET_TEST) <= TOLERANCE
    )
    
    if is_optimal:
        return {
            "success": True,
            "already_optimal": True,
            "message": "Dataset already meets target distribution (80/10/10 ±5%)",
            "current_distribution": current_distribution,
            "current_ratios": {
                "train": round(current_train_ratio * 100, 1),
                "val": round(current_val_ratio * 100, 1),
                "test": round(current_test_ratio * 100, 1)
            }
        }
    
    # Perform distribution
    try:
        result = distribute_classification_images(
            dataset_dir,
            dataset.classes_json,
            seed
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to distribute images: {str(e)}"
        )
    
    # Update dataset image count and status
    try:
        validation = validate_yolo_dataset(dataset_dir, dataset.task_type)
        dataset.images_count = validation["images_count"]
        
        # Update status to VALID if dataset meets requirements
        # For classification: needs images and classes defined
        if validation["valid"] and dataset.images_count > 0 and dataset.classes_json:
            dataset.status = DatasetStatus.VALID
        
        db.commit()
        db.refresh(dataset)
    except Exception as e:
        # Non-fatal error
        print(f"Warning: Failed to update dataset info: {str(e)}")
    
    # Calculate percentages for response
    final_total = sum(result["distribution"].values())
    percentages = {}
    if final_total > 0:
        percentages = {
            "train": round(result["distribution"]["train"] / final_total * 100, 1),
            "val": round(result["distribution"]["val"] / final_total * 100, 1),
            "test": round(result["distribution"]["test"] / final_total * 100, 1)
        }
    
    return {
        "success": True,
        "message": f"Distributed {final_total} images across splits (moved {result['moved_images']} images)",
        "distribution": result["distribution"],
        "percentages": percentages,
        "warnings": result["warnings"],
        "classes_processed": result["classes_processed"]
    }

@router.post("/{dataset_id}/validate", response_model=Dict[str, Any])
async def validate_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Validate a dataset and change its status from INCOMPLETE to VALID if requirements are met.
    For detection datasets, checks if:
    - Dataset has images
    - Dataset has a data.yaml file
    - At least some images have labels (labels_count > 0)
    - Classes are defined
    
    Args:
        dataset_id: Dataset ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Validation result with status
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    dataset_dir = dataset.get_dataset_path()
    
    if not dataset_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset directory does not exist"
        )
    
    # First, recalculate stats to ensure accurate counts
    try:
        validation = validate_yolo_dataset(dataset_dir, dataset.task_type)
        dataset.images_count = validation["images_count"]
        dataset.labels_count = validation["labels_count"]
        db.commit()
        db.refresh(dataset)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recalculate statistics: {str(e)}"
        )
    
    # Validation checks
    errors = []
    warnings = []
    
    # Check if dataset has images
    if dataset.images_count == 0:
        errors.append("Dataset has no images")
    
    # Check task type specific requirements
    if dataset.task_type in ["detect", "segment"]:
        # Check if classes are defined
        if not dataset.classes_json or len(dataset.classes_json) == 0:
            errors.append("No classes defined")
        
        # Auto-generate data.yaml if missing
        yaml_path = dataset_dir / "data.yaml"
        if not yaml_path.exists():
            try:
                # Check if has splits
                images_dir = dataset_dir / "images"
                has_splits = (images_dir / "train").exists() or (images_dir / "val").exists() or (images_dir / "test").exists()
                
                # Normalize classes_json to dict format
                classes_dict = normalize_classes_json(dataset.classes_json)
                
                # Generate data.yaml
                generated_yaml = create_yolo_yaml(
                    dataset_dir,
                    dataset.name,
                    classes_dict,
                    has_splits,
                    dataset.task_type
                )
                
                if generated_yaml:
                    dataset.yaml_path = str(generated_yaml)
                    warnings.append("data.yaml was missing and has been automatically generated")
                else:
                    errors.append("Failed to generate data.yaml file")
            except Exception as e:
                errors.append(f"Failed to generate data.yaml: {str(e)}")
        
        # Check if at least some labels exist
        if dataset.labels_count == 0:
            errors.append("No labels found. At least some images must have labels.")
        
        # Warning if not all images are labeled
        if dataset.labels_count < dataset.images_count:
            warnings.append(f"Only {dataset.labels_count} out of {dataset.images_count} images have labels")
        
        # Check if splits have images
        images_dir = dataset_dir / "images"
        if images_dir.exists():
            train_dir = images_dir / "train"
            val_dir = images_dir / "val"
            
            if train_dir.exists():
                train_images = list(train_dir.glob("*.jpg")) + list(train_dir.glob("*.png"))
                if len(train_images) == 0:
                    warnings.append("Train split has no images")
            else:
                errors.append("Train split directory not found")
            
            if val_dir.exists():
                val_images = list(val_dir.glob("*.jpg")) + list(val_dir.glob("*.png"))
                if len(val_images) == 0:
                    warnings.append("Validation split has no images")
    
    # If there are errors, cannot validate
    if errors:
        return {
            "success": False,
            "status": dataset.status.value,
            "errors": errors,
            "warnings": warnings,
            "message": "Validation failed. Please fix the errors before validating."
        }
    
    # Update status to VALID
    dataset.status = DatasetStatus.VALID
    db.commit()
    db.refresh(dataset)
    
    return {
        "success": True,
        "status": dataset.status.value,
        "errors": [],
        "warnings": warnings,
        "message": "Dataset validated successfully and marked as VALID"
    }

@router.post("/admin/normalize-classes", response_model=Dict[str, Any])
async def normalize_all_classes_json(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Admin endpoint to normalize all datasets' classes_json to consistent dict format.
    
    Fixes datasets that have classes_json stored as list of dicts:
    [{'0': 'helmet'}, {'1': 'gloves'}] -> {'0': 'helmet', '1': 'gloves'}
    
    Returns:
        Summary of normalization results
    """
    from app.models.user import UserRole
    
    # Only ADMIN can run this
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN users can normalize all datasets"
        )
    
    datasets = db.query(Dataset).all()
    normalized_count = 0
    errors = []
    
    for dataset in datasets:
        try:
            if dataset.classes_json:
                original = dataset.classes_json
                normalized = normalize_classes_json(dataset.classes_json)
                
                # Check if it changed
                if original != normalized:
                    dataset.classes_json = normalized
                    normalized_count += 1
                    print(f"Normalized dataset {dataset.id} ({dataset.name})")
        except Exception as e:
            errors.append(f"Dataset {dataset.id}: {str(e)}")
    
    if normalized_count > 0:
        db.commit()
    
    return {
        "success": True,
        "total_datasets": len(datasets),
        "normalized_count": normalized_count,
        "errors": errors,
        "message": f"Successfully normalized {normalized_count} datasets"
    }
