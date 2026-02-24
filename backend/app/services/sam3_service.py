"""
SAM3 Service - Facebook Segment Anything Model 3 (VisionMask)
Fully offline segmentation with text/point/box prompts
"""
import os
import time
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from app.config import settings
from app.services.yolo_service import DetectionResult


class SAM3Service:
    """Service for SAM3 segmentation inference."""
    
    def __init__(self):
        """Initialize SAM3 service."""
        self._model_cache: Dict[str, Any] = {}
        self._processor_cache: Dict[str, Any] = {}
        self._log_device_info()
    
    def _log_device_info(self):
        """Log GPU/CPU device information at startup."""
        try:
            import torch
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0)
                print(f"🎭 SAM3 VisionMask Service initialized with GPU acceleration")
                print(f"   Device: {device_name}")
                print(f"   CUDA Version: {torch.version.cuda}")
                print(f"   Available GPUs: {device_count}")
            else:
                print("⚠️  SAM3 VisionMask Service initialized with CPU (GPU not available)")
                print("   For faster inference, install CUDA-enabled PyTorch")
        except Exception as e:
            print(f"⚠️  Could not detect device info: {e}")
    
    def load_model(self, model_path: str, bpe_path: str) -> Tuple[Any, Any]:
        """
        Load SAM3 model and processor from checkpoint.
        
        Args:
            model_path: Path to SAM3 safetensors checkpoint
            bpe_path: Path to BPE vocabulary file
            
        Returns:
            Tuple of (model, processor)
        """
        cache_key = f"{model_path}:{bpe_path}"
        
        if cache_key in self._model_cache:
            return self._model_cache[cache_key], self._processor_cache[cache_key]
        
        try:
            from sam3 import build_sam3_image_model
            from sam3.model.sam3_image_processor import Sam3Processor
            import torch
            
            # Determine device
            if settings.YOLO_DEVICE == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = settings.YOLO_DEVICE
            
            print(f"📦 Loading SAM3 model from {model_path}")
            print(f"   Device: {device}")
            
            # Load SAM3 model
            model = build_sam3_image_model(
                bpe_path=bpe_path,
                device=device,
                eval_mode=True,
                checkpoint_path=model_path,
                load_from_HF=False
            )
            
            # Create processor
            processor = Sam3Processor(model, device=device)
            
            # Cache model and processor
            self._model_cache[cache_key] = model
            self._processor_cache[cache_key] = processor
            
            print(f"✅ SAM3 model loaded successfully")
            
            return model, processor
            
        except Exception as e:
            print(f"❌ Error loading SAM3 model: {e}")
            raise RuntimeError(f"Failed to load SAM3 model: {str(e)}")
    
    def segment_image(
        self,
        model_path: str,
        image_path: str,
        bpe_path: Optional[str] = None,
        confidence: Optional[float] = None,
        class_filter: Optional[List[str]] = None,
        iou_threshold: Optional[float] = None,
        imgsz: Optional[int] = None,
        prompts: List[Dict[str, Any]] = [], #if non is provided, automatic segmentation
        **kwargs
    ) -> DetectionResult:
        """
        Segment image using SAM3 with prompts.
        
        Supports batch text prompts for multi-object segmentation:
        - Single text: [{"type": "text", "value": "car"}] → finds ONE car
        - Multiple texts: [{"type": "text", "value": "car"}, {"type": "text", "value": "car"}] → finds multiple cars
        - Batch mode: [{"type": "text", "value": "car", "batch": True}] → experimental multi-instance mode
        
        Args:
            model_path: Path to SAM3 checkpoint
            image_path: Path to input image
            prompts: List of prompt dicts:
                    - {"type": "text", "value": "car"}  # Single instance
                    - {"type": "text", "value": "car", "batch": True}  # Multi-instance (experimental)
                    - {"type": "point", "coords": [x, y], "label": 1}
                    - {"type": "box", "coords": [x1, y1, x2, y2]}
            bpe_path: Path to BPE vocab (defaults to searching in model's asset folder or standard location)
            
        Returns:
            DetectionResult with masks in polygon format
        """
        start_time = time.time()
        
        # Set default BPE path if not provided
        if bpe_path is None:
            # First, try to find BPE in the model's asset folder
            model_dir = Path(model_path).parent
            asset_dir = model_dir / "asset"
            
            if asset_dir.exists():
                # Look for any .txt.gz file in asset folder
                bpe_files = list(asset_dir.glob("*.txt.gz"))
                if bpe_files:
                    bpe_path = str(bpe_files[0])
                    print(f"📦 Found BPE vocab in model asset folder: {bpe_path}")
            
            # Fallback to standard location
            if bpe_path is None:
                sam3_dir = Path(settings.DATA_DIR) / "models" / "sam3"
                bpe_path = str(sam3_dir / "assets" / "bpe_simple_vocab_16e6.txt.gz")
        
        # Load model and processor
        model, processor = self.load_model(model_path, bpe_path)
        
        try:
            # Load and validate image
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image not found: {image_path}")
            
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Failed to load image: {image_path}")
            
            height, width = image.shape[:2]
            
            # Convert OpenCV BGR to RGB PIL Image
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            
            # Separate prompts by type for batch processing
            text_prompts = [p for p in prompts if p.get("type") == "text"]
            point_prompts = [p for p in prompts if p.get("type") == "point"]
            box_prompts = [p for p in prompts if p.get("type") == "box"]
            
            all_masks = []
            all_mask_metadata = []  # Track prompt info for each mask
            
            # Check if no prompts provided → automatic segmentation mode
            if not text_prompts and not point_prompts and not box_prompts:
                print("🤖 No prompts provided → Running automatic segmentation")
                return self._automatic_segmentation(
                    processor, pil_image, width, height, start_time
                )
            
            # Process text prompts - each text prompt generates separate masks
            if text_prompts:
                print(f"🔍 Processing {len(text_prompts)} text prompt(s)")
                for idx, text_prompt in enumerate(text_prompts):
                    text_value = text_prompt.get("value", "")
                    is_batch = text_prompt.get("batch", False)
                    
                    # Set image for this prompt
                    state = processor.set_image(pil_image)
                    state = processor.set_text_prompt(text_value, state)
                    
                    # Get masks for this text prompt
                    masks_tensor = state.get("masks")
                    if masks_tensor is not None and len(masks_tensor) > 0:
                        all_masks.append(masks_tensor)
                        # Store metadata: class_id and class_name for each mask from this prompt
                        all_mask_metadata.append({
                            "class_id": idx,  # Unique class_id per text prompt
                            "class_name": text_value,  # Use prompt text as class name
                            "count": len(masks_tensor)
                        })
                        print(f"   ✓ Text prompt {idx+1} '{text_value}': {len(masks_tensor)} mask(s)")
            
            # Process point prompts - each point generates separate mask
            if point_prompts:
                print(f"📍 Processing {len(point_prompts)} point prompt(s)")
                base_class_id = len(text_prompts)  # Continue class_id sequence
                for idx, point_prompt in enumerate(point_prompts):
                    coords = point_prompt.get("coords", [])
                    label = point_prompt.get("label", 1)
                    
                    if len(coords) == 2:
                        import torch
                        state = processor.set_image(pil_image)
                        
                        # SAM3 doesn't have set_point_prompt, need to manually add to geometric_prompt
                        if "geometric_prompt" not in state:
                            state["geometric_prompt"] = processor.model._get_dummy_prompt()
                        
                        # Add dummy text prompt "visual" if no text features exist
                        if "language_features" not in state["backbone_out"]:
                            dummy_text_outputs = processor.model.backbone.forward_text(
                                ["visual"], device=processor.device
                            )
                            state["backbone_out"].update(dummy_text_outputs)
                        
                        # Points in pixel coordinates as [N_points, batch, 2] -> [1, 1, 2] tensor
                        point_coords = torch.tensor(
                            [[coords[0], coords[1]]], 
                            device=processor.device, 
                            dtype=torch.float32
                        ).unsqueeze(1)  # [1, 1, 2]
                        
                        # Labels as [N_points, batch] -> [1, 1] tensor
                        point_labels = torch.tensor(
                            [[label]], 
                            device=processor.device, 
                            dtype=torch.long
                        )  # [1, 1]
                        
                        # Encode points to embeddings using geometry encoder
                        # Points need to be embedded first - SAM3 uses a geometry encoder
                        # For now, use add_geometric_prompt approach with points converted to box
                        # Alternative: Convert point to small box around it
                        point_size = 10  # Small box around point
                        x, y = coords[0], coords[1]
                        # Convert to normalized [center_x, center_y, width, height]
                        center_x = x / width
                        center_y = y / height
                        box_width = point_size / width
                        box_height = point_size / height
                        
                        box = [center_x, center_y, box_width, box_height]
                        box_label = True if label == 1 else False
                        
                        state = processor.add_geometric_prompt(box, box_label, state)
                        
                        masks_tensor = state.get("masks")
                        if masks_tensor is not None and len(masks_tensor) > 0:
                            all_masks.append(masks_tensor)
                            all_mask_metadata.append({
                                "class_id": base_class_id + idx,
                                "class_name": f"point_{idx+1}",
                                "count": len(masks_tensor)
                            })
                            print(f"   ✓ Point prompt {idx+1} at {coords}: {len(masks_tensor)} mask(s)")
            
            # Process box prompts - each box generates separate mask
            if box_prompts:
                print(f"📦 Processing {len(box_prompts)} box prompt(s)")
                base_class_id = len(text_prompts) + len(point_prompts)
                for idx, box_prompt in enumerate(box_prompts):
                    coords = box_prompt.get("coords", [])
                    
                    if len(coords) == 4:
                        state = processor.set_image(pil_image)
                        
                        # Convert XYXY [x1, y1, x2, y2] to [center_x, center_y, width, height] normalized [0, 1]
                        x1, y1, x2, y2 = coords
                        center_x = (x1 + x2) / 2 / width   # Normalize to [0, 1]
                        center_y = (y1 + y2) / 2 / height  # Normalize to [0, 1]
                        box_width = (x2 - x1) / width      # Normalize to [0, 1]
                        box_height = (y2 - y1) / height    # Normalize to [0, 1]
                        
                        box = [center_x, center_y, box_width, box_height]
                        label = True  # Positive box (foreground)
                        
                        state = processor.add_geometric_prompt(box, label, state)
                        
                        masks_tensor = state.get("masks")
                        if masks_tensor is not None and len(masks_tensor) > 0:
                            all_masks.append(masks_tensor)
                            all_mask_metadata.append({
                                "class_id": base_class_id + idx,
                                "class_name": f"box_{idx+1}",
                                "count": len(masks_tensor)
                            })
                            print(f"   ✓ Box prompt {idx+1}: {len(masks_tensor)} mask(s)")
            
            # Combine all masks from all prompts
            if len(all_masks) == 0:
                print("⚠️  No masks generated from any prompts")
                return DetectionResult(
                    task_type="segment",
                    inference_type="sam3",
                    inference_time_ms=(time.time() - start_time) * 1000,
                    masks=[],
                    boxes=[],
                    scores=[],
                    classes=[],
                    class_names=[]
                )
            
            # Concatenate all mask tensors
            import torch
            combined_masks = torch.cat(all_masks, dim=0) if len(all_masks) > 1 else all_masks[0]
            
            print(f"📊 Total masks collected: {len(combined_masks)}")
            
            # Convert masks to polygon format with metadata
            masks_list = self._masks_to_polygons(combined_masks, width, height, all_mask_metadata)
            
            # We can apply confidence filtering or class filtering here if needed
            if confidence is not None:
                # Filter masks by confidence score if available
                masks_list = [m for m in masks_list if m.get("score", 1.0) >= confidence]
                print(f"🔎 Applied confidence filter: {len(masks_list)} masks remain after filtering")

            if class_filter is not None:
                masks_list = [m for m in masks_list if m.get("class_name") in class_filter]
                print(f"🔎 Applied class filter: {len(masks_list)} masks remain after filtering")

            # Extract boxes, scores, classes for UI compatibility
            boxes = [mask["bbox"] for mask in masks_list]
            scores = [mask["score"] for mask in masks_list]
            classes = [mask["class_id"] for mask in masks_list]
            class_names = [mask["class_name"] for mask in masks_list]
            
            inference_time_ms = (time.time() - start_time) * 1000
            
            print(f"✅ SAM3 segmentation complete: {len(masks_list)} masks generated in {inference_time_ms:.1f}ms")
            
            # Cleanup
            self._cleanup_memory()
            
            return DetectionResult(
                task_type="segment",
                inference_type="sam3",
                inference_time_ms=inference_time_ms,
                masks=masks_list,
                boxes=boxes,
                scores=scores,
                classes=classes,
                class_names=class_names
            )
            
        except Exception as e:
            print(f"❌ Error during SAM3 segmentation: {e}")
            raise RuntimeError(f"Segmentation failed: {str(e)}")
    
    def _automatic_segmentation(
        self,
        processor,
        pil_image: Image.Image,
        width: int,
        height: int,
        start_time: float
    ) -> DetectionResult:
        """
        Perform automatic segmentation without prompts.
        
        SAM3 can automatically detect and segment all objects in an image
        without requiring any text, point, or box prompts.
        
        Args:
            processor: SAM3 processor instance
            pil_image: PIL Image to segment
            width: Image width
            height: Image height
            start_time: Start time for performance tracking
            
        Returns:
            DetectionResult with automatically detected masks
        """
        try:
            import torch
            
            # Set image
            state = processor.set_image(pil_image)
            
            # Set dummy text prompt "visual" for automatic segmentation
            # SAM3 requires some prompt, so we use "visual" as a generic trigger
            dummy_text_outputs = processor.model.backbone.forward_text(
                ["visual"], device=processor.device
            )
            state["backbone_out"].update(dummy_text_outputs)
            
            # Get dummy geometric prompt
            if "geometric_prompt" not in state:
                state["geometric_prompt"] = processor.model._get_dummy_prompt()
            
            # Run inference without specific prompts
            state = processor._forward_grounding(state)
            
            # Get masks
            masks_tensor = state.get("masks")
            if masks_tensor is None or len(masks_tensor) == 0:
                print("⚠️  No masks generated in automatic mode")
                return DetectionResult(
                    task_type="segment",
                    inference_type="sam3",
                    inference_time_ms=(time.time() - start_time) * 1000,
                    masks=[],
                    boxes=[],
                    scores=[],
                    classes=[],
                    class_names=[]
                )
            
            print(f"🎯 Automatic segmentation found {len(masks_tensor)} mask(s)")
            
            # Create metadata for automatic masks
            all_mask_metadata = [{
                "class_id": 0,
                "class_name": "object",
                "count": len(masks_tensor)
            }]
            
            # Convert masks to polygon format
            masks_list = self._masks_to_polygons(masks_tensor, width, height, all_mask_metadata)
            
            # Extract boxes, scores, classes for UI compatibility
            boxes = [mask["bbox"] for mask in masks_list]
            scores = [mask["score"] for mask in masks_list]
            classes = [mask["class_id"] for mask in masks_list]
            class_names = [mask["class_name"] for mask in masks_list]
            
            inference_time_ms = (time.time() - start_time) * 1000
            
            print(f"✅ Automatic segmentation complete: {len(masks_list)} masks in {inference_time_ms:.1f}ms")
            
            # Cleanup
            self._cleanup_memory()
            
            return DetectionResult(
                task_type="segment",
                inference_type="sam3",
                inference_time_ms=inference_time_ms,
                masks=masks_list,
                boxes=boxes,
                scores=scores,
                classes=classes,
                class_names=class_names
            )
            
        except Exception as e:
            print(f"❌ Error during automatic segmentation: {e}")
            raise RuntimeError(f"Automatic segmentation failed: {str(e)}")
    
    def _masks_to_polygons(
        self,
        masks_tensor,
        image_width: int,
        image_height: int,
        mask_metadata: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert SAM3 mask tensor to polygon format.
        
        Args:
            masks_tensor: Tensor of binary masks [N, H, W]
            image_width: Original image width
            image_height: Original image height
            mask_metadata: List of metadata dicts with class_id, class_name, count for each prompt
            
        Returns:
            List of mask dictionaries with polygons
        """
        import torch
        
        masks_list = []
        
        # Ensure masks is a tensor
        if isinstance(masks_tensor, torch.Tensor):
            masks_np = masks_tensor.cpu().numpy()
        else:
            masks_np = np.array(masks_tensor)
        
        # Handle different mask shapes more robustly
        print(f"📊 Masks tensor shape: {masks_np.shape}")
        
        if len(masks_np.shape) == 2:
            # Single mask [H, W]
            masks_np = masks_np[np.newaxis, ...]
        elif len(masks_np.shape) == 4:
            # [N, 1, H, W] - squeeze out the channel dimension
            if masks_np.shape[1] == 1:
                masks_np = masks_np.squeeze(1)  # Now [N, H, W]
                print(f"   Squeezed to shape: {masks_np.shape}")
            else:
                # [B, C, H, W] - take first batch if B=1, otherwise flatten
                if masks_np.shape[0] == 1:
                    masks_np = masks_np[0]  # Now [C, H, W]
                else:
                    # Multiple batches with channels - reshape to [N, H, W]
                    masks_np = masks_np.reshape(-1, masks_np.shape[2], masks_np.shape[3])
                print(f"   Reshaped to: {masks_np.shape}")
        elif len(masks_np.shape) == 3:
            # Already [N, H, W] - good to go
            pass
        else:
            raise ValueError(f"Unexpected mask shape: {masks_np.shape}")
        
        # Build class mapping from metadata
        mask_to_class = {}
        if mask_metadata:
            current_mask_idx = 0
            for meta in mask_metadata:
                for i in range(meta["count"]):
                    mask_to_class[current_mask_idx] = {
                        "class_id": meta["class_id"],
                        "class_name": meta["class_name"]
                    }
                    current_mask_idx += 1
        
        # Process each mask
        for idx, mask in enumerate(masks_np):
            # Ensure mask is binary
            if mask.dtype != np.uint8:
                mask = (mask > 0.5).astype(np.uint8)
            
            # Check if mask is empty
            mask_pixels = np.sum(mask > 0)
            if mask_pixels == 0:
                print(f"   ⚠️  Mask {idx+1}: Empty mask, skipping")
                continue
            
            # Resize mask to original image size if needed
            if mask.shape[0] != image_height or mask.shape[1] != image_width:
                mask = cv2.resize(
                    mask.astype(np.uint8),
                    (image_width, image_height),
                    interpolation=cv2.INTER_NEAREST
                )
            
            # Find contours
            contours, _ = cv2.findContours(
                mask.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            # Convert largest contour to polygon
            if len(contours) > 0:
                # Use the largest contour
                largest_contour = max(contours, key=cv2.contourArea)
                contour_area = cv2.contourArea(largest_contour)
                
                # Skip very small contours (likely noise)
                if contour_area < 100:  # Minimum 100 pixels
                    print(f"   ⚠️  Mask {idx+1}: Contour too small ({contour_area:.0f} pixels), skipping")
                    continue
                
                # Simplify contour
                epsilon = 0.002 * cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                # Convert to list of [x, y] coordinates
                polygon = approx.reshape(-1, 2).tolist()
                
                # Calculate bounding box
                x_coords = [p[0] for p in polygon]
                y_coords = [p[1] for p in polygon]
                bbox = [
                    min(x_coords),
                    min(y_coords),
                    max(x_coords),
                    max(y_coords)
                ]
                
                # Calculate mask area (approximate confidence)
                mask_area = cv2.contourArea(largest_contour)
                bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                score = mask_area / bbox_area if bbox_area > 0 else 1.0
                
                # Get class info from metadata
                class_info = mask_to_class.get(idx, {"class_id": 0, "class_name": "object"})
                
                print(f"   ✓ Mask {idx+1}: {contour_area:.0f} pixels, class '{class_info['class_name']}', bbox {bbox}, score {score:.3f}")
                
                masks_list.append({
                    "instance_id": idx,
                    "class_id": class_info["class_id"],
                    "class_name": class_info["class_name"],
                    "bbox": bbox,
                    "score": float(score),
                    "polygon": polygon,
                    "height": image_height,
                    "width": image_width
                })
            else:
                print(f"   ⚠️  Mask {idx+1}: No contours found, skipping")
        
        print(f"📋 Converted {len(masks_list)} valid masks out of {len(masks_np)} total")
        return masks_list
    
    def _cleanup_memory(self):
        """Clean up GPU/CPU memory after inference."""
        try:
            import torch
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            print(f"⚠️  Memory cleanup warning: {e}")
    
    def clear_cache(self):
        """Clear all cached models and processors."""
        self._model_cache.clear()
        self._processor_cache.clear()
        self._cleanup_memory()
        print("✅ SAM3 model cache cleared")

    def cleanup(self):
        """Cleanup resources before shutdown."""
        self.clear_cache()
        print("✅ SAM3 service cleanup complete")


# Global SAM3 service instance
sam3_service = SAM3Service()
