/**
 * Drawing Utilities for Inference Results
 * Unified canvas drawing functions for YOLO, SAM3, and future models
 */

import type { PredictionResponse } from '@/lib/types';

export interface MaskData {
    polygon: number[][];
    confidence?: number;
    class_name?: string;
}

export interface DrawOptions {
    showLabels?: boolean;
    showConfidence?: boolean;
    lineWidth?: number;
    fontSize?: number;
    boxColor?: string;
    selectedClasses?: Set<string>;
}

export interface MaskRenderOptions {
    fillOpacity?: number;
    strokeOpacity?: number;
    strokeWidth?: number;
}

/**
 * Generate color using golden angle for evenly distributed hues
 * Cached for performance
 */
const colorCache = new Map<number, { fill: string; stroke: string }>();

export function generateMaskColor(index: number): { fill: string; stroke: string } {
    if (colorCache.has(index)) {
        return colorCache.get(index)!;
    }
    
    const hue = (index * 137.508) % 360;
    const colors = {
        fill: `hsla(${hue}, 70%, 50%, 0.3)`,
        stroke: `hsl(${hue}, 70%, 40%)`
    };
    
    colorCache.set(index, colors);
    return colors;
}

/**
 * Draw a single polygon mask on canvas
 */
export function drawPolygonMask(
    ctx: CanvasRenderingContext2D,
    polygon: number[][],
    colorIndex: number,
    options: MaskRenderOptions = {}
): void {
    const { fillOpacity = 0.3, strokeOpacity = 1.0, strokeWidth = 2 } = options;
    
    if (!polygon || polygon.length < 3) return;
    
    const { fill, stroke } = generateMaskColor(colorIndex);
    
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(polygon[0][0], polygon[0][1]);
    
    for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i][0], polygon[i][1]);
    }
    
    ctx.closePath();
    
    // Fill with transparency
    ctx.fillStyle = fill.replace(/[\d.]+\)$/, `${fillOpacity})`);
    ctx.fill();
    
    // Stroke with solid color
    ctx.strokeStyle = stroke;
    ctx.lineWidth = strokeWidth;
    ctx.stroke();
    
    ctx.restore();
}

/**
 * Draw a bounding box with label
 */
export function drawBoundingBox(
    ctx: CanvasRenderingContext2D,
    box: number[],
    label: string,
    confidence: number,
    options: DrawOptions = {}
): void {
    const {
        showLabels = true,
        showConfidence = true,
        lineWidth = 3,
        fontSize = 14,
        boxColor = '#E1604C'
    } = options;
    
    const [x1, y1, x2, y2] = box;
    
    ctx.save();
    
    // Draw box
    ctx.strokeStyle = boxColor;
    ctx.lineWidth = lineWidth;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    
    if (showLabels) {
        // Prepare label text
        const confidenceText = showConfidence ? ` ${(confidence * 100).toFixed(0)}%` : '';
        const labelText = `${label}${confidenceText}`;
        
        ctx.font = `bold ${fontSize}px Montserrat, sans-serif`;
        const textWidth = ctx.measureText(labelText).width;
        
        // Draw label background
        const labelHeight = fontSize + 10;
        ctx.fillStyle = boxColor;
        ctx.fillRect(x1, y1 - labelHeight, textWidth + 10, labelHeight);
        
        // Draw label text
        ctx.fillStyle = '#FFFFFF';
        ctx.textBaseline = 'top';
        ctx.fillText(labelText, x1 + 5, y1 - labelHeight + 2);
    }
    
    ctx.restore();
}

/**
 * Draw classification result (top center label)
 */
