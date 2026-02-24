/**
 * Segmentation Format Utilities
 * 
 * Handles conversion between different polygon/mask formats:
 * - Fabric.js polygon objects (pixel coordinates)
 * - YOLO segmentation format (normalized polygon points)
 * - Backend API format
 */

import { fabric } from 'fabric';

export interface SegmentationPolygon {
  class_id: number;
  points: number[]; // Flat array: [x1, y1, x2, y2, x3, y3, ...]
}

export interface SegmentationLabel {
  image_width: number;
  image_height: number;
  polygons: SegmentationPolygon[];
  classes: { [key: string]: string };
}

export interface FabricPolygonData {
  polygon: fabric.Polygon;
  class_id: number;
  className: string;
}

/**
 * Convert Fabric.js polygon to YOLO normalized format
 * 
 * CRITICAL: Extracts canvas-space coordinates via transformation matrix,
 * then reverses ONLY the background image transformation (not polygon's own transforms)
 * to get back to image-space, then normalizes.
 */
export function fabricPolygonToYOLO(
  polygon: fabric.Polygon,
  class_id: number,
  imageWidth: number,
  imageHeight: number,
  imageScale: number = 1,
  imageLeft: number = 0,
  imageTop: number = 0
): SegmentationPolygon {
  const points = polygon.points || [];
  const normalizedPoints: number[] = [];

  // Points are in canvas-space coordinates
  // Need to convert: canvas-space → image-space → normalized
  
  let lastNormalizedX: number | null = null;
  let lastNormalizedY: number | null = null;
  
  for (const point of points) {
    // Convert canvas-space to image-space by reversing background transformation
    const imageX = (point.x - imageLeft) / imageScale;
    const imageY = (point.y - imageTop) / imageScale;

    // Normalize coordinates to 0-1 range
    const normalizedX = imageX / imageWidth;
    const normalizedY = imageY / imageHeight;

    // Clamp to valid range and warn if out of bounds (indicates corruption)
    const clampedX = Math.max(0, Math.min(1, normalizedX));
    const clampedY = Math.max(0, Math.min(1, normalizedY));
    
    if (normalizedX < 0 || normalizedX > 1 || normalizedY < 0 || normalizedY > 1) {
      console.warn('Polygon coordinate out of bounds:', { normalizedX, normalizedY, clampedX, clampedY });
    }

    // Skip duplicate consecutive points (Fabric.js auto-closes polygons)
    // Use small epsilon for floating point comparison
    const epsilon = 0.000001;
    if (lastNormalizedX !== null && lastNormalizedY !== null) {
      const dx = Math.abs(clampedX - lastNormalizedX);
      const dy = Math.abs(clampedY - lastNormalizedY);
      if (dx < epsilon && dy < epsilon) {
        continue; // Skip this duplicate point
      }
    }

    normalizedPoints.push(clampedX, clampedY);
    lastNormalizedX = clampedX;
    lastNormalizedY = clampedY;
  }

  return {
    class_id,
    points: normalizedPoints
  };
}

/**
 * Convert YOLO normalized polygon to Fabric.js polygon (pixel coordinates)
 * 
 * CRITICAL: Creates polygon in CANVAS-SPACE coordinates directly.
 * Points are converted from normalized → image-space → canvas-space.
 * Polygon has NO transformations (left=0, top=0, scale=1) to prevent drift.
 */
export function yoloPolygonToFabric(
  polygon: SegmentationPolygon,
  imageWidth: number,
  imageHeight: number,
  className: string,
  color: string,
  imageScale: number = 1,
  imageLeft: number = 0,
  imageTop: number = 0
): FabricPolygonData {
  const points: { x: number; y: number }[] = [];

  // Convert normalized → image-space → canvas-space
  for (let i = 0; i < polygon.points.length; i += 2) {
    // Denormalize to image-space
    const imageX = polygon.points[i] * imageWidth;
    const imageY = polygon.points[i + 1] * imageHeight;
    
    // Transform to canvas-space by applying background image transformation
    const canvasX = imageX * imageScale + imageLeft;
    const canvasY = imageY * imageScale + imageTop;
    
    points.push({ x: canvasX, y: canvasY });
  }

  // Create polygon in canvas-space with NO transformations
  const fabricPolygon = new fabric.Polygon(points, {
    fill: color + '40', // Semi-transparent fill
    stroke: color,
    strokeWidth: 2,
    objectCaching: false,
    selectable: true,
    hasBorders: true,
    hasControls: true,
    lockRotation: true,
    perPixelTargetFind: true,
    strokeUniform: true,
    strokeLineJoin: 'round',
  });

  return {
    polygon: fabricPolygon,
    class_id: polygon.class_id,
    className
  };
}

