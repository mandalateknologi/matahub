"""
YOLO Service - Training and Detection Wrapper
"""
import os
import time
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import cv2
import numpy as np

from app.config import settings


@dataclass
class DetectionResult:
    """Detection result for a single image/frame."""
    task_type: str  # detect, classify, segment
    inference_time_ms: float
    inference_type: Optional[str] = None  # yolo, sam3, etc.
    
    # Object Detection fields
    boxes: Optional[List[List[float]]] = None  # [[x1, y1, x2, y2], ...]
    scores: Optional[List[float]] = None
    classes: Optional[List[int]] = None
    class_names: Optional[List[str]] = None
    
    # Classification fields
    top_class: Optional[str] = None  # Most confident class
    top_confidence: Optional[float] = None  # Confidence of top class
    top_classes: Optional[List[str]] = None  # Top-N classes
    probabilities: Optional[List[float]] = None  # Probabilities for top-N classes
    
    # Segmentation fields (for future)
    masks: Optional[List[Any]] = None  # Segmentation masks


class YOLOService:
    """Service for YOLO model training and inference."""
    
    def __init__(self):
        """Initialize YOLO service."""
        self._model_cache: Dict[str, Any] = {}
        self._log_device_info()
    
    def _log_device_info(self):
        """Log GPU/CPU device information at startup."""
        try:
            import torch
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0)
                print(f"🚀 YOLO Service initialized with GPU acceleration")
                print(f"   Device: {device_name}")
                print(f"   CUDA Version: {torch.version.cuda}")
                print(f"   Available GPUs: {device_count}")
            else:
                print("⚠️  YOLO Service initialized with CPU (GPU not available)")
                print("   For faster training, install CUDA-enabled PyTorch")
        except Exception as e:
            print(f"⚠️  Could not detect device info: {e}")
    
    def get_base_models(self) -> List[Dict[str, str]]:
        """
        Get list of available base YOLO models.
        
        Returns:
            List of model info dictionaries
        """
        models = [
            {
                "name": "yolov8n",
                "description": "YOLOv8 Nano - Fastest, smallest model",
                "parameters": "3.2M",
                "speed": "Fastest",
                "accuracy": "Lower"
            },
            {
                "name": "yolov8s",
                "description": "YOLOv8 Small - Good balance of speed and accuracy",
                "parameters": "11.2M",
                "speed": "Fast",
                "accuracy": "Good"
            },
            {
                "name": "yolov8m",
                "description": "YOLOv8 Medium - Balanced performance",
                "parameters": "25.9M",
                "speed": "Medium",
                "accuracy": "Better"
            },
            {
                "name": "yolov8l",
                "description": "YOLOv8 Large - Higher accuracy",
                "parameters": "43.7M",
                "speed": "Slower",
                "accuracy": "High"
            },
            {
                "name": "yolov8x",
                "description": "YOLOv8 Extra Large - Best accuracy",
                "parameters": "68.2M",
                "speed": "Slowest",
                "accuracy": "Highest"
            }
        ]
        return models
    
    def load_model(self, model_path: str) -> Any:
        """
        Load a YOLO model from file.
        
        Args:
            model_path: Path to the model weights file (.pt)
            
        Returns:
            Loaded YOLO model
        """
        if model_path in self._model_cache:
            return self._model_cache[model_path]
        
        try:
            from ultralytics import YOLO
            model = YOLO(model_path)
            self._model_cache[model_path] = model
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {str(e)}")
    
    def load_base_model(self, base_type: str) -> Any:
        """
        Load a base YOLO model.
        
        Args:
            base_type: Base model type (yolov8n, yolov8s, etc.)
            
        Returns:
            Loaded YOLO model
        """
        if base_type not in settings.YOLO_BASE_MODELS:
            raise ValueError(f"Invalid base model: {base_type}")
        
        try:
            from ultralytics import YOLO
            model = YOLO(f"{base_type}.pt")
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load base model: {str(e)}")
    
    def train(
        self,
        dataset_path: str,
        output_dir: str,
        task_type: str = "detect",
        base_model: str = "yolov8n.pt",
        epochs: int = 100,
        batch_size: int = 16,
        image_size: int = 640,
        learning_rate: float = 0.01,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Train a YOLO model on a dataset.
        
        Args:
            dataset_path: Path to the dataset directory (with data.yaml)
            output_dir: Path to save training outputs
            task_type: Task type (detect, classify, segment)
            base_model: Full path to the base YOLO model file (.pt)
            epochs: Number of training epochs
            batch_size: Training batch size
            image_size: Input image size
            learning_rate: Initial learning rate
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with training results and metrics
        """
        from ultralytics import YOLO
        import torch
        
        # Get device from config (auto-detect if set to "auto")
        device = settings.get_device()
        if device == "0" and torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"🚀 Training on GPU: {device_name}")
        else:
            device = "cpu"
            print(f"💻 Training on CPU")
        
        # Load base model from full path
        model = YOLO(base_model)
        
        # Determine data path based on task type
        # Classification: YOLO expects directory path
        # Detection/Segmentation: YOLO expects data.yaml path
        if task_type == "classify":
            data_path = Path(dataset_path)
            if not data_path.exists():
                raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")
        else:
            # For detection/segmentation, use data.yaml
            data_yaml = Path(dataset_path) / "data.yaml"
            if not data_yaml.exists():
                # Try to auto-generate data.yaml for datasets
                dataset_path_obj = Path(dataset_path)
                if (dataset_path_obj / "train").exists() and (dataset_path_obj / "train").is_dir():
                    # Check if it's a classification structure (has class folders)
                    train_subdirs = [d for d in (dataset_path_obj / "train").iterdir() if d.is_dir()]
                    if train_subdirs:
                        # Classification structure detected, auto-generate data.yaml
                        print("📁 Classification dataset detected, generating data.yaml...")
                        self._generate_classification_yaml(dataset_path_obj, train_subdirs)
                        if not data_yaml.exists():
                            raise FileNotFoundError(f"Failed to generate data.yaml in {dataset_path}")
                    else:
                        raise FileNotFoundError(f"data.yaml not found in {dataset_path}")
                else:
                    raise FileNotFoundError(f"data.yaml not found in {dataset_path}")
            data_path = data_yaml
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Train model with GPU if available
        results = model.train(
            data=str(data_path),
            epochs=epochs,
            batch=batch_size,
            imgsz=image_size,
            lr0=learning_rate,
            device=device,  # Use GPU (0) if available, otherwise CPU
            project=output_dir,
            name="train",
            exist_ok=True,
            verbose=True,
        )
        
        # Get best model path
        best_model_path = Path(output_dir) / "train" / "weights" / "best.pt"
        
        # Extract metrics based on task type
        metrics = {}
        if hasattr(results, 'results_dict'):
            metrics = results.results_dict
        elif task_type == "classify":
            # Classification metrics: top1 and top5 accuracy
            # Try multiple attribute paths for compatibility
            if hasattr(results, 'top1') and hasattr(results, 'top5'):
                metrics = {
                    "metrics/accuracy_top1": float(results.top1) if results.top1 is not None else 0,
                    "metrics/accuracy_top5": float(results.top5) if results.top5 is not None else 0,
                }
            elif hasattr(results, 'metrics'):
                # Check for metrics attribute with top1/top5
                metrics_obj = results.metrics
                metrics = {
                    "metrics/accuracy_top1": float(getattr(metrics_obj, 'top1', 0)),
                    "metrics/accuracy_top5": float(getattr(metrics_obj, 'top5', 0)),
                }
        elif hasattr(results, 'box'):
            # Detection/Segmentation metrics
            metrics = {
                "mAP50": float(results.box.map50) if hasattr(results.box, 'map50') else 0,
                "mAP50-95": float(results.box.map) if hasattr(results.box, 'map') else 0,
                "precision": float(results.box.p[0]) if hasattr(results.box, 'p') else 0,
                "recall": float(results.box.r[0]) if hasattr(results.box, 'r') else 0,
            }
        
        # Prepare return value before cleanup
        result_data = {
            "model_path": str(best_model_path),
            "metrics": metrics,
            "epochs_completed": epochs,
        }
        
        # CRITICAL: Explicit memory cleanup to release RAM immediately
        try:
            # Delete YOLO model and results to release PyTorch tensors
            del model
            del results
            
            # Clear CUDA cache if GPU was used
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Wait for GPU operations to complete
            
            # Force Python garbage collection to release memory immediately
            gc.collect()
            print("✅ Training memory cleanup completed")
            
        except Exception as cleanup_error:
            print(f"⚠️  Memory cleanup warning (non-fatal): {cleanup_error}")
        
        return result_data
    
    def detect_image(
        self,
        model_path: str,
        image_path: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        top_k: int = 5,
        iou_threshold: Optional[float] = 0.45,
        imgsz: Optional[int] = 640,
        class_filter: Optional[List[str]] = None
    ) -> DetectionResult:
        """
        Run inference on a single image (detection, classification, or segmentation).
        
        Args:
            model_path: Path to the model weights
            image_path: Path to the image file
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            top_k: Number of top classes to return (for classification)
            class_filter: Optional list of class names to filter (only return these classes)
            
        Returns:
            DetectionResult with task-specific results
        """
        model = self.load_model(model_path)

        class_ids = None
        if len(class_filter or []) > 0:
            # Map class names to IDs
            reverse_map = {v: k for k, v in model.names.items()}
            class_ids = [reverse_map[cls] for cls in class_filter if cls in reverse_map] if class_filter else []
        device = settings.get_device()
        
        start_time = time.time()
        results = model.predict(
            source=image_path,
            conf=confidence,
            device=device,
            classes=class_ids if class_ids else None,
            verbose=False
        )
        inference_time = (time.time() - start_time) * 1000
        
        if not results or len(results) == 0:
            # Return empty result based on task type
            return DetectionResult(
                task_type=task_type,
                inference_type="yolo",
                inference_time_ms=inference_time,
                boxes=[] if task_type == "detect" else None,
                scores=[] if task_type == "detect" else None,
                classes=[] if task_type == "detect" else None,
                class_names=[] if task_type == "detect" else None,
                top_class=None if task_type == "classify" else None,
                top_confidence=None if task_type == "classify" else None,
                top_classes=[] if task_type == "classify" else None,
                probabilities=[] if task_type == "classify" else None
            )
        
        result = results[0]
        
        # Handle different task types
        if task_type == "classify":
            # Classification: extract probabilities
            if hasattr(result, 'probs') and result.probs is not None:
                probs_data = result.probs.data.cpu().numpy()
                top_indices = probs_data.argsort()[-top_k:][::-1]
                
                top_classes = [result.names[int(i)] for i in top_indices]
                probabilities = [float(probs_data[i]) for i in top_indices]
                
                return DetectionResult(
                    task_type=task_type,
                    inference_time_ms=inference_time,
                    inference_type="yolo",
                    top_class=top_classes[0] if top_classes else None,
                    top_confidence=probabilities[0] if probabilities else None,
                    top_classes=top_classes,
                    probabilities=probabilities
                )
            else:
                # No classification results
                return DetectionResult(
                    task_type=task_type,
                    inference_type="yolo",
                    inference_time_ms=inference_time,
                    top_class=None,
                    top_confidence=None,
                    top_classes=[],
                    probabilities=[]
                )
        
        elif task_type == "segment":
            # Segmentation: extract boxes + masks
            boxes = []
            scores = []
            classes = []
            class_names = []
            masks = []
            
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy().tolist()
                scores = result.boxes.conf.cpu().numpy().tolist()
                classes = result.boxes.cls.cpu().numpy().astype(int).tolist()
                class_names = [result.names[c] for c in classes]
            
            # Extract segmentation masks
            if hasattr(result, 'masks') and result.masks is not None:
                try:
                    # Get original image dimensions
                    orig_shape = result.orig_shape  # (height, width)
                    img_height, img_width = int(orig_shape[0]), int(orig_shape[1])
                    
                    # Get polygon coordinates in pixel space: list of (K,2) arrays
                    polys = result.masks.xy
                    
                    # Create mask list with instance-based format
                    for i, polygon_coords in enumerate(polys):
                        if i >= len(classes) or i >= len(boxes):
                            break
                        
                        # Skip if polygon is empty
                        if len(polygon_coords) == 0:
                            continue
                        
                        # Convert polygon to binary mask
                        # Create empty mask with original image dimensions
                        binary_mask = np.zeros((img_height, img_width), dtype=np.uint8)
                        
                        # Convert polygon coordinates to integer pixel coordinates
                        polygon_int = polygon_coords.astype(np.int32)
                        
                        # Fill polygon using OpenCV
                        import cv2
                        cv2.fillPoly(binary_mask, [polygon_int], 1)
                        
                        # Instead of sending full mask, send polygon coordinates (much smaller!)
                        mask_dict = {
                            "instance_id": i,
                            "class_id": int(classes[i]),
                            "class_name": class_names[i],
                            "bbox": boxes[i],
                            "score": float(scores[i]),
                            # Send polygon coordinates instead of full mask (200x smaller!)
                            "polygon": polygon_int.tolist(),  # [[x1,y1], [x2,y2], ...]
                            "height": img_height,
                            "width": img_width
                        }
                        masks.append(mask_dict)
                except Exception as e:
                    print(f"Warning: Failed to extract segmentation masks: {e}")
                    import traceback
                    traceback.print_exc()
                    masks = []

            return DetectionResult(
                task_type=task_type,
                inference_type="yolo",
                inference_time_ms=inference_time,
                boxes=boxes,
                scores=scores,
                classes=classes,
                class_names=class_names,
                masks=masks
            )
        
        else:  # detect (default)
            # Object Detection: extract boxes
            boxes = []
            scores = []
            classes = []
            class_names = []
            
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy().tolist()
                scores = result.boxes.conf.cpu().numpy().tolist()
                classes = result.boxes.cls.cpu().numpy().astype(int).tolist()
                class_names = [result.names[c] for c in classes]
                
                # Apply class filter if provided
                if class_filter:
                    # Normalize class filter (lowercase for comparison)
                    normalized_filter = [cf.lower() for cf in class_filter]
                    
                    # Filter detections
                    filtered_boxes = []
                    filtered_scores = []
                    filtered_classes = []
                    filtered_class_names = []
                    
                    for i, class_name in enumerate(class_names):
                        if class_name.lower() in normalized_filter:
                            filtered_boxes.append(boxes[i])
                            filtered_scores.append(scores[i])
                            filtered_classes.append(classes[i])
                            filtered_class_names.append(class_name)
                    
                    boxes = filtered_boxes
                    scores = filtered_scores
                    classes = filtered_classes
                    class_names = filtered_class_names
            
            return DetectionResult(
                task_type=task_type,
                inference_type="yolo",
                inference_time_ms=inference_time,
                boxes=boxes,
                scores=scores,
                classes=classes,
                class_names=class_names
            )
    
    def detect_batch(
        self,
        model_path: str,
        image_paths: List[str],
        task_type: str = "detect",
        confidence: float = 0.25,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
        top_k: int = 5,
        class_filter: Optional[List[str]] = None
    ) -> List[Tuple[str, DetectionResult]]:
        """
        Run inference on multiple images.
        
        Args:
            model_path: Path to the model weights
            image_paths: List of image file paths
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            top_k: Number of top classes to return (for classification)
            class_filter: Optional list of class names to filter (only return these classes)
            
        Returns:
            List of (filename, DetectionResult) tuples
        """
        model = self.load_model(model_path)
        results_list = []
        
        for image_path in image_paths:
            try:
                result = self.detect_image(model_path, image_path, task_type, confidence, top_k, class_filter)
                results_list.append((Path(image_path).name, result))
            except Exception as e:
                # Return empty result for failed images based on task type
                results_list.append((Path(image_path).name, DetectionResult(
                    task_type=task_type,
                    inference_time_ms=0,
                    boxes=[] if task_type == "detect" else None,
                    scores=[] if task_type == "detect" else None,
                    classes=[] if task_type == "detect" else None,
                    class_names=[] if task_type == "detect" else None,
                    top_class=None if task_type == "classify" else None,
                    top_confidence=None if task_type == "classify" else None,
                    top_classes=[] if task_type == "classify" else None,
                    probabilities=[] if task_type == "classify" else None,
                    inference_type="yolo"
                )))
        
        return results_list
    
    def detect_video(
        self,
        model_path: str,
        video_path: str,
        task_type: str,
        confidence: float = 0.25,
        frame_callback: Optional[callable] = None,
        skip_frames: int = 1,
        return_frame: bool = False,
        iou_threshold: Optional[float] = 0.45,
        imgsz: Optional[int] = 640,
        class_filter: Optional[List[str]] = None
    ):
        """
        Run detection/segmentation on a video file (generator version).
        
        Args:
            model_path: Path to the model weights
            video_path: Path to the video file or RTSP URL
            task_type: Task type (detect, segment)
            confidence: Confidence threshold
            frame_callback: Optional callback for each frame result
            skip_frames: Process every Nth frame
            return_frame: If True, returns (frame_number, DetectionResult, frame), otherwise (frame_number, DetectionResult)
            class_filter: Optional list of class names to filter detections
            
        Yields:
            Tuple of (frame_number, DetectionResult) or (frame_number, DetectionResult, frame)
        """
        if task_type:
            if task_type not in ["detect", "segment"]:
                raise ValueError(f"Invalid task_type for video detection: {task_type}")
        else:
            raise ValueError(f"You must specify task_type for video detection")

        model = self.load_model(model_path)
        device = settings.get_device()
        
        print(f"Opening video/stream: {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"Failed to open video/stream: {video_path}")
            raise RuntimeError(f"Failed to open video: {video_path}")
        
        print(f"Video/stream opened successfully")
        frame_number = 0
        processed_frames = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print(f"No more frames (ret={ret}, frame_number={frame_number})")
                    break
                
                # Skip frames
                if frame_number % skip_frames != 0:
                    frame_number += 1
                    continue
                
                # Run detection
                start_time = time.time()
                results = model.predict(
                    source=frame,
                    conf=confidence,
                    device=device,
                    verbose=False
                )
                inference_time = (time.time() - start_time) * 1000
                
                # Extract results
                boxes = []
                scores = []
                classes = []
                class_names = []
                masks = []
                
                if results and len(results) > 0:
                    result = results[0]
                    if result.boxes is not None:
                        boxes = result.boxes.xyxy.cpu().numpy().tolist()
                        scores = result.boxes.conf.cpu().numpy().tolist()
                        classes = result.boxes.cls.cpu().numpy().astype(int).tolist()
                        class_names = [result.names[c] for c in classes]
                    
                    # Extract segmentation masks if task_type is segment
                    if task_type == "segment" and hasattr(result, 'masks') and result.masks is not None:
                        try:
                            # Get frame dimensions
                            img_height, img_width = frame.shape[:2]
                            
                            # Get polygon coordinates
                            polys = result.masks.xy
                            
                            # Create mask list with instance-based format
                            for i, polygon_coords in enumerate(polys):
                                if i >= len(classes) or i >= len(boxes):
                                    break
                                
                                if len(polygon_coords) == 0:
                                    continue
                                
                                # Convert polygon to integer coordinates
                                polygon_int = polygon_coords.astype(np.int32)
                                
                                mask_dict = {
                                    "instance_id": i,
                                    "class_id": int(classes[i]),
                                    "class_name": class_names[i],
                                    "bbox": boxes[i],
                                    "score": float(scores[i]),
                                    "polygon": polygon_int.tolist(),
                                    "height": img_height,
                                    "width": img_width
                                }
                                masks.append(mask_dict)
                        except Exception as e:
                            print(f"Warning: Failed to extract segmentation masks from video frame: {e}")
                            masks = []
                
                # Apply class filter if provided
                if class_filter and class_names:
                    # Normalize filter list to lowercase
                    filter_lower = [f.lower() for f in class_filter]
                    
                    # Filter detections (including masks)
                    filtered_boxes = []
                    filtered_scores = []
                    filtered_classes = []
                    filtered_class_names = []
                    filtered_masks = []
                    
                    for i, class_name in enumerate(class_names):
                        if class_name.lower() in filter_lower:
                            filtered_boxes.append(boxes[i])
                            filtered_scores.append(scores[i])
                            filtered_classes.append(classes[i])
                            filtered_class_names.append(class_name)
                            # Find corresponding mask if exists
                            if masks:
                                for mask in masks:
                                    if mask.get("instance_id") == i:
                                        filtered_masks.append(mask)
                                        break
                    
                    boxes = filtered_boxes
                    scores = filtered_scores
                    classes = filtered_classes
                    class_names = filtered_class_names
                    masks = filtered_masks
                
                detection_result = None
                if len(boxes) > 0:
                    detection_result = DetectionResult(
                        task_type=task_type,
                        inference_type="yolo",
                        inference_time_ms=inference_time,
                        boxes=boxes,
                        scores=scores,
                        classes=classes,
                        class_names=class_names,
                        masks=masks if task_type == "segment" else None
                    )

                if frame_callback:
                    frame_callback(frame_number, detection_result)
                
                processed_frames += 1
                if processed_frames % 10 == 0:
                    print(f"Processed {processed_frames} frames, {len(boxes)} detections in frame {frame_number}")
                
                if return_frame:
                    yield frame_number, detection_result, frame
                else:
                    yield frame_number, detection_result
                
                frame_number += 1
                
        finally:
            cap.release()
            print(f"Video/stream closed. Total frames processed: {processed_frames}")
    
    def detect_rtsp(
        self,
        model_path: str,
        rtsp_url: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        frame_callback: callable = None,
        max_frames: int = 100,
        iou_threshold: Optional[float] = 0.45,
        imgsz: Optional[int] = 640,
        class_filter: Optional[List[str]] = None
    ) -> List[Tuple[int, DetectionResult]]:
        """
        Run detection/segmentation on an RTSP stream.
        
        Args:
            model_path: Path to the model weights
            rtsp_url: RTSP stream URL
            task_type: Task type (detect, segment)
            confidence: Confidence threshold
            frame_callback: Callback for each frame result
            max_frames: Maximum frames to process
            
        Returns:
            List of (frame_number, DetectionResult) tuples
        """
        return self.detect_video(
            model_path=model_path,
            video_path=rtsp_url,
            task_type=task_type,
            confidence=confidence,
            frame_callback=frame_callback,
            skip_frames=5  # Skip more frames for RTSP to reduce latency
        )
    
    def _generate_classification_yaml(self, dataset_path: Path, train_subdirs: List[Path]) -> None:
        """
        Generate data.yaml for classification datasets.
        
        Args:
            dataset_path: Path to the dataset directory
            train_subdirs: List of class subdirectories in train folder
        """
        # Extract class names from folder names
        class_names = sorted([d.name for d in train_subdirs])
        
        yaml_content = f"""# ATVISION Classification Dataset
path: {dataset_path}
train: train
val: val
test: test

# Classes
nc: {len(class_names)}
names: {class_names}
"""
        
        yaml_path = dataset_path / "data.yaml"
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        print(f"✅ Generated data.yaml with {len(class_names)} classes: {class_names[:5]}{'...' if len(class_names) > 5 else ''}")
    
    def extract_metrics_from_model(
        self,
        model_path: str,
        dataset_path: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Extract metrics from an uploaded model by validating it on a dataset.
        
        This method loads a pre-trained .pt file and runs validation against
        the provided dataset to extract performance metrics (mAP, precision, recall).
        
        Args:
            model_path: Path to the .pt model file
            dataset_path: Path to the dataset directory containing data.yaml
            progress_callback: Optional callback(progress: float) for progress updates
            
        Returns:
            Dictionary containing:
                - metrics: Dict with mAP50, mAP50-95, precision, recall
                - class_count: Number of classes detected
                - class_names: List of class names
                
        Raises:
            Exception: If model loading or validation fails
        """
        try:
            from ultralytics import YOLO
            
            # Load the uploaded model
            if progress_callback:
                progress_callback(0.1)
            
            model = YOLO(model_path)
            
            if progress_callback:
                progress_callback(0.2)
            
            # Find data.yaml in dataset path
            data_yaml = Path(dataset_path) / "data.yaml"
            if not data_yaml.exists():
                raise FileNotFoundError(f"data.yaml not found in {dataset_path}")
            
            if progress_callback:
                progress_callback(0.3)
            
            # Run validation on the dataset
            device = settings.get_device()
            results = model.val(
                data=str(data_yaml),
                device=device,
                verbose=False
            )
            
            if progress_callback:
                progress_callback(0.9)
            
            # Extract metrics (same format as training)
            metrics = {}
            if hasattr(results, 'results_dict'):
                metrics = results.results_dict
            elif hasattr(results, 'box'):
                metrics = {
                    "mAP50": float(results.box.map50) if hasattr(results.box, 'map50') else 0,
                    "mAP50-95": float(results.box.map) if hasattr(results.box, 'map') else 0,
                    "precision": float(results.box.p[0]) if hasattr(results.box, 'p') and len(results.box.p) > 0 else 0,
                    "recall": float(results.box.r[0]) if hasattr(results.box, 'r') and len(results.box.r) > 0 else 0,
                }
            
            # Extract class information
            class_names = list(model.names.values()) if hasattr(model, 'names') else []
            class_count = len(class_names)
            
            if progress_callback:
                progress_callback(1.0)
            
            return {
                "metrics": metrics,
                "class_count": class_count,
                "class_names": class_names
            }
            
        except Exception as e:
            raise Exception(f"Failed to extract metrics from model: {str(e)}")
    
    # New method names (prediction-focused naming)
    def predict_image(self, *args, **kwargs):
        """Alias for detect_image with prediction-focused naming."""
        return self.detect_image(*args, **kwargs)
    
    def predict_batch(self, *args, **kwargs):
        """Alias for detect_batch with prediction-focused naming."""
        return self.detect_batch(*args, **kwargs)
    
    def predict_video(self, *args, **kwargs):
        """Alias for detect_video with prediction-focused naming."""
        return self.detect_video(*args, **kwargs)
    
    def predict_rtsp(self, *args, **kwargs):
        """Alias for detect_rtsp with prediction-focused naming."""
        return self.detect_rtsp(*args, **kwargs)
    
    def clear_inference_cache(self) -> int:
        """
        Clear the model cache to free memory.
        
        This should be called periodically to prevent indefinite memory accumulation
        from inference operations.
        
        Returns:
            Number of models cleared from cache
        """
        cache_size = len(self._model_cache)
        
        if cache_size > 0:
            # Delete all cached models
            self._model_cache.clear()
            
            # Clear CUDA cache if GPU is available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            
            # Force garbage collection
            gc.collect()
            
            print(f"✅ Cleared {cache_size} model(s) from inference cache")
        
        return cache_size


# Global service instance
yolo_service = YOLOService()
