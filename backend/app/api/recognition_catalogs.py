"""
Recognition Catalog API Router
"""
import time
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.models.recognition import RecognitionCatalog, RecognitionLabel, RecognitionImage, RecognitionJob
from app.schemas.recognition import (
    RecognitionCatalogCreate,
    RecognitionCatalogResponse,
    RecognitionCatalogDetail,
    RecognitionCatalogUpdate,
    RecognitionLabelCreate,
    RecognitionLabelResponse,
    RecognitionLabelDetail,
    RecognitionLabelUpdate,
    RecognitionImageResponse,
    RecognitionJobResponse,
    SimilaritySearchResponse,
    SimilarityMatchResponse,
    RecognitionCatalogStats
)
from app.utils.auth import get_current_active_user
from app.utils.permissions import (
    require_project_admin_or_admin,
    check_catalog_ownership,
    filter_query_by_ownership
)
from app.services.recognition_service import get_recognition_service
from app.workers.recognition_worker import recognition_worker
from app.config import settings
from datetime import datetime, timezone

router = APIRouter(prefix="/api/recognition-catalogs", tags=["Recognition Catalogs"])

# ===== Catalog Endpoints =====
@router.get("", response_model=List[RecognitionCatalogResponse])
async def list_catalogs(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """
    Get list of recognition catalogs.
    PROJECT_ADMIN sees only their own catalogs.
    ADMIN sees all catalogs.
    """
    query = db.query(RecognitionCatalog)
    query = filter_query_by_ownership(query, RecognitionCatalog, current_user)
    
    if category:
        query = query.filter(RecognitionCatalog.category == category)
    
    catalogs = query.offset(skip).limit(limit).all()
    return catalogs

@router.get("/categories", response_model=List[str])
async def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """Get list of unique categories from user's catalogs."""
    query = db.query(RecognitionCatalog.category).distinct()
    query = filter_query_by_ownership(query, RecognitionCatalog, current_user)
    
    categories = [row[0] for row in query.all()]
    return categories

@router.post("", response_model=RecognitionCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_catalog(
    catalog_data: RecognitionCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_admin_or_admin)
):
    """Create a new recognition catalog."""
    # Create catalog record
    new_catalog = RecognitionCatalog(
        name=catalog_data.name,
        description=catalog_data.description,
        category=catalog_data.category,
        creator_id=current_user.id,
        image_count=0,
        label_count=0
    )
    
    db.add(new_catalog)
    db.commit()
    db.refresh(new_catalog)
    
    # Create directory structure
    catalog_dir = new_catalog.get_catalog_path()
    catalog_dir.mkdir(parents=True, exist_ok=True)
    
    return new_catalog

@router.get("/{catalog_id}", response_model=RecognitionCatalogDetail)
async def get_catalog(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed catalog information with labels."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    # Check ownership
    check_catalog_ownership(catalog, current_user)
    
    return catalog

@router.patch("/{catalog_id}", response_model=RecognitionCatalogResponse)
async def update_catalog(
    catalog_id: int,
    catalog_data: RecognitionCatalogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update catalog information."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Update fields
    if catalog_data.name is not None:
        catalog.name = catalog_data.name
    if catalog_data.description is not None:
        catalog.description = catalog_data.description
    if catalog_data.category is not None:
        catalog.category = catalog_data.category
    
    catalog.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(catalog)
    
    return catalog

@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catalog(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a catalog and all its data."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Delete directory
    catalog_dir = catalog.get_catalog_path()
    if catalog_dir.exists():
        shutil.rmtree(catalog_dir)
    
    # Delete from database (cascades to labels and images)
    db.delete(catalog)
    db.commit()

# ===== Label Endpoints =====
@router.get("/{catalog_id}/labels", response_model=List[RecognitionLabelResponse])
async def list_labels(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of labels in a catalog."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    labels = db.query(RecognitionLabel).filter(RecognitionLabel.catalog_id == catalog_id).all()
    return labels

@router.post("/{catalog_id}/labels", response_model=RecognitionLabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    catalog_id: int,
    label_data: RecognitionLabelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new label in a catalog."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Check if label already exists
    existing_label = db.query(RecognitionLabel).filter(
        RecognitionLabel.catalog_id == catalog_id,
        RecognitionLabel.label_name == label_data.label_name
    ).first()
    
    if existing_label:
        raise HTTPException(status_code=400, detail=f"Label '{label_data.label_name}' already exists in this catalog")
    
    # Create label
    new_label = RecognitionLabel(
        catalog_id=catalog_id,
        label_name=label_data.label_name,
        description=label_data.description,
        image_count=0
    )
    
    db.add(new_label)
    
    # Update catalog label count
    catalog.label_count += 1
    catalog.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(new_label)
    
    return new_label

@router.get("/{catalog_id}/labels/{label_id}", response_model=RecognitionLabelDetail)
async def get_label(
    catalog_id: int,
    label_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed label information with images."""
    label = db.query(RecognitionLabel).filter(
        RecognitionLabel.id == label_id,
        RecognitionLabel.catalog_id == catalog_id
    ).first()
    
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    
    # Check catalog ownership
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    check_catalog_ownership(catalog, current_user)
    
    return label

@router.patch("/{catalog_id}/labels/{label_id}", response_model=RecognitionLabelResponse)
async def update_label(
    catalog_id: int,
    label_id: int,
    label_data: RecognitionLabelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update label information."""
    label = db.query(RecognitionLabel).filter(
        RecognitionLabel.id == label_id,
        RecognitionLabel.catalog_id == catalog_id
    ).first()
    
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    check_catalog_ownership(catalog, current_user)
    
    # Update fields
    if label_data.label_name is not None:
        # Check for duplicate
        existing = db.query(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id,
            RecognitionLabel.label_name == label_data.label_name,
            RecognitionLabel.id != label_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Label '{label_data.label_name}' already exists")
        
        label.label_name = label_data.label_name
    
    if label_data.description is not None:
        label.description = label_data.description
    
    label.updated_at = datetime.now(timezone.utc)
    catalog.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(label)
    
    return label

@router.delete("/{catalog_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    catalog_id: int,
    label_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a label and all its images."""
    label = db.query(RecognitionLabel).filter(
        RecognitionLabel.id == label_id,
        RecognitionLabel.catalog_id == catalog_id
    ).first()
    
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    check_catalog_ownership(catalog, current_user)
    
    # Update catalog counts
    catalog.label_count -= 1
    catalog.image_count -= label.image_count
    catalog.updated_at = datetime.now(timezone.utc)
    
    # Delete from database (cascades to images)
    db.delete(label)
    db.commit()

# ===== Image Upload Endpoints =====
@router.post("/{catalog_id}/labels/{label_id}/images", response_model=List[RecognitionImageResponse])
async def upload_images(
    catalog_id: int,
    label_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload images for a label.
    Sync processing for ≤5 images, background worker for >5 images.
    """
    # Validate catalog and label
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    label = db.query(RecognitionLabel).filter(
        RecognitionLabel.id == label_id,
        RecognitionLabel.catalog_id == catalog_id
    ).first()
    
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    
    # Create directory for label
    label_dir = catalog.get_catalog_path() / f"label_{label_id}"
    label_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded files
    saved_images = []
    recognition_service = get_recognition_service()
    
    for file in files:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            continue
        
        # Generate unique filename
        timestamp = int(time.time() * 1000)
        filename = f"{timestamp}_{file.filename}"
        file_path = label_dir / filename
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Create thumbnail
        thumbnail_dir = label_dir / "thumbnails"
        thumbnail_dir.mkdir(exist_ok=True)
        thumbnail_path = thumbnail_dir / filename
        recognition_service.create_thumbnail(str(file_path), str(thumbnail_path))
        
        # Create database record
        relative_path = f"recognition_catalogs/{catalog_id}/label_{label_id}/{filename}"
        relative_thumbnail = f"recognition_catalogs/{catalog_id}/label_{label_id}/thumbnails/{filename}"
        
        new_image = RecognitionImage(
            label_id=label_id,
            image_path=relative_path,
            thumbnail_path=relative_thumbnail,
            is_processed=False
        )
        
        db.add(new_image)
        saved_images.append(new_image)
    
    db.commit()
    
    # Refresh to get IDs
    for img in saved_images:
        db.refresh(img)
    
    image_ids = [img.id for img in saved_images]
    
    # Process embeddings: sync for ≤5 images, background worker for >5
    if len(saved_images) <= 5:
        # Sync processing
        print(f"🔄 Processing {len(saved_images)} images synchronously...")
        
        for img in saved_images:
            try:
                abs_path = Path(settings.DATA_DIR) / img.image_path
                embedding = recognition_service.generate_embedding(str(abs_path))
                
                img.embedding = embedding
                img.is_processed = True
            except Exception as e:
                print(f"❌ Failed to process {img.image_path}: {e}")
        
        # Update counts
        label.image_count = db.query(RecognitionImage).filter(
            RecognitionImage.label_id == label_id
        ).count()
        
        catalog.image_count = db.query(RecognitionImage).join(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id
        ).count()
        
        db.commit()
        
    else:
        # Background processing
        print(f"🔄 Processing {len(saved_images)} images in background...")
        
        # Create job
        job = RecognitionJob(
            catalog_id=catalog_id,
            label_id=label_id,
            total_images=len(saved_images),
            processed_images=0,
            failed_images=0,
            status="pending"
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Start worker
        recognition_worker.start_embedding_job(
            job_id=job.id,
            catalog_id=catalog_id,
            label_id=label_id,
            image_ids=image_ids
        )
    
    return saved_images

@router.get("/{catalog_id}/labels/{label_id}/images/{image_id}")
async def get_image(
    catalog_id: int,
    label_id: int,
    image_id: int,
    thumbnail: bool = False,
    db: Session = Depends(get_db)
):
    """Download image or thumbnail (public endpoint for browser image loading)."""
    image = db.query(RecognitionImage).filter(RecognitionImage.id == image_id).first()
    
    if not image or image.label_id != label_id:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Validate catalog exists (no ownership check for public image access)
    label = db.query(RecognitionLabel).filter(RecognitionLabel.id == label_id).first()
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    # Build path
    if thumbnail and image.thumbnail_path:
        file_path = Path(settings.DATA_DIR) / image.thumbnail_path
    else:
        file_path = Path(settings.DATA_DIR) / image.image_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

# ===== Similarity Search Endpoint =====
@router.post("/{catalog_id}/search", response_model=SimilaritySearchResponse)
async def search_similar(
    catalog_id: int,
    query_image: UploadFile = File(...),
    search_params: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search for similar images in catalog using uploaded query image.
    """
    import json
    
    # Parse search params
    try:
        params = json.loads(search_params)
        top_k = params.get("top_k", 5)
        threshold = params.get("threshold", 0.5)
        label_filter = params.get("label_filter")
    except:
        top_k = 5
        threshold = 0.5
        label_filter = None
    
    # Validate catalog
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Save query image temporarily
    temp_dir = Path(settings.DATA_DIR) / "temp"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"query_{int(time.time() * 1000)}_{query_image.filename}"
    
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(query_image.file, f)
    
    try:
        # Generate embedding for query image
        start_time = time.time()
        recognition_service = get_recognition_service()
        query_embedding = recognition_service.generate_embedding(str(temp_path))
        
        # Fetch processed images from database
        query = db.query(
            RecognitionImage.id,
            RecognitionImage.embedding,
            RecognitionImage.image_path,
            RecognitionImage.thumbnail_path,
            RecognitionLabel.id.label("label_id"),
            RecognitionLabel.label_name
        ).join(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id,
            RecognitionImage.is_processed == True
        )
        
        # Apply label filter if specified
        if label_filter:
            query = query.filter(RecognitionLabel.id.in_(label_filter))
        
        db_images_raw = query.all()
        
        # Convert to dict format for search
        db_images = [
            {
                "id": row.id,
                "embedding": row.embedding,
                "image_path": row.image_path,
                "thumbnail_path": row.thumbnail_path,
                "label_id": row.label_id,
                "label_name": row.label_name
            }
            for row in db_images_raw
        ]
        
        # Search
        matches = recognition_service.search_database(
            query_embedding=query_embedding,
            db_images=db_images,
            top_k=top_k,
            threshold=threshold
        )
        
        inference_time = (time.time() - start_time) * 1000
        
        # Convert to response format
        match_responses = [
            SimilarityMatchResponse(
                label_id=match.label_id,
                label_name=match.label_name,
                image_id=match.image_id,
                image_path=match.image_path,
                thumbnail_path=db_images[[img["id"] for img in db_images].index(match.image_id)]["thumbnail_path"],
                similarity_score=match.similarity_score,
                distance_metric=match.distance_metric
            )
            for match in matches
        ]
        
        return SimilaritySearchResponse(
            query_image_path=str(temp_path.name),
            matches=match_responses,
            inference_time_ms=inference_time,
            total_candidates=len(db_images)
        )
        
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()

# ===== Semantic Text Search Endpoint =====
@router.post("/{catalog_id}/search/text", response_model=SimilaritySearchResponse)
async def search_by_text(
    catalog_id: int,
    text_query: str = Form(...),
    top_k: int = Form(5),
    threshold: float = Form(0.5),
    label_filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Semantic text search: Find images matching natural language descriptions.
    Examples: "a happy child in nature", "futuristic city skyline at night"
    
    Uses CLIP's multimodal embeddings to match text queries with images.
    """
    import json
    
    # Parse label filter if provided
    label_filter_list = None
    if label_filter:
        try:
            label_filter_list = json.loads(label_filter)
        except:
            pass
    
    # Validate catalog
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    try:
        # Generate embedding for text query
        start_time = time.time()
        recognition_service = get_recognition_service()
        query_embedding = recognition_service.generate_text_embedding(text_query)
        
        # Fetch processed images from database
        query = db.query(
            RecognitionImage.id,
            RecognitionImage.embedding,
            RecognitionImage.image_path,
            RecognitionImage.thumbnail_path,
            RecognitionLabel.id.label("label_id"),
            RecognitionLabel.label_name
        ).join(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id,
            RecognitionImage.is_processed == True
        )
        
        # Apply label filter if specified
        if label_filter_list:
            query = query.filter(RecognitionLabel.id.in_(label_filter_list))
        
        db_images_raw = query.all()
        
        # Convert to dict format for search
        db_images = [
            {
                "id": row.id,
                "embedding": row.embedding,
                "image_path": row.image_path,
                "thumbnail_path": row.thumbnail_path,
                "label_id": row.label_id,
                "label_name": row.label_name
            }
            for row in db_images_raw
        ]
        
        # Search using text embedding
        matches = recognition_service.search_database(
            query_embedding=query_embedding,
            db_images=db_images,
            top_k=top_k,
            threshold=threshold
        )
        
        inference_time = (time.time() - start_time) * 1000
        
        # Convert to response format
        match_responses = [
            SimilarityMatchResponse(
                label_id=match.label_id,
                label_name=match.label_name,
                image_id=match.image_id,
                image_path=match.image_path,
                thumbnail_path=db_images[[img["id"] for img in db_images].index(match.image_id)]["thumbnail_path"],
                similarity_score=match.similarity_score,
                distance_metric=match.distance_metric
            )
            for match in matches
        ]
        
        return SimilaritySearchResponse(
            query_image_path=f"text_query: {text_query}",
            matches=match_responses,
            inference_time_ms=inference_time,
            total_candidates=len(db_images)
        )
        
    except Exception as e:
        print(f"Error in semantic text search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

# ===== Job Status Endpoint =====
@router.get("/jobs/{job_id}", response_model=RecognitionJobResponse)
async def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recognition job status."""
    job = db.query(RecognitionJob).filter(RecognitionJob.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check catalog ownership
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == job.catalog_id).first()
    check_catalog_ownership(catalog, current_user)
    
    return job

# ===== Statistics Endpoint =====
@router.get("/{catalog_id}/stats", response_model=RecognitionCatalogStats)
async def get_catalog_stats(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get catalog statistics."""
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Calculate stats
    total_images = db.query(RecognitionImage).join(RecognitionLabel).filter(
        RecognitionLabel.catalog_id == catalog_id
    ).count()
    
    processed_images = db.query(RecognitionImage).join(RecognitionLabel).filter(
        RecognitionLabel.catalog_id == catalog_id,
        RecognitionImage.is_processed == True
    ).count()
    
    unprocessed_images = total_images - processed_images
    
    avg_images = total_images / catalog.label_count if catalog.label_count > 0 else 0
    
    return RecognitionCatalogStats(
        catalog_id=catalog.id,
        catalog_name=catalog.name,
        category=catalog.category,
        total_labels=catalog.label_count,
        total_images=total_images,
        processed_images=processed_images,
        unprocessed_images=unprocessed_images,
        average_images_per_label=avg_images
    )

# ===== ZIP Upload Endpoint =====
@router.post("/{catalog_id}/upload-zip", status_code=status.HTTP_201_CREATED)
async def upload_zip(
    catalog_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a ZIP file containing classification dataset structure.
    ZIP structure: data.zip -> LabelName1/ -> image1.jpg, image2.jpg
                               LabelName2/ -> image1.png, image2.png
    Each folder becomes a label, images inside are added to that label.
    """
    # Validate catalog
    catalog = db.query(RecognitionCatalog).filter(RecognitionCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    
    check_catalog_ownership(catalog, current_user)
    
    # Validate file is a ZIP
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")
    
    # Create temp directory for extraction
    temp_dir = Path(settings.DATA_DIR) / "temp" / f"zip_upload_{int(time.time() * 1000)}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded ZIP
    zip_path = temp_dir / file.filename
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    try:
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir / "extracted")
        
        extracted_root = temp_dir / "extracted"
        
        # Process folder structure
        labels_created = 0
        images_uploaded = 0
        recognition_service = get_recognition_service()
        
        # Find all directories (each is a label)
        for label_dir in extracted_root.iterdir():
            if not label_dir.is_dir():
                continue
            
            # Skip hidden/system folders
            if label_dir.name.startswith('.') or label_dir.name.startswith('__'):
                continue
            
            label_name = label_dir.name
            
            # Check if label already exists
            existing_label = db.query(RecognitionLabel).filter(
                RecognitionLabel.catalog_id == catalog_id,
                RecognitionLabel.label_name == label_name
            ).first()
            
            if existing_label:
                # Use existing label
                label = existing_label
            else:
                # Create new label
                label = RecognitionLabel(
                    catalog_id=catalog_id,
                    label_name=label_name,
                    description=f"Imported from ZIP: {file.filename}",
                    image_count=0
                )
                db.add(label)
                db.flush()  # Get label ID
                labels_created += 1
            
            # Create directory for label
            label_storage_dir = catalog.get_catalog_path() / f"label_{label.id}"
            label_storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Process images in this label folder
            image_files = []
            for img_file in label_dir.iterdir():
                if not img_file.is_file():
                    continue
                
                # Check if it's an image
                if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']:
                    continue
                
                # Generate unique filename
                timestamp = int(time.time() * 1000)
                new_filename = f"{timestamp}_{img_file.name}"
                dest_path = label_storage_dir / new_filename
                
                # Copy image
                shutil.copy2(img_file, dest_path)
                
                # Create thumbnail
                thumbnail_dir = label_storage_dir / "thumbnails"
                thumbnail_dir.mkdir(exist_ok=True)
                thumbnail_path = thumbnail_dir / new_filename
                recognition_service.create_thumbnail(str(dest_path), str(thumbnail_path))
                
                # Create database record
                relative_path = f"recognition_catalogs/{catalog_id}/label_{label.id}/{new_filename}"
                relative_thumbnail = f"recognition_catalogs/{catalog_id}/label_{label.id}/thumbnails/{new_filename}"
                
                new_image = RecognitionImage(
                    label_id=label.id,
                    image_path=relative_path,
                    thumbnail_path=relative_thumbnail,
                    is_processed=False
                )
                
                db.add(new_image)
                image_files.append(new_image)
                images_uploaded += 1
            
            # Commit images for this label
            db.commit()
            
            # Refresh to get IDs
            for img in image_files:
                db.refresh(img)
            
            # Process embeddings: sync for ≤5 images, background for >5
            if len(image_files) <= 5 and len(image_files) > 0:
                # Sync processing
                for img in image_files:
                    try:
                        abs_path = Path(settings.DATA_DIR) / img.image_path
                        embedding = recognition_service.generate_embedding(str(abs_path))
                        img.embedding = embedding
                        img.is_processed = True
                    except Exception as e:
                        print(f"❌ Failed to process {img.image_path}: {e}")
                
                db.commit()
            elif len(image_files) > 5:
                # Background processing
                job = RecognitionJob(
                    catalog_id=catalog_id,
                    label_id=label.id,
                    total_images=len(image_files),
                    processed_images=0,
                    failed_images=0,
                    status="pending"
                )
                
                db.add(job)
                db.commit()
                db.refresh(job)
                
                # Start worker
                image_ids = [img.id for img in image_files]
                recognition_worker.start_embedding_job(
                    job_id=job.id,
                    catalog_id=catalog_id,
                    label_id=label.id,
                    image_ids=image_ids
                )
        
        # Update catalog counts
        catalog.label_count = db.query(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id
        ).count()
        
        catalog.image_count = db.query(RecognitionImage).join(RecognitionLabel).filter(
            RecognitionLabel.catalog_id == catalog_id
        ).count()
        
        # Update each label's image count
        for label_obj in db.query(RecognitionLabel).filter(RecognitionLabel.catalog_id == catalog_id).all():
            label_obj.image_count = db.query(RecognitionImage).filter(
                RecognitionImage.label_id == label_obj.id
            ).count()
        
        db.commit()
        
        return {
            "message": "ZIP uploaded successfully",
            "labels_created": labels_created,
            "images_uploaded": images_uploaded,
            "catalog_id": catalog_id
        }
        
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP: {str(e)}")
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