export function drawClassification(
    ctx: CanvasRenderingContext2D,
    topClass: string,
    confidence: number,
    canvasWidth: number,
    options: DrawOptions = {}
): void {
    const { fontSize = 20 } = options;
    
    ctx.save();
    
    const labelText = `${topClass} ${(confidence * 100).toFixed(1)}%`;
    ctx.font = `bold ${fontSize}px Montserrat, sans-serif`;
    const textWidth = ctx.measureText(labelText).width;
    
    const x = (canvasWidth - textWidth) / 2;
    const y = 20;
    const padding = 10;
    
    // Background
    ctx.fillStyle = 'rgba(29, 47, 67, 0.9)';
    ctx.fillRect(x - padding, y - padding, textWidth + padding * 2, fontSize + padding * 2);
    
    // Text
    ctx.fillStyle = '#FFFFFF';
    ctx.textBaseline = 'top';
    ctx.fillText(labelText, x, y);
    
    ctx.restore();
}

/**
 * Main orchestrator: Draw all inference results on canvas
 */
export function drawInferenceResults(
    ctx: CanvasRenderingContext2D,
    response: PredictionResponse,
    options: DrawOptions = {}
): void {
    if (!ctx || !response) return;
    
    const { task_type = 'detect' } = response;
    const { selectedClasses } = options;
    
    // Task-specific rendering
    switch (task_type) {
        case 'classify':
            // Draw classification label
            if (response.top_class && response.top_confidence !== undefined) {
                drawClassification(
                    ctx,
                    response.top_class,
                    response.top_confidence,
                    ctx.canvas.width,
                    options
                );
            }
            break;
            
        case 'detect':
        case 'segment':
            // Draw masks first (if available)
            if (response.masks && response.masks.length > 0) {
                response.masks.forEach((mask: MaskData, index: number) => {
                    // Filter by selected classes if specified
                    if (selectedClasses && mask.class_name && !selectedClasses.has(mask.class_name)) {
                        return;
                    }
                    
                    if (mask.polygon && mask.polygon.length > 0) {
                        drawPolygonMask(ctx, mask.polygon, index);
                    }
                });
            }
            
            // Draw bounding boxes (if available)
            if (response.boxes && response.boxes.length > 0) {
                response.boxes.forEach((box: number[], index: number) => {
                    const className = response.class_names?.[index] || 'Unknown';
                    const score = response.scores?.[index] || 0;
                    
                    // Filter by selected classes if specified
                    if (selectedClasses && !selectedClasses.has(className)) {
                        return;
                    }
                    
                    drawBoundingBox(ctx, box, className, score, options);
                });
            }
            break;
            
        default:
            // Fall through to detect mode - draw boxes if available
            if (response.boxes && response.boxes.length > 0) {
                response.boxes.forEach((box: number[], index: number) => {
                    const className = response.class_names?.[index] || 'Unknown';
                    const score = response.scores?.[index] || 0;
                    
                    if (selectedClasses && !selectedClasses.has(className)) {
                        return;
                    }
                    
                    drawBoundingBox(ctx, box, className, score, options);
                });
            }
            break;
    }
}

/**
 * Draw inference results with scaling (for different canvas sizes)
 */
export function drawInferenceResultsScaled(
    ctx: CanvasRenderingContext2D,
    response: PredictionResponse,
    scaleX: number,
    scaleY: number,
    options: DrawOptions = {}
): void {
    if (!ctx || !response) return;
    
    ctx.save();
    ctx.scale(scaleX, scaleY);
    
    drawInferenceResults(ctx, response, options);
    
    ctx.restore();
}

/**
 * Draw inference results to a new canvas and return as Data URL
 * Useful for gallery thumbnails
 */
export async function drawInferenceResultsToDataURL(
    sourceImage: HTMLImageElement | HTMLCanvasElement,
    response: PredictionResponse,
    options: DrawOptions = {}
): Promise<string> {
    const canvas = document.createElement('canvas');
    canvas.width = sourceImage.width;
    canvas.height = sourceImage.height;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        throw new Error('Failed to get canvas context');
    }
    
    // Draw source image
    ctx.drawImage(sourceImage, 0, 0);
    
    // Draw inference results
    drawInferenceResults(ctx, response, options);
    
    return canvas.toDataURL('image/jpeg', 0.95);
}
