"""
Inference Service - Model-Agnostic Inference Router
Routes inference requests to appropriate service (YOLO, SAM3, etc.) based on model type.
Supports Hybrid Inference architecture for cloud-connected local agents.
"""
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.services.yolo_service import yolo_service, DetectionResult
from app.services.sam3_service import sam3_service


class InferenceService:
    """
    Unified inference service that routes to model-specific implementations.
    Automatically detects model type and delegates to appropriate service.
    """
    
    def __init__(self):
        """Initialize inference service with access to all model services."""
        self.yolo = yolo_service
        self.sam3 = sam3_service
    
    def detect_image(
        self,
        model_path: str,
        inference_type: str,
        image_path: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        class_filter: Optional[List[str]] = None,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
        prompts: Optional[List[Dict[str, Any]]] = None,
        bpe_path: Optional[str] = None
    ) -> DetectionResult:
        """
        Run inference on a single image using appropriate model service.
        
        Args:
            model_path: Path to model weights/checkpoint
            inference_type: Inference service type (yolo, sam3, etc.)
            image_path: Path to input image
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold (YOLO only)
            prompts: SAM3 prompts (text/point/box) - SAM3 only
            bpe_path: BPE vocabulary path - SAM3 only
            class_filter: Filter specific classes (YOLO only)
            iou_threshold: IOU threshold (YOLO only)
            imgsz: Image size (YOLO only)
            
        Returns:
            DetectionResult with predictions
            
        Raises:
            ValueError: If inference_type is unsupported
        """
        if inference_type == "sam3":
            # Route to SAM3 service
            if prompts is None:
                prompts = []  # Automatic segmentation
            
            return self.sam3.segment_image(
                model_path=model_path,
                image_path=image_path,
                prompts=prompts,
                bpe_path=bpe_path,
                confidence=confidence,
                class_filter=class_filter,
                iou_threshold=iou_threshold,
                imgsz=imgsz
            )
        
        elif inference_type == "yolo":
            # Route to YOLO service
            return self.yolo.detect_image(
                    model_path=model_path,
                    image_path=image_path,
                    task_type=task_type,
                    confidence=confidence,
                    class_filter=class_filter,
                    iou_threshold=iou_threshold,
                    imgsz=imgsz
                )
                
        else:
            raise ValueError(f"Unsupported inference type: {inference_type}")
    
    def detect_batch(
        self,
        model_path: str,
        inference_type: str,
        image_paths: List[str],
        task_type: str = "detect",
        confidence: float = 0.25,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
        prompts: Optional[List[Dict[str, Any]]] = None,
        bpe_path: Optional[str] = None,
        class_filter: Optional[List[str]] = None
    ) -> List[DetectionResult]:
        """
        Run inference on multiple images using appropriate model service.
        
        Args:
            model_path: Path to model weights/checkpoint
            inference_type: Inference service type (yolo, sam3, etc.)
            image_paths: List of paths to input images
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold (YOLO only)
            prompts: SAM3 prompts applied to all images - SAM3 only
            bpe_path: BPE vocabulary path - SAM3 only
            class_filter: Filter specific classes (YOLO only)
            
        Returns:
            List of DetectionResult objects
        """
        results = []
        for image_path in image_paths:
            result = self.detect_image(
                model_path=model_path,
                inference_type=inference_type,
                image_path=image_path,
                task_type=task_type,
                confidence=confidence,
                iou_threshold=iou_threshold,
                imgsz=imgsz,
                prompts=prompts,
                bpe_path=bpe_path,
                class_filter=class_filter
            )
            results.append(result)
        return results
    
    def detect_video(
        self,
        model_path: str,
        inference_type: str,
        video_path: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        class_filter: Optional[List[str]] = None,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
        prompts: Optional[List[Dict[str, Any]]] = None,
        limit_frames: Optional[int] = None,
        skip_frames: int = 5,
        bpe_path: Optional[str] = None
    ) -> List[DetectionResult]:
        """
        Run inference on video frames using appropriate model service.
        
        Args:
            model_path: Path to model weights/checkpoint
            inference_type: Inference service type (yolo, sam3, etc.)
            video_path: Path to video file
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold (YOLO only)
            skip_frames: Process every Nth frame
            prompts: SAM3 prompts applied to all frames - SAM3 only
            bpe_path: BPE vocabulary path - SAM3 only
            class_filter: Filter specific classes (YOLO only)
            limit_frames: Limit processing to first N frames
            
        Returns:
            List of DetectionResult objects (one per processed frame)
        """
        if inference_type == "sam3":
            return self.sam3.segment_video(
                model_path=model_path,
                video_path=video_path,
                
                prompts=prompts or [],
                skip_frames=skip_frames,
                bpe_path=bpe_path
            )
        
        elif inference_type == "yolo":
            return self.yolo.detect_video(
                model_path=model_path,
                video_path=video_path,
                task_type=task_type,
                confidence=confidence,
                skip_frames=skip_frames,
                class_filter=class_filter
            )
        
        else:
            raise ValueError(f"Unsupported inference type: {inference_type}")
    
    def get_supported_inference_types(self) -> List[str]:
        """
        Get list of supported inference types.
        
        Returns:
            List of inference type strings
        """
        return ["yolo", "sam3"]
    
    def validate_model_config(
        self,
        inference_type: str,
        task_type: str,
        prompts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Validate model configuration before inference.
        
        Args:
            inference_type: Inference service type
            task_type: Task type
            prompts: SAM3 prompts (if applicable)
            
        Returns:
            Dictionary with validation results and recommendations
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Validate inference type
        if inference_type not in self.get_supported_inference_types():
            validation["valid"] = False
            validation["errors"].append(
                f"Unsupported inference type: {inference_type}. "
                f"Supported types: {', '.join(self.get_supported_inference_types())}"
            )
        
        # SAM3-specific validation
        if inference_type == "sam3":
            if task_type not in ["segment"]:
                validation["valid"] = False
                validation["errors"].append(
                    f"SAM3 only supports 'segment' task, got: {task_type}"
                )
            
            if prompts:
                for i, prompt in enumerate(prompts):
                    if "type" not in prompt:
                        validation["errors"].append(
                            f"Prompt {i} missing 'type' field"
                        )
                    elif prompt["type"] not in ["text", "point", "box"]:
                        validation["errors"].append(
                            f"Prompt {i} has invalid type: {prompt['type']}"
                        )
        
        # YOLO-specific validation
        elif inference_type == "yolo":
            if task_type not in ["detect", "classify", "segment"]:
                validation["valid"] = False
                validation["errors"].append(
                    f"YOLO supports 'detect', 'classify', 'segment' tasks, got: {task_type}"
                )
            
            if prompts is not None:
                validation["warnings"].append(
                    "Prompts parameter ignored for YOLO models"
                )
        
        return validation


# Singleton instance
inference_service = InferenceService()
