/**
 * Canvas Store (Shared drawing utilities)
 * 
 * Manages canvas references, drawing options, zoom/pan state, prompt drawing mode,
 * and draw queue (from Phase 0 fix). Provides unified drawing interface for all
 * inference modes.
 * 
 * Centralizes canvas-related state for reuse across capture, workflow, and campaign pages.
 */

import { writable, derived, get } from 'svelte/store';
import { tick } from 'svelte';
import type { PredictionResponse } from '@/lib/types';
import {
  drawInferenceResults as utilDrawInferenceResults,
  drawInferenceResultsScaled as utilDrawInferenceResultsScaled,
  type DrawOptions,
} from '../utils/drawingUtils';

// ===========================
// Type Definitions
// ===========================

export type CanvasType = 'main' | 'overlay' | 'rtsp' | 'rtspOverlay';

export interface CanvasRefs {
  main: HTMLCanvasElement | null;
  overlay: HTMLCanvasElement | null;
  rtsp: HTMLCanvasElement | null;
  rtspOverlay: HTMLCanvasElement | null;
}

export interface CanvasState {
  // Canvas references (managed by components)
  canvases: CanvasRefs;
  
  // Drawing options (configurable)
  drawOptions: DrawOptions;
  
  // Zoom/Pan state
  zoomLevel: number;
  panOffset: { x: number; y: number };
  isPanning: boolean;
  panStart: { x: number; y: number };
  
  // Prompt drawing mode (SAM3)
  promptMode: 'auto' | 'text' | 'point' | 'box';
  isDrawingBox: boolean;
  boxStartCoords: { x: number; y: number } | null;
  tempBoxCoords: { x1: number; y1: number; x2: number; y2: number } | null;
  
  // Draw queue (Phase 0 fix for RS7+RS8)
  drawQueue: Array<() => void>;
  isDrawing: boolean;
  promptDrawPending: boolean;
}

// ===========================
// Default Values
// ===========================

const DEFAULT_STATE: CanvasState = {
  canvases: {
    main: null,
    overlay: null,
    rtsp: null,
    rtspOverlay: null,
  },
  drawOptions: {
    showLabels: true,
    showConfidence: true,
    lineWidth: 3,
    fontSize: 16,
    boxColor: '#E1604C',
    selectedClasses: undefined,
  },
  zoomLevel: 1,
  panOffset: { x: 0, y: 0 },
  isPanning: false,
  panStart: { x: 0, y: 0 },
  promptMode: 'auto',
  isDrawingBox: false,
  boxStartCoords: null,
  tempBoxCoords: null,
  drawQueue: [],
  isDrawing: false,
  promptDrawPending: false,
};

// ===========================
// Store Factory
// ===========================