/**
 * Convert all Fabric.js polygons to segmentation label format for API
 */
export function fabricCanvasToSegmentationLabel(
  canvas: fabric.Canvas,
  polygonData: Map<fabric.Polygon, { class_id: number; className: string }>,
  imageWidth: number,
  imageHeight: number,
  classes: { [key: string]: string }
): SegmentationLabel {
  const polygons: SegmentationPolygon[] = [];

  // Get background image transformation
  const bgImage = canvas.backgroundImage as fabric.Image;
  const imageScale = bgImage?.scaleX || 1;
  const imageLeft = bgImage?.left || 0;
  const imageTop = bgImage?.top || 0;

  canvas.getObjects('polygon').forEach((obj) => {
    const polygon = obj as fabric.Polygon;
    const data = polygonData.get(polygon);
    
    if (data) {
      polygons.push(
        fabricPolygonToYOLO(
          polygon, 
          data.class_id, 
          imageWidth, 
          imageHeight,
          imageScale,
          imageLeft,
          imageTop
        )
      );
    }
  });

  return {
    image_width: imageWidth,
    image_height: imageHeight,
    polygons,
    classes
  };
}

/**
 * Load segmentation labels into Fabric.js canvas
 */
export function loadSegmentationLabelToCanvas(
  canvas: fabric.Canvas,
  label: SegmentationLabel,
  classColors: Map<number, string>,
  onPolygonAdded: (polygon: fabric.Polygon, class_id: number, className: string) => void
): void {
  // Preserve background image before clearing
  const bgImage = canvas.backgroundImage;
  
  // Clear only objects, not background
  canvas.remove(...canvas.getObjects());

  // Restore background image if it was set
  if (bgImage) {
    canvas.backgroundImage = bgImage;
  }

  // Get the scale and position of the background image
  const fabricImage = bgImage as fabric.Image;
  const imageScale = fabricImage?.scaleX || 1;
  const imageLeft = fabricImage?.left || 0;
  const imageTop = fabricImage?.top || 0;

  label.polygons.forEach((polygon) => {
    const className = label.classes[polygon.class_id.toString()] || 'Unknown';
    const color = classColors.get(polygon.class_id) || '#00FF00';

    const fabricData = yoloPolygonToFabric(
      polygon,
      label.image_width,
      label.image_height,
      className,
      color,
      imageScale,
      imageLeft,
      imageTop
    );

    canvas.add(fabricData.polygon);
    onPolygonAdded(fabricData.polygon, fabricData.class_id, fabricData.className);
  });

  canvas.renderAll();
}

/**
 * Generate random color for class
 */
export function generateClassColor(classId: number): string {
  const hue = (classId * 137) % 360; // Golden angle for good color distribution
  return `hsl(${hue}, 70%, 50%)`;
}

/**
 * Parse YOLO segmentation label file content
 * Format: class_id x1 y1 x2 y2 x3 y3 ...
 */
export function parseYOLOSegmentationFile(content: string): SegmentationPolygon[] {
  const lines = content.trim().split('\n').filter(line => line.trim());
  const polygons: SegmentationPolygon[] = [];

  for (const line of lines) {
    const parts = line.trim().split(/\s+/).map(parseFloat);
    
    if (parts.length < 7) {
      // Need at least class_id + 3 points (6 coordinates)
      console.warn('Invalid segmentation label line (too few points):', line);
      continue;
    }

    const class_id = Math.floor(parts[0]);
    const points = parts.slice(1);

    // Validate even number of coordinates
    if (points.length % 2 !== 0) {
      console.warn('Invalid segmentation label line (odd number of coordinates):', line);
      continue;
    }

    polygons.push({ class_id, points });
  }

  return polygons;
}

/**
 * Format segmentation polygons to YOLO label file content
 */
export function formatYOLOSegmentationFile(polygons: SegmentationPolygon[]): string {
  return polygons
    .map(polygon => {
      const pointsStr = polygon.points
        .map(p => p.toFixed(6))
        .join(' ');
      return `${polygon.class_id} ${pointsStr}`;
    })
    .join('\n');
}
