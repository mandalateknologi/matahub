/**
 * Inference Gallery Store (Generalized for reuse)
 * 
 * Manages gallery images, navigation, and view modes for capture pages.
 * Supports image/batch/video/webcam/RTSP modes with unified interface.
 * 
 * Replaces RS2 (gallery navigation) from capture page reactive statements.
 */

import { writable, derived } from 'svelte/store';
import type { GalleryImage } from '@/lib/types';

// ===========================
// Type Definitions
// ===========================

export interface InferenceGalleryState {
  // Gallery images (all modes)
  images: GalleryImage[];
  
  // Navigation
  currentIndex: number;
  selectedIndex: number;  // For display (may differ from current in some modes)
  
  // View modes
  webcamViewMode: 'live' | 'gallery';
  rtspViewMode: 'live' | 'gallery';
  videoViewMode: 'live' | 'gallery';  // For future use
}

// ===========================
// Default Values
// ===========================

const DEFAULT_STATE: InferenceGalleryState = {
  images: [],
  currentIndex: 0,
  selectedIndex: 0,
  webcamViewMode: 'live',
  rtspViewMode: 'live',
  videoViewMode: 'live',
};

// ===========================
// Store Factory
// ===========================

function createInferenceGalleryStore() {
  const { subscribe, set, update } = writable<InferenceGalleryState>(DEFAULT_STATE);
  
  return {
    subscribe,
    
    /**
     * Add a single image to gallery
     */
    addImage: (image: GalleryImage) => {
      update(state => {
        const newImages = [...state.images, image];
        return {
          ...state,
          images: newImages,
          currentIndex: newImages.length - 1,
          selectedIndex: newImages.length - 1,
        };
      });
    },
    
    /**
     * Add multiple images (batch mode)
     */
    addBatch: (images: GalleryImage[]) => {
      update(state => {
        const newImages = [...state.images, ...images];
        return {
          ...state,
          images: newImages,
          currentIndex: state.images.length,  // Point to first new image
          selectedIndex: state.images.length,
        };
      });
    },
    
    /**
     * Update image at specific index
     */
    updateImage: (index: number, updates: Partial<GalleryImage>) => {
      update(state => {
        if (index < 0 || index >= state.images.length) return state;
        
        const newImages = [...state.images];
        newImages[index] = { ...newImages[index], ...updates };
        
        return { ...state, images: newImages };
      });
    },
    
    /**
     * Navigate to specific index
     */
    navigate: (index: number) => {
      update(state => {
        if (index < 0 || index >= state.images.length) return state;
        
        return {
          ...state,
          currentIndex: index,
          selectedIndex: index,
        };
      });
    },
    
    /**
     * Navigate to next image
     */
    next: () => {
      update(state => {
        if (state.images.length === 0) return state;
        
        const nextIndex = (state.currentIndex + 1) % state.images.length;
        return {
          ...state,
          currentIndex: nextIndex,
          selectedIndex: nextIndex,
        };
      });
    },
    
    /**
     * Navigate to previous image
     */
    previous: () => {
      update(state => {
        if (state.images.length === 0) return state;
        
        const prevIndex = state.currentIndex === 0 
          ? state.images.length - 1 
          : state.currentIndex - 1;
        
        return {
          ...state,
          currentIndex: prevIndex,
          selectedIndex: prevIndex,
        };
      });
    },
    
    /**
     * Select image (for display, may differ from navigation)
     */
    select: (index: number) => {
      update(state => {
        if (index < 0 || index >= state.images.length) return state;
        return { ...state, selectedIndex: index };
      });
    },
    
    /**
     * Remove image at index
     */
    removeAt: (index: number) => {
      update(state => {
        if (index < 0 || index >= state.images.length) return state;
        
        const newImages = state.images.filter((_, i) => i !== index);
        const newCurrentIndex = Math.min(state.currentIndex, newImages.length - 1);
        const newSelectedIndex = Math.min(state.selectedIndex, newImages.length - 1);
        
        return {
          ...state,
          images: newImages,
          currentIndex: Math.max(0, newCurrentIndex),
          selectedIndex: Math.max(0, newSelectedIndex),
        };
      });
    },
    
    /**
     * Clear all images
     */
    clear: () => {
      update(state => ({
        ...state,
        images: [],
        currentIndex: 0,
        selectedIndex: 0,
      }));
    },
    
    /**
     * Set webcam view mode
     */
    setWebcamViewMode: (mode: 'live' | 'gallery') => {
      update(state => ({ ...state, webcamViewMode: mode }));
    },
    
    /**
     * Set RTSP view mode
     */
    setRTSPViewMode: (mode: 'live' | 'gallery') => {
      update(state => ({ ...state, rtspViewMode: mode }));
    },
    
    /**
     * Set video view mode
     */
    setVideoViewMode: (mode: 'live' | 'gallery') => {
      update(state => ({ ...state, videoViewMode: mode }));
    },
    
    /**
     * Toggle webcam view mode
     */
    toggleWebcamView: () => {
      update(state => ({
        ...state,
        webcamViewMode: state.webcamViewMode === 'live' ? 'gallery' : 'live',
      }));
    },
    
    /**
     * Toggle RTSP view mode
     */
    toggleRTSPView: () => {
      update(state => ({
        ...state,
        rtspViewMode: state.rtspViewMode === 'live' ? 'gallery' : 'live',
      }));
    },
    
    /**
     * Toggle video view mode
     */
    toggleVideoView: () => {
      update(state => ({
        ...state,
        videoViewMode: state.videoViewMode === 'live' ? 'gallery' : 'live',
      }));
    },
    
    /**
     * Reset to defaults
     */
    reset: () => {
      set(DEFAULT_STATE);
    },
  };
}

