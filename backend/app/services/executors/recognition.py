"""
Recognition Executor
Handles CLIP-based recognition workflow nodes.
"""
import logging
import cv2
from typing import Dict, Any
from pathlib import Path
from PIL import Image

from app.services.executors.base import NodeExecutorBase
from app.services.recognition_service import get_recognition_service
from app.db import SessionLocal
from app.models.recognition import RecognitionCatalog
from app.utils.image_processing import crop_bbox_with_padding, normalize_bbox_coordinates
from app.config import settings

logger = logging.getLogger(__name__)


class RecognitionExecutor(NodeExecutorBase):
    """Executor for recognition nodes using CLIP-based similarity search."""
    
    def __init__(self):
        super().__init__("recognition")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute recognition on detection results.
        
        Crops detected bounding boxes with padding, generates CLIP embeddings,
        performs pgvector similarity search, and creates annotated images with
        recognition labels.
        """
        validated = self.validate_config(config)
        db = SessionLocal()
        
        try:
            # Get recognition catalog
            catalog = db.query(RecognitionCatalog).filter(
                RecognitionCatalog.id == validated.catalog_id
            ).first()
            
            if not catalog:
                raise ValueError(f"Recognition catalog {validated.catalog_id} not found")
            
            logger.info(f"Recognition node {node_id}: Using catalog '{catalog.name}' (ID: {catalog.id})")
            
            # Get detection results from parent nodes
            dependency_outputs = context.get('_dependency_outputs', {})
            detection_results = []
            detection_job_id = None
            
            for dep_id, dep_output in dependency_outputs.items():
                if 'results' in dep_output and dep_output.get('job_type') == 'prediction':
                    detection_results = dep_output['results']
                    detection_job_id = dep_output.get('job_id')
                    logger.info(f"Recognition node {node_id}: Found {len(detection_results)} results from job {detection_job_id}")
                    break
            
            if not detection_results:
                raise ValueError("No detection results found from parent nodes. Recognition node must follow a detection node.")
            
            # Get workflow context
            actual_context = context.get('_context', context)
            
            logger.info(f"Recognition node {node_id}: Processing {len(detection_results)} detection results")
            
            # Initialize recognition service
            recognition_service = get_recognition_service()
            
            # Process results
            recognition_results = []
            total_recognitions = 0
            recognition_distribution = {}
            annotated_image_urls = []
            
            colors_palette = [
                (225, 96, 76),    # Accent
                (29, 47, 67),     # Navy
                (115, 122, 127),  # Grey
            ]
            
            for det_result in detection_results:
                # Filter by confidence
                top_confidence = det_result.get('top_confidence')
                if top_confidence is not None and top_confidence < validated.min_detection_confidence:
                    continue
                
                # Filter by class
                top_class = det_result.get('top_class')
                if validated.class_filter and top_class not in validated.class_filter:
                    continue
                
                # Resolve image path
                image_url = det_result.get('image_url', '')
                if image_url.startswith('/data/predictions/'):
                    image_path = str(Path(settings.DATA_DIR) / image_url.lstrip('/data/'))
                else:
                    continue
                
                if not Path(image_path).exists():
                    continue
                
                # Load image
                original_img = Image.open(image_path).convert("RGB")
                img_width, img_height = original_img.size
                img_cv2 = cv2.imread(image_path)
                
                if img_cv2 is None:
                    continue
                
                boxes = det_result.get('boxes', [])
                class_names = det_result.get('class_names', [])
                scores = det_result.get('scores', [])
                
                det_recognition_data = {
                    "detection_id": det_result.get('id'),
                    "file_name": det_result.get('file_name'),
                    "original_image_url": image_url,
                    "bboxes_recognized": []
                }
                
                # Process bboxes
                for i, (bbox, class_name, score) in enumerate(zip(boxes, class_names, scores)):
                    if score < validated.min_detection_confidence:
                        continue
                    
                    bbox_abs = normalize_bbox_coordinates(bbox, img_width, img_height)
                    
                    try:
                        cropped_img = crop_bbox_with_padding(
                            original_img,
                            bbox_abs,
                            padding_percent=validated.bbox_padding_percent
                        )
                    except Exception:
                        continue
                    
                    # Save temporarily
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                        cropped_img.save(tmp_file.name, 'JPEG')
                        crop_temp_path = tmp_file.name
                    
                    try:
                        # Generate embedding and search
                        query_embedding = recognition_service.generate_embedding(crop_temp_path)
                        matches = recognition_service.search_database_pgvector(
                            query_embedding=query_embedding,
                            catalog_id=validated.catalog_id,
                            top_k=validated.top_k,
                            threshold=validated.threshold,
                            label_filter=validated.label_filter,
                            db_session=db
                        )
                        
                        match_data = [
                            {
                                "label_id": m.label_id,
                                "label_name": m.label_name,
                                "image_id": m.image_id,
                                "similarity_score": m.similarity_score,
                                "distance_metric": m.distance_metric
                            }
                            for m in matches
                        ]
                        
                        top_match = match_data[0] if match_data else None
                        
                        # Draw annotation
                        if top_match:
                            x1, y1, x2, y2 = bbox_abs
                            color = colors_palette[i % len(colors_palette)]
                            cv2.rectangle(img_cv2, (x1, y1), (x2, y2), color, 2)
                            
                            label_text = f"{top_match['label_name']}: {top_match['similarity_score']:.2f}"
                            (label_w, label_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                            cv2.rectangle(img_cv2, (x1, y1 - label_h - 8), (x1 + label_w + 4, y1), color, -1)
                            cv2.putText(img_cv2, label_text, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
                            
                            recognition_distribution[top_match['label_name']] = recognition_distribution.get(top_match['label_name'], 0) + 1
                            total_recognitions += 1
                        
                        det_recognition_data["bboxes_recognized"].append({
                            "bbox": bbox_abs,
                            "detection_class": class_name,
                            "detection_confidence": float(score),
                            "matches": match_data,
                            "top_match": top_match
                        })
                    finally:
                        Path(crop_temp_path).unlink(missing_ok=True)
                
                # Save annotated image
                if det_recognition_data["bboxes_recognized"]:
                    output_dir = Path(settings.DATA_DIR) / "predictions" / str(detection_job_id) / "recognized"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    output_filename = f"recognized_{det_result.get('file_name')}"
                    output_path = output_dir / output_filename
                    cv2.imwrite(str(output_path), img_cv2)
                    
                    annotated_url = f"/data/predictions/{detection_job_id}/recognized/{output_filename}"
                    annotated_image_urls.append(annotated_url)
                    det_recognition_data["annotated_image_url"] = annotated_url
                    
                    recognition_results.append(det_recognition_data)
            
            # Build output
            show_images_results = []
            for rec_result in recognition_results:
                show_images_results.append({
                    "id": rec_result["detection_id"],
                    "file_name": rec_result["file_name"],
                    "image_url": rec_result.get("annotated_image_url", rec_result["original_image_url"]),
                    "task_type": "recognition",
                    "detection_count": len(rec_result["bboxes_recognized"]),
                    "recognition_data": rec_result["bboxes_recognized"]
                })
            
            output = {
                "job_type": "recognition",
                "catalog_id": validated.catalog_id,
                "catalog_name": catalog.name,
                "status": "completed",
                "annotated_image_urls": annotated_image_urls,
                "result_count": len(recognition_results),
                "results": show_images_results,
                "recognition_results": recognition_results,
                "summary": {
                    "total_detections_processed": sum(len(r["bboxes_recognized"]) for r in recognition_results),
                    "total_recognitions": total_recognitions,
                    "recognition_distribution": recognition_distribution,
                    "catalog_label_count": catalog.label_count,
                    "catalog_image_count": catalog.image_count,
                    "threshold": validated.threshold,
                    "top_k": validated.top_k
                }
            }
            
            logger.info(f"Recognition node {node_id}: Completed with {total_recognitions} recognitions")
            return output
            
        except Exception as e:
            logger.error(f"Recognition node {node_id} failed: {str(e)}", exc_info=True)
            raise
        finally:
            db.close()
