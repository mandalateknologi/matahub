"""
Image processing utilities for workflows.

Provides functions for image manipulation including bounding box cropping,
padding, and coordinate transformations.
"""

from pathlib import Path
from typing import List
from PIL import Image
import logging

logger = logging.getLogger(__name__)


def crop_bbox_with_padding(
    image: Image.Image,
    bbox: List[float],
    padding_percent: float = 0.15,
) -> Image.Image:
    """
    Crop a bounding box from an image with padding.
    
    Adds padding around the bounding box and clips coordinates to stay
    within image bounds.
    
    Args:
        image: PIL Image object to crop from
        bbox: Bounding box coordinates [x1, y1, x2, y2]
        padding_percent: Percentage of bbox size to add as padding (0.0-0.5)
                        Default 0.15 = 15% padding
    
    Returns:
        Cropped PIL Image object
    
    Raises:
        ValueError: If bbox coordinates are invalid or padding is out of range
    
    Example:
        >>> img = Image.open("photo.jpg")
        >>> bbox = [100, 50, 200, 150]  # x1, y1, x2, y2
        >>> cropped = crop_bbox_with_padding(img, bbox, padding_percent=0.2)
    """
    if not (0.0 <= padding_percent <= 0.5):
        raise ValueError(f"padding_percent must be between 0.0 and 0.5, got {padding_percent}")
    
    if len(bbox) != 4:
        raise ValueError(f"bbox must have 4 coordinates [x1, y1, x2, y2], got {len(bbox)}")
    
    x1, y1, x2, y2 = bbox
    
    # Validate bbox coordinates
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"Invalid bbox coordinates: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
    
    width, height = image.size
    
    # Handle normalized coordinates (0-1 range)
    if x2 <= 1.0 and y2 <= 1.0:
        x1, x2 = x1 * width, x2 * width
        y1, y2 = y1 * height, y2 * height
    
    # Calculate padding based on bbox size
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    pad_w = bbox_width * padding_percent
    pad_h = bbox_height * padding_percent
    
    # Apply padding and clip to image bounds
    x1_padded = max(0, x1 - pad_w)
    y1_padded = max(0, y1 - pad_h)
    x2_padded = min(width, x2 + pad_w)
    y2_padded = min(height, y2 + pad_h)
    
    # Convert to integers for cropping
    crop_box = (
        int(x1_padded),
        int(y1_padded),
        int(x2_padded),
        int(y2_padded)
    )
    
    logger.debug(f"Cropping bbox {bbox} with {padding_percent*100}% padding: {crop_box}")
    
    # Crop and return
    return image.crop(crop_box)


def normalize_bbox_coordinates(
    bbox: List[float],
    image_width: int,
    image_height: int
) -> List[int]:
    """
    Normalize bounding box coordinates to absolute pixel values.
    
    Converts normalized coordinates (0-1) to absolute pixel coordinates.
    If coordinates are already absolute, returns them as integers.
    
    Args:
        bbox: Bounding box [x1, y1, x2, y2]
        image_width: Image width in pixels
        image_height: Image height in pixels
    
    Returns:
        Absolute coordinates [x1, y1, x2, y2] as integers
    """
    x1, y1, x2, y2 = bbox
    
    # Check if normalized (all values <= 1)
    if x2 <= 1.0 and y2 <= 1.0:
        x1 = int(x1 * image_width)
        x2 = int(x2 * image_width)
        y1 = int(y1 * image_height)
        y2 = int(y2 * image_height)
    else:
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    
    return [x1, y1, x2, y2]


def validate_image_path(image_path: str) -> Path:
    """
    Validate that an image path exists and is a supported format.
    
    Args:
        image_path: Path to image file
    
    Returns:
        Path object if valid
    
    Raises:
        FileNotFoundError: If image doesn't exist
        ValueError: If image format not supported
    """
    path = Path(image_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    if path.suffix.lower() not in supported_formats:
        raise ValueError(f"Unsupported image format: {path.suffix}")
    
    return path