// ===========================
// Export Store Instance
// ===========================

export const inferenceGalleryStore = createInferenceGalleryStore();

// ===========================
// Derived Stores
// ===========================

/**
 * Current selected image
 */
export const currentImage = derived(
  inferenceGalleryStore,
  ($gallery) => {
    if ($gallery.images.length === 0) return null;
    return $gallery.images[$gallery.currentIndex] || null;
  }
);

/**
 * Selected image (for display)
 */
export const selectedImage = derived(
  inferenceGalleryStore,
  ($gallery) => {
    if ($gallery.images.length === 0) return null;
    return $gallery.images[$gallery.selectedIndex] || null;
  }
);

/**
 * Whether gallery has multiple images
 */
export const hasMultipleImages = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.length > 1
);

/**
 * Whether gallery is empty
 */
export const isGalleryEmpty = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.length === 0
);

/**
 * Gallery size
 */
export const gallerySize = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.length
);

/**
 * Whether can navigate next
 */
export const canNavigateNext = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.length > 0 && $gallery.currentIndex < $gallery.images.length - 1
);

/**
 * Whether can navigate previous
 */
export const canNavigatePrevious = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.length > 0 && $gallery.currentIndex > 0
);

/**
 * Navigation info (for display)
 */
export const navigationInfo = derived(
  inferenceGalleryStore,
  ($gallery) => ({
    current: $gallery.currentIndex + 1,
    total: $gallery.images.length,
    hasNext: $gallery.currentIndex < $gallery.images.length - 1,
    hasPrevious: $gallery.currentIndex > 0,
  })
);

/**
 * All images with detection data
 */
export const imagesWithDetections = derived(
  inferenceGalleryStore,
  ($gallery) => $gallery.images.filter(img => img.detectionData !== undefined)
);

/**
 * Total detections across all gallery images
 */
export const totalGalleryDetections = derived(
  imagesWithDetections,
  ($images) => {
    return $images.reduce((total, img) => {
      if (!img.detectionData) return total;
      
      // Count based on task type
      if (img.detectionData.class_names) {
        return total + img.detectionData.class_names.length;
      } else if (img.detectionData.top_class) {
        return total + 1;
      }
      
      return total;
    }, 0);
  }
);

/**
 * Class counts across all gallery images
 */
export const galleryClassCounts = derived(
  imagesWithDetections,
  ($images) => {
    const counts: Record<string, number> = {};
    
    $images.forEach(img => {
      if (!img.detectionData) return;
      
      // Detection/Segmentation
      if (img.detectionData.class_names) {
        img.detectionData.class_names.forEach(name => {
          counts[name] = (counts[name] || 0) + 1;
        });
      }
      
      // Classification
      if (img.detectionData.top_class) {
        const name = img.detectionData.top_class;
        counts[name] = (counts[name] || 0) + 1;
      }
    });
    
    return counts;
  }
);

/**
 * Available classes across all gallery images
 */
export const galleryAvailableClasses = derived(
  galleryClassCounts,
  ($counts) => Object.keys($counts).sort()
);
