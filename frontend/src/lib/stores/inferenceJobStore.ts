/**
 * Inference Job Store (Generalized for reuse)
 * 
 * Manages inference detection state, job status, results, and RTSP frame data.
 * Provides derived stores for computed values like availableClasses, filteredResults.
 * 
 * Replaces RS1 (RTSP frame rendering) from capture page reactive statements.
 */

import { writable, derived, get } from 'svelte/store';
import type { 
  PredictionJob, 
  PredictionResponse, 
  PredictionResponseWithFrame 
} from '@/lib/types';

// ===========================
// Type Definitions
// ===========================

export interface DetectionResult {
  class_name: string;
  confidence: number;
  bbox?: number[];
  count?: number;
}

export interface FrameStats {
  width: number;
  height: number;
  fps: number;
  totalDetections: number;
  timestamp?: string;
}

export interface InferenceJobState {
  // Job State
  isDetecting: boolean;
  currentJob: PredictionJob | null;
  
  // Results
  detections: PredictionResponse | null;
  detectionResults: DetectionResult[];
  classCounts: Record<string, number>;
  frameStats: FrameStats;
  
  // Last prediction (for display)
  lastPredictionResponse: PredictionResponse | null;
  
  // Batch/Video Progress
  batchProgress: {
    current: number;
    total: number;
    fileName: string;
  };
  
  // Video Session (manual capture mode)
  activeVideoSession: PredictionJob | null;
  activeWebcamSession: PredictionJob | null;
  
  // RTSP Live Frame
  rtspLastFrameData: PredictionResponseWithFrame | null;
  rtspFrameStatus: 'loading' | 'ready' | 'error';
  
  // Processed Frames (for video/RTSP to avoid duplicates)
  processedFrameNumbers: Set<number>;
}

// ===========================
// Default Values
// ===========================

const DEFAULT_STATE: InferenceJobState = {
  isDetecting: false,
  currentJob: null,
  detections: null,
  detectionResults: [],
  classCounts: {},
  frameStats: {
    width: 0,
    height: 0,
    fps: 0,
    totalDetections: 0,
  },
  lastPredictionResponse: null,
  batchProgress: {
    current: 0,
    total: 0,
    fileName: '',
  },
  activeVideoSession: null,
  activeWebcamSession: null,
  rtspLastFrameData: null,
  rtspFrameStatus: 'loading',
  processedFrameNumbers: new Set(),
};

// ===========================
// Helper Functions
// ===========================

/**
 * Process detection response into DetectionResult array
 */
function processDetectionResponse(
  response: PredictionResponse,
  width: number,
  height: number,
  fps?: number
): {
  detectionResults: DetectionResult[];
  classCounts: Record<string, number>;
  frameStats: FrameStats;
} {
  const detectionResults: DetectionResult[] = [];
  const classCounts: Record<string, number> = {};
  
  // Process based on task type
  if (response.class_names && response.scores) {
    // Detection/Segmentation
    response.class_names.forEach((name, i) => {
      detectionResults.push({
        class_name: name,
        confidence: response.scores![i],
        bbox: response.boxes?.[i],
      });
      
      classCounts[name] = (classCounts[name] || 0) + 1;
    });
  } else if (response.top_class && response.top_confidence !== undefined) {
    // Classification
    detectionResults.push({
      class_name: response.top_class,
      confidence: response.top_confidence,
    });
    
    classCounts[response.top_class] = 1;
  }
  
  const frameStats: FrameStats = {
    width,
    height,
    fps: fps || 0,
    totalDetections: detectionResults.length,
    timestamp: response.frame_timestamp,
  };
  
  return { detectionResults, classCounts, frameStats };
}

/**
 * Extract unique class names from detection results
 */
function extractClasses(results: DetectionResult[]): string[] {
  const classSet = new Set<string>();
  results.forEach(result => classSet.add(result.class_name));
  return Array.from(classSet).sort();
}

/**
 * Calculate confidence statistics
 */
function calculateConfidenceStats(results: DetectionResult[]): {
  min: number;
  max: number;
  avg: number;
  median: number;
} {
  if (results.length === 0) {
    return { min: 0, max: 0, avg: 0, median: 0 };
  }
  
  const confidences = results.map(r => r.confidence).sort((a, b) => a - b);
  const min = confidences[0];
  const max = confidences[confidences.length - 1];
  const avg = confidences.reduce((sum, c) => sum + c, 0) / confidences.length;
  const median = confidences[Math.floor(confidences.length / 2)];
  
  return { min, max, avg, median };
}

// ===========================
// Store Factory
// ===========================