function createCanvasStore() {
  const { subscribe, set, update } = writable<CanvasState>(DEFAULT_STATE);
  
  // ===========================
  // Helper Functions
  // ===========================
  
  /**
   * Process canvas draw queue with RAF throttling
   * (Phase 0 fix for RS7+RS8 race condition)
   */
  async function processCanvasQueue() {
    const state = get({ subscribe });
    
    if (state.isDrawing || state.drawQueue.length === 0) return;
    
    update(s => ({ ...s, isDrawing: true }));
    
    while (true) {
      const state = get({ subscribe });
      if (state.drawQueue.length === 0) break;
      
      const drawFn = state.drawQueue[0];
      update(s => ({ ...s, drawQueue: s.drawQueue.slice(1) }));
      
      drawFn();
      await tick();
    }
    
    update(s => ({ ...s, isDrawing: false }));
  }
  
  // ===========================
  // Public Methods
  // ===========================
  
  return {
    subscribe,
    
    // -------------------
    // Canvas Management
    // -------------------
    
    /**
     * Register a canvas element
     */
    setCanvas: (type: CanvasType, canvas: HTMLCanvasElement | null) => {
      update(state => ({
        ...state,
        canvases: { ...state.canvases, [type]: canvas },
      }));
    },
    
    /**
     * Get canvas context (with null check)
     */
    getContext: (type: CanvasType): CanvasRenderingContext2D | null => {
      const state = get({ subscribe });
      const canvas = state.canvases[type];
      return canvas ? canvas.getContext('2d') : null;
    },
    
    /**
     * Clear a canvas
     */
    clearCanvas: (type: CanvasType) => {
      const state = get({ subscribe });
      const canvas = state.canvases[type];
      
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
      }
    },
    
    /**
     * Resize a canvas
     */
    resizeCanvas: (type: CanvasType, width: number, height: number) => {
      const state = get({ subscribe });
      const canvas = state.canvases[type];
      
      if (canvas) {
        canvas.width = width;
        canvas.height = height;
      }
    },
    
    // -------------------
    // Drawing Operations
    // -------------------
    
    /**
     * Draw inference results on canvas (main orchestrator)
     */
    drawInference: (type: CanvasType, response: PredictionResponse) => {
      const state = get({ subscribe });
      const ctx = state.canvases[type]?.getContext('2d');
      
      if (!ctx) {
        console.warn(`Canvas ${type} not available for drawing`);
        return;
      }
      
      utilDrawInferenceResults(ctx, response, state.drawOptions);
    },
    
    /**
     * Draw inference results with scaling (for overlays)
     */
    drawInferenceScaled: (
      type: CanvasType,
      response: PredictionResponse,
      scaleX: number,
      scaleY: number
    ) => {
      const state = get({ subscribe });
      const ctx = state.canvases[type]?.getContext('2d');
      
      if (!ctx) {
        console.warn(`Canvas ${type} not available for drawing`);
        return;
      }
      
      utilDrawInferenceResultsScaled(ctx, response, scaleX, scaleY, state.drawOptions);
    },
    
    /**
     * Queue a draw operation (Phase 0 fix)
     */
    queueDraw: (drawFn: () => void) => {
      update(state => ({
        ...state,
        drawQueue: [...state.drawQueue, drawFn],
      }));
      
      processCanvasQueue();
    },
    
    /**
     * Queue a draw with RAF throttling (for prompts)
     */
    queueDrawThrottled: (drawFn: () => void) => {
      const state = get({ subscribe });
      
      if (!state.promptDrawPending) {
        update(s => ({ ...s, promptDrawPending: true }));
        
        requestAnimationFrame(() => {
          update(s => ({ ...s, promptDrawPending: false }));
          
          update(state => ({
            ...state,
            drawQueue: [...state.drawQueue, drawFn],
          }));
          
          processCanvasQueue();
        });
      }
    },
    
    // -------------------
    // Drawing Options
    // -------------------
    
    /**
     * Update drawing options
     */
    updateDrawOptions: (options: Partial<DrawOptions>) => {
      update(state => ({
        ...state,
        drawOptions: { ...state.drawOptions, ...options },
      }));
    },
    
    /**
     * Set selected classes filter
     */
    setSelectedClasses: (classes: Set<string>) => {
      update(state => ({
        ...state,
        drawOptions: {
          ...state.drawOptions,
          selectedClasses: classes.size > 0 ? classes : undefined,
        },
      }));
    },
    
    /**
     * Toggle a class in filter
     */
    toggleClass: (className: string) => {
      update(state => {
        const current = state.drawOptions.selectedClasses || new Set<string>();
        const newSet = new Set(current);
        
        if (newSet.has(className)) {
          newSet.delete(className);
        } else {
          newSet.add(className);
        }
        
        return {
          ...state,
          drawOptions: {
            ...state.drawOptions,
            selectedClasses: newSet.size > 0 ? newSet : undefined,
          },
        };
      });
    },
    
    // -------------------
    // Zoom/Pan Controls
    // -------------------
    
    /**
     * Set zoom level
     */
    setZoom: (level: number) => {
      update(state => ({ ...state, zoomLevel: Math.max(0.1, Math.min(5, level)) }));
    },
    
    /**
     * Zoom in
     */
    zoomIn: () => {
      update(state => ({
        ...state,
        zoomLevel: Math.min(5, state.zoomLevel + 0.25),
      }));
    },
    
    /**
     * Zoom out
     */
    zoomOut: () => {
      update(state => ({
        ...state,
        zoomLevel: Math.max(0.1, state.zoomLevel - 0.25),
      }));
    },
    
    /**
     * Reset zoom
     */
    resetZoom: () => {
      update(state => ({ ...state, zoomLevel: 1, panOffset: { x: 0, y: 0 } }));
    },
    
    /**
     * Set pan offset
     */
    setPan: (offset: { x: number; y: number }) => {
      update(state => ({ ...state, panOffset: offset }));
    },
    
    /**
     * Start panning
     */
    startPanning: (startPos: { x: number; y: number }) => {
      update(state => ({
        ...state,
        isPanning: true,
        panStart: startPos,
      }));
    },
    
    /**
     * Update pan during drag
     */
    updatePan: (currentPos: { x: number; y: number }) => {
      update(state => {
        if (!state.isPanning) return state;
        
        const dx = currentPos.x - state.panStart.x;
        const dy = currentPos.y - state.panStart.y;
        
        return {
          ...state,
          panOffset: {
            x: state.panOffset.x + dx,
            y: state.panOffset.y + dy,
          },
          panStart: currentPos,
        };
      });
    },
    
    /**
     * Stop panning
     */
    stopPanning: () => {
      update(state => ({ ...state, isPanning: false }));
    },
    
    // -------------------
    // Prompt Drawing (SAM3)
    // -------------------
    
    /**
     * Set prompt mode
     */
    setPromptMode: (mode: 'auto' | 'text' | 'point' | 'box') => {
      update(state => ({ ...state, promptMode: mode }));
    },
    
    /**
     * Start box drawing
     */
    startBoxDraw: (coords: { x: number; y: number }) => {
      update(state => ({
        ...state,
        isDrawingBox: true,
        boxStartCoords: coords,
        tempBoxCoords: null,
      }));
    },
    
    /**
     * Update box drawing
     */
    updateBoxDraw: (coords: { x: number; y: number }) => {
      update(state => {
        if (!state.isDrawingBox || !state.boxStartCoords) return state;
        
        return {
          ...state,
          tempBoxCoords: {
            x1: state.boxStartCoords.x,
            y1: state.boxStartCoords.y,
            x2: coords.x,
            y2: coords.y,
          },
        };
      });
    },
    
    /**
     * Finish box drawing and return coordinates
     */
    finishBoxDraw: (): { x1: number; y1: number; x2: number; y2: number } | null => {
      const state = get({ subscribe });
      const coords = state.tempBoxCoords;
      
      update(s => ({
        ...s,
        isDrawingBox: false,
        boxStartCoords: null,
        tempBoxCoords: null,
      }));
      
      return coords;
    },
    
    /**
     * Cancel box drawing
     */
    cancelBoxDraw: () => {
      update(state => ({
        ...state,
        isDrawingBox: false,
        boxStartCoords: null,
        tempBoxCoords: null,
      }));
    },
    
    // -------------------
    // Reset
    // -------------------
    
    /**
     * Reset all state (preserves canvas refs)
     */
    reset: () => {
      update(state => ({
        ...DEFAULT_STATE,
        canvases: state.canvases,  // Preserve canvas references
      }));
    },
  };
}

