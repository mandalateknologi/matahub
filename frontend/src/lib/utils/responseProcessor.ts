/**
 * Response Processing Utilities
 * Unified processing for inference responses (YOLO, SAM3, future models)
 */

import type { PredictionResponse } from '@/lib/types';

export interface ProcessedResults {
    detectionResults: Array<{ class_name: string; confidence: number }>;
    classCounts: Record<string, number>;
    availableClasses: string[];
    frameStats: FrameStats;
}

export interface FrameStats {
    width: number;
    height: number;
    fps?: number;
    totalDetections: number;
    totalMasks: number;
    avgConfidence: number;
    task_type: string;
}

/**
 * Normalize inference response to ensure consistent structure
 * Handles differences between YOLO and SAM3 responses
 */
export function normalizeInferenceResponse(response: PredictionResponse): PredictionResponse {
    // Ensure arrays are initialized
    return {
        ...response,
        boxes: response.boxes || [],
        scores: response.scores || [],
        classes: response.classes || [],
        class_names: response.class_names || [],
        masks: response.masks || [],
        top_classes: response.top_classes || [],
        probabilities: response.probabilities || []
    };
}

/**
 * Process inference response and extract statistics
 * Unified logic for all task types (detect, classify, segment)
 * Replaces processDetectionResults() and updateCurrentFrameStats()
 */
export function processInferenceResponse(
    response: PredictionResponse,
    frameWidth: number = 0,
    frameHeight: number = 0,
    frameFps?: number
): ProcessedResults {
    const normalized = normalizeInferenceResponse(response);
    const { task_type = 'detect' } = normalized;
    
    let detectionResults: Array<{ class_name: string; confidence: number }> = [];
    let classCounts: Record<string, number> = {};
    let totalDetections = 0;
    let totalMasks = 0;
    let totalConfidence = 0;
    let confidenceCount = 0;
    
    // Process based on task type
    switch (task_type) {
        case 'classify':
            // Classification: Process top classes
            if (normalized.top_classes && normalized.probabilities) {
                detectionResults = normalized.top_classes.map((className: string, index: number) => ({
                    class_name: className,
                    confidence: normalized.probabilities![index] || 0
                }));
                
                // Count occurrences
                normalized.top_classes.forEach((className: string) => {
                    classCounts[className] = (classCounts[className] || 0) + 1;
                });
                
                totalDetections = normalized.top_classes.length;
                totalConfidence = normalized.probabilities.reduce((sum: number, conf: number) => sum + conf, 0);
                confidenceCount = normalized.probabilities.length;
            }
            break;
            
        case 'detect':
        case 'segment':
            // Detection/Segmentation: Process boxes and masks
            if (normalized.class_names && normalized.scores) {
                detectionResults = normalized.class_names.map((className: string, index: number) => ({
                    class_name: className,
                    confidence: normalized.scores![index] || 0
                }));
                
                // Sort by confidence (descending)
                detectionResults.sort((a, b) => b.confidence - a.confidence);
                
                // Count occurrences per class
                normalized.class_names.forEach((className: string) => {
                    classCounts[className] = (classCounts[className] || 0) + 1;
                });
                
                totalDetections = normalized.class_names.length;
                totalConfidence = normalized.scores.reduce((sum: number, score: number) => sum + score, 0);
                confidenceCount = normalized.scores.length;
            }
            
            // Count masks
            if (normalized.masks) {
                totalMasks = normalized.masks.length;
            }
            break;
    }
    
    // Extract available classes (sorted alphabetically)
    const availableClasses = Object.keys(classCounts).sort();
    
    // Calculate average confidence
    const avgConfidence = confidenceCount > 0 ? totalConfidence / confidenceCount : 0;
    
    // Build frame stats
    const frameStats: FrameStats = {
        width: frameWidth,
        height: frameHeight,
        fps: frameFps,
        totalDetections,
        totalMasks,
        avgConfidence,
        task_type
    };
    
    return {
        detectionResults,
        classCounts,
        availableClasses,
        frameStats
    };
}

/**
 * Extract class filter from current results
 * Used to populate filter UI
 */
export function extractClassesFromResults(results: Array<{ class_name: string; confidence: number }>): string[] {
    const uniqueClasses = new Set<string>();
    results.forEach(result => {
        if (result.class_name) {
            uniqueClasses.add(result.class_name);
        }
    });
    return Array.from(uniqueClasses).sort();
}

/**
 * Filter results by class names
 */
export function filterResultsByClasses(
    results: Array<{ class_name: string; confidence: number }>,
    selectedClasses: Set<string>
): Array<{ class_name: string; confidence: number }> {
    if (selectedClasses.size === 0) {
        return results;
    }
    return results.filter(result => selectedClasses.has(result.class_name));
}

/**
 * Calculate confidence statistics
 */
export function calculateConfidenceStats(results: Array<{ class_name: string; confidence: number }>): {
    min: number;
    max: number;
    avg: number;
    median: number;
} {
    if (results.length === 0) {
        return { min: 0, max: 0, avg: 0, median: 0 };
    }
    
    const confidences = results.map(r => r.confidence).sort((a, b) => a - b);
    const sum = confidences.reduce((acc, val) => acc + val, 0);
    
    return {
        min: confidences[0],
        max: confidences[confidences.length - 1],
        avg: sum / confidences.length,
        median: confidences[Math.floor(confidences.length / 2)]
    };
}