function createInferenceJobStore() {
  const { subscribe, set, update } = writable<InferenceJobState>(DEFAULT_STATE);
  
  return {
    subscribe,
    
    /**
     * Start a new inference job
     */
    startJob: (job: PredictionJob) => {
      update(state => ({
        ...state,
        isDetecting: true,
        currentJob: job,
        detections: null,
        detectionResults: [],
        classCounts: {},
        batchProgress: { current: 0, total: 0, fileName: '' },
      }));
    },
    
    /**
     * Update job status/progress
     */
    updateJob: (job: Partial<PredictionJob>) => {
      update(state => ({
        ...state,
        currentJob: state.currentJob ? { ...state.currentJob, ...job } : null,
      }));
    },
    
    /**
     * Update batch processing progress
     */
    updateBatchProgress: (current: number, total: number, fileName: string) => {
      update(state => ({
        ...state,
        batchProgress: { current, total, fileName },
      }));
    },
    
    /**
     * Complete a job
     */
    completeJob: () => {
      update(state => ({
        ...state,
        isDetecting: false,
        currentJob: null,
        batchProgress: { current: 0, total: 0, fileName: '' },
      }));
    },
    
    /**
     * Update inference results
     */
    updateResults: (response: PredictionResponse, width: number, height: number, fps?: number) => {
      const processed = processDetectionResponse(response, width, height, fps);
      
      update(state => ({
        ...state,
        detections: response,
        detectionResults: processed.detectionResults,
        classCounts: processed.classCounts,
        frameStats: processed.frameStats,
        lastPredictionResponse: response,
      }));
    },
    
    /**
     * Clear current results
     */
    clearResults: () => {
      update(state => ({
        ...state,
        detections: null,
        detectionResults: [],
        classCounts: {},
        frameStats: DEFAULT_STATE.frameStats,
        lastPredictionResponse: null,
      }));
    },
    
    /**
     * Update RTSP live frame data
     */
    updateRTSPFrame: (frameData: PredictionResponseWithFrame) => {
      update(state => ({
        ...state,
        rtspLastFrameData: frameData,
        rtspFrameStatus: 'ready',
      }));
    },
    
    /**
     * Set RTSP frame status
     */
    setRTSPFrameStatus: (status: 'loading' | 'ready' | 'error') => {
      update(state => ({ ...state, rtspFrameStatus: status }));
    },
    
    /**
     * Clear RTSP frame data
     */
    clearRTSPFrame: () => {
      update(state => ({
        ...state,
        rtspLastFrameData: null,
        rtspFrameStatus: 'loading',
      }));
    },
    
    /**
     * Start video manual session
     */
    startVideoSession: (job: PredictionJob) => {
      update(state => ({
        ...state,
        activeVideoSession: job,
        processedFrameNumbers: new Set(),
      }));
    },
    
    /**
     * End video manual session
     */
    endVideoSession: () => {
      update(state => ({
        ...state,
        activeVideoSession: null,
        processedFrameNumbers: new Set(),
      }));
    },
    
    /**
     * Start webcam session
     */
    startWebcamSession: (job: PredictionJob) => {
      update(state => ({
        ...state,
        activeWebcamSession: job,
      }));
    },
    
    /**
     * End webcam session
     */
    endWebcamSession: () => {
      update(state => ({
        ...state,
        activeWebcamSession: null,
      }));
    },
    
    /**
     * Mark frame as processed (for video/RTSP)
     */
    markFrameProcessed: (frameNumber: number) => {
      update(state => {
        const newSet = new Set(state.processedFrameNumbers);
        newSet.add(frameNumber);
        return { ...state, processedFrameNumbers: newSet };
      });
    },
    
    /**
     * Check if frame already processed
     */
    isFrameProcessed: (frameNumber: number): boolean => {
      const state = get({ subscribe });
      return state.processedFrameNumbers.has(frameNumber);
    },
    
    /**
     * Reset all state (for new capture session)
     */
    reset: () => {
      set(DEFAULT_STATE);
    },
  };
}

// ===========================
// Export Store Instance
// ===========================

export const inferenceJobStore = createInferenceJobStore();

// ===========================
// Derived Stores
// ===========================

/**
 * Available class names from current results
 */
export const availableClasses = derived(
  inferenceJobStore,
  ($job) => extractClasses($job.detectionResults)
);

/**
 * Filtered results by selected classes
 * Requires selectedClasses parameter
 */
export function filteredResults(selectedClasses: Set<string>) {
  return derived(
    inferenceJobStore,
    ($job) => {
      if (selectedClasses.size === 0) {
        return $job.detectionResults;
      }
      return $job.detectionResults.filter(r => selectedClasses.has(r.class_name));
    }
  );
}

/**
 * Confidence statistics
 */
export const confidenceStats = derived(
  inferenceJobStore,
  ($job) => calculateConfidenceStats($job.detectionResults)
);

/**
 * Whether job is active
 */
export const isJobActive = derived(
  inferenceJobStore,
  ($job) => $job.isDetecting
);

/**
 * Whether video manual session is active
 */
export const hasActiveVideoSession = derived(
  inferenceJobStore,
  ($job) => $job.activeVideoSession !== null
);

/**
 * Whether webcam session is active
 */
export const hasActiveWebcamSession = derived(
  inferenceJobStore,
  ($job) => $job.activeWebcamSession !== null
);

/**
 * Whether RTSP frame is ready for display
 */
export const rtspFrameReady = derived(
  inferenceJobStore,
  ($job) => $job.rtspFrameStatus === 'ready' && $job.rtspLastFrameData !== null
);

/**
 * Total detection count across all classes
 */
export const totalDetections = derived(
  inferenceJobStore,
  ($job) => $job.detectionResults.length
);

/**
 * Class count array (for charts/display)
 */
export const classCountArray = derived(
  inferenceJobStore,
  ($job) => {
    return Object.entries($job.classCounts)
      .map(([class_name, count]) => ({ class_name, count }))
      .sort((a, b) => b.count - a.count);
  }
);