// ===========================
// Export Store Instance
// ===========================

export const canvasStore = createCanvasStore();

// ===========================
// Derived Stores
// ===========================

/**
 * Whether main canvas is available
 */
export const hasMainCanvas = derived(
  canvasStore,
  ($canvas) => $canvas.canvases.main !== null
);

/**
 * Whether overlay canvas is available
 */
export const hasOverlayCanvas = derived(
  canvasStore,
  ($canvas) => $canvas.canvases.overlay !== null
);

/**
 * Whether RTSP canvas is available
 */
export const hasRTSPCanvas = derived(
  canvasStore,
  ($canvas) => $canvas.canvases.rtsp !== null
);

/**
 * Whether can draw inference results
 */
export function canDrawInference(canvasType: CanvasType) {
  return derived(
    canvasStore,
    ($canvas) => $canvas.canvases[canvasType] !== null
  );
}

/**
 * Current zoom transform CSS
 */
export const zoomTransform = derived(
  canvasStore,
  ($canvas) => {
    return `scale(${$canvas.zoomLevel}) translate(${$canvas.panOffset.x}px, ${$canvas.panOffset.y}px)`;
  }
);

/**
 * Whether zoomed (not at default 1.0)
 */
export const isZoomed = derived(
  canvasStore,
  ($canvas) => $canvas.zoomLevel !== 1
);

/**
 * Whether panned (not at default 0,0)
 */
export const isPanned = derived(
  canvasStore,
  ($canvas) => $canvas.panOffset.x !== 0 || $canvas.panOffset.y !== 0
);

/**
 * Whether drawing box for SAM3 prompts
 */
export const isDrawingBox = derived(
  canvasStore,
  ($canvas) => $canvas.isDrawingBox
);

/**
 * Current box coordinates (while drawing)
 */
export const currentBoxCoords = derived(
  canvasStore,
  ($canvas) => $canvas.tempBoxCoords
);
