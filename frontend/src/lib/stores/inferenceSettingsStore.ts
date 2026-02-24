/**
 * Inference Settings Store (Generalized for reuse)
 * 
 * Manages model selection, detection settings (confidence, classFilter, skipFrames),
 * and prompt settings (promptMode, inferPrompts) with localStorage persistence.
 * 
 * Replaces RS5 (smart settings auto-save) and RS6 (prompt settings auto-save)
 * from capture page reactive statements.
 */

import { writable, derived, get } from 'svelte/store';
import type { Model } from '@/lib/types';
import type { InferencePrompt } from '@/lib/types';

// ===========================
// Type Definitions
// ===========================

export interface InferenceSettings {
  // Model Selection
  selectedModelId: number | null;
  selectedModel: Model | null;
  
  // Detection Settings (persisted per model)
  confidence: number;
  classFilter: string[];
  skipFrames: number;
  
  // Prompt Settings (persisted per model)
  promptMode: 'auto' | 'text' | 'point' | 'box';
  inferPrompts: InferencePrompt[];
  textPrompt: string;
  
  // UI State (not persisted)
  isTipsCollapsed: boolean;
}

interface StoredSmartSettings {
  confidence: number;
  classFilter: string[];
  skipFrames: number;
}

interface StoredPromptSettings {
  promptMode: 'auto' | 'text' | 'point' | 'box';
  prompts: InferencePrompt[];
}

// ===========================
// Default Values
// ===========================

/**
 * Load last selected model ID from localStorage
 */
function loadLastSelectedModelId(): number | null {
  try {
    const stored = localStorage.getItem('last_selected_model_id');
    return stored ? parseInt(stored, 10) : null;
  } catch {
    return null;
  }
}

/**
 * Save last selected model ID to localStorage
 */
function saveLastSelectedModelId(modelId: number | null): void {
  try {
    if (modelId) {
      localStorage.setItem('last_selected_model_id', modelId.toString());
    } else {
      localStorage.removeItem('last_selected_model_id');
    }
  } catch (error) {
    console.warn('Failed to save last selected model ID:', error);
  }
}

const DEFAULT_SETTINGS: InferenceSettings = {
  selectedModelId: loadLastSelectedModelId(), // Restore from localStorage
  selectedModel: null,
  confidence: 0.5,
  classFilter: [],
  skipFrames: 5,
  promptMode: 'auto',
  inferPrompts: [],
  textPrompt: '',
  isTipsCollapsed: false,
};

// ===========================
// Store Factory
// ===========================

function createInferenceSettingsStore() {
  const { subscribe, set, update } = writable<InferenceSettings>(DEFAULT_SETTINGS);
  
  // Debounce timer for smart settings save
  let settingsSaveTimer: number | null = null;
  
  // ===========================
  // Helper Functions
  // ===========================
  
  /**
   * Load smart settings from localStorage for a specific model
   */
  function loadSmartSettings(modelId: number): StoredSmartSettings {
    const key = `smart_settings_${modelId}`;
    const stored = localStorage.getItem(key);
    
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return {
          confidence: parsed.confidence ?? DEFAULT_SETTINGS.confidence,
          classFilter: parsed.classFilter ?? DEFAULT_SETTINGS.classFilter,
          skipFrames: parsed.skipFrames ?? DEFAULT_SETTINGS.skipFrames,
        };
      } catch (error) {
        console.warn(`Failed to parse smart settings for model ${modelId}:`, error);
      }
    }
    
    return {
      confidence: DEFAULT_SETTINGS.confidence,
      classFilter: DEFAULT_SETTINGS.classFilter,
      skipFrames: DEFAULT_SETTINGS.skipFrames,
    };
  }
  
  /**
   * Save smart settings to localStorage (called by debounced method)
   */
  function saveSmartSettingsImmediate(modelId: number, settings: StoredSmartSettings): void {
    const key = `smart_settings_${modelId}`;
    localStorage.setItem(key, JSON.stringify(settings));
  }
  
  /**
   * Load prompt settings from localStorage for a specific model
   */
  function loadPromptSettings(modelId: number): StoredPromptSettings {
    const key = `atvision_prompts_model_${modelId}`;
    const stored = localStorage.getItem(key);
    
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        return {
          promptMode: parsed.promptMode ?? DEFAULT_SETTINGS.promptMode,
          prompts: parsed.prompts ?? DEFAULT_SETTINGS.inferPrompts,
        };
      } catch (error) {
        console.warn(`Failed to parse prompt settings for model ${modelId}:`, error);
      }
    }
    
    return {
      promptMode: DEFAULT_SETTINGS.promptMode,
      prompts: DEFAULT_SETTINGS.inferPrompts,
    };
  }
  
  /**
   * Save prompt settings to localStorage (immediate, no debounce)
   */
  function savePromptSettingsImmediate(modelId: number, settings: StoredPromptSettings): void {
    const key = `atvision_prompts_model_${modelId}`;
    localStorage.setItem(key, JSON.stringify(settings));
  }
  
  // ===========================
  // Public Methods
  // ===========================
  
  return {
    subscribe,
    
    /**
     * Select a model and load its saved settings
     */
    selectModel: (model: Model | null) => {
      console.log('[inferenceSettingsStore] selectModel called with:', model?.name, 'id:', model?.id);
      
      // Persist selected model ID to localStorage
      saveLastSelectedModelId(model?.id ?? null);
      
      update(state => {
        const newState = {
          ...state,
          selectedModelId: model?.id ?? null,
          selectedModel: model,
        };
        
        console.log('[inferenceSettingsStore] selectModel updating to selectedModelId:', newState.selectedModelId);
        
        // Load settings for new model
        if (model) {
          const smartSettings = loadSmartSettings(model.id);
          const promptSettings = loadPromptSettings(model.id);
          
          newState.confidence = smartSettings.confidence;
          newState.classFilter = smartSettings.classFilter;
          newState.skipFrames = smartSettings.skipFrames;
          newState.promptMode = promptSettings.promptMode;
          newState.inferPrompts = promptSettings.prompts;
          
          console.log('[inferenceSettingsStore] Loaded skipFrames from localStorage:', newState.skipFrames);
        } else {
          // Reset to defaults when no model selected
          newState.confidence = DEFAULT_SETTINGS.confidence;
          newState.classFilter = DEFAULT_SETTINGS.classFilter;
          newState.skipFrames = DEFAULT_SETTINGS.skipFrames;
          newState.promptMode = DEFAULT_SETTINGS.promptMode;
          newState.inferPrompts = DEFAULT_SETTINGS.inferPrompts;
        }
        
        return newState;
      });
    },
    
    /**
     * Update confidence threshold
     * Triggers debounced save
     */
    setConfidence: (confidence: number) => {
      update(state => ({ ...state, confidence }));
      
      // Debounced save (300ms)
      const currentState = get({ subscribe });
      if (currentState.selectedModelId) {
        if (settingsSaveTimer) clearTimeout(settingsSaveTimer);
        
        settingsSaveTimer = window.setTimeout(() => {
          const state = get({ subscribe });
          if (state.selectedModelId) {
            saveSmartSettingsImmediate(state.selectedModelId, {
              confidence: state.confidence,
              classFilter: state.classFilter,
              skipFrames: state.skipFrames,
            });
          }
          settingsSaveTimer = null;
        }, 300);
      }
    },
    
    /**
     * Update class filter
     * Triggers debounced save
     */
    setClassFilter: (classFilter: string[]) => {
      console.log('[inferenceSettingsStore] setClassFilter called:', classFilter);
      update(state => ({ ...state, classFilter }));
      
      // Debounced save (300ms)
      const currentState = get({ subscribe });
      if (currentState.selectedModelId) {
        if (settingsSaveTimer) clearTimeout(settingsSaveTimer);
        
        settingsSaveTimer = window.setTimeout(() => {
          const state = get({ subscribe });
          if (state.selectedModelId) {
            console.log('[inferenceSettingsStore] Saving to localStorage:', state.classFilter);
            saveSmartSettingsImmediate(state.selectedModelId, {
              confidence: state.confidence,
              classFilter: state.classFilter,
              skipFrames: state.skipFrames,
            });
          }
          settingsSaveTimer = null;
        }, 300);
      }
    },
    
    /**
     * Update skip frames count
     * Triggers debounced save
     */
    setSkipFrames: (skipFrames: number) => {
      update(state => ({ ...state, skipFrames }));
      
      // Debounced save (300ms)
      const currentState = get({ subscribe });
      if (currentState.selectedModelId) {
        if (settingsSaveTimer) clearTimeout(settingsSaveTimer);
        
        settingsSaveTimer = window.setTimeout(() => {
          const state = get({ subscribe });
          if (state.selectedModelId) {
            saveSmartSettingsImmediate(state.selectedModelId, {
              confidence: state.confidence,
              classFilter: state.classFilter,
              skipFrames: state.skipFrames,
            });
          }
          settingsSaveTimer = null;
        }, 300);
      }
    },
    
    /**
     * Update prompt mode
     * Triggers immediate save (no debounce)
     */
    setPromptMode: (promptMode: 'auto' | 'text' | 'point' | 'box') => {
      console.log('[inferenceSettingsStore] setPromptMode called:', promptMode);
      update(state => ({ ...state, promptMode }));
      
      // Immediate save
      const currentState = get({ subscribe });
      console.log('[inferenceSettingsStore] Current state after update:', currentState.promptMode);
      if (currentState.selectedModelId) {
        savePromptSettingsImmediate(currentState.selectedModelId, {
          promptMode,
          prompts: currentState.inferPrompts,
        });
      }
    },
    
    /**
     * Update inference prompts
     * Triggers immediate save (no debounce)
     */
    setInferPrompts: (inferPrompts: InferencePrompt[]) => {
      update(state => ({ ...state, inferPrompts }));
      
      // Immediate save
      const currentState = get({ subscribe });
      if (currentState.selectedModelId) {
        savePromptSettingsImmediate(currentState.selectedModelId, {
          promptMode: currentState.promptMode,
          prompts: inferPrompts,
        });
      }
    },
    
    /**
     * Update text prompt (UI state, not persisted separately)
     */
    setTextPrompt: (textPrompt: string) => {
      update(state => ({ ...state, textPrompt }));
    },
    
    /**
     * Toggle tips collapse state
     */
    toggleTips: () => {
      update(state => ({ ...state, isTipsCollapsed: !state.isTipsCollapsed }));
    },
    
    /**
     * Reset to defaults (for new capture session)
     */
    reset: () => {
      if (settingsSaveTimer) {
        clearTimeout(settingsSaveTimer);
        settingsSaveTimer = null;
      }
      set(DEFAULT_SETTINGS);
    },
  };
}

// ===========================
// Export Store Instance
// ===========================

export const inferenceSettingsStore = createInferenceSettingsStore();

// ===========================
// Derived Stores
// ===========================

/**
 * Whether the selected model requires prompts (SAM3, future prompt-capable models)
 */
export const requiresPrompts = derived(
  inferenceSettingsStore,
  ($settings) => {
    if (!$settings.selectedModel) return false;
    
    // Check requires_prompts field first (new models)
    if ($settings.selectedModel.requires_prompts !== undefined) {
      return $settings.selectedModel.requires_prompts;
    }
    
    // Fallback: Check if model is SAM3 (backward compatibility)
    return (
      $settings.selectedModel.base_type === 'sam3' ||
      $settings.selectedModel.task_type === 'sam3' ||
      $settings.selectedModel.inference_type === 'sam3'
    );
  }
);

/**
 * Effective prompt mode (auto-switches to "text" for RTSP)
 * Accepts sourceType as parameter for reactivity
 */
export function effectivePromptMode(sourceType: string) {
  return derived(
    inferenceSettingsStore,
    ($settings) => {
      // Force "text" mode for RTSP (RS4 behavior)
      if (sourceType === 'rtsp' && $settings.promptMode === 'auto') {
        return 'text';
      }
      return $settings.promptMode;
    }
  );
}

/**
 * Whether model is selected and ready
 */
export const modelReady = derived(
  inferenceSettingsStore,
  ($settings) => $settings.selectedModelId !== null && $settings.selectedModel !== null
);

/**
 * Current smart settings (for display/export)
 */
export const smartSettings = derived(
  inferenceSettingsStore,
  ($settings) => ({
    confidence: $settings.confidence,
    classFilter: $settings.classFilter,
    skipFrames: $settings.skipFrames,
  })
);

/**
 * Current prompt settings (for display/export)
 */
export const promptSettings = derived(
  inferenceSettingsStore,
  ($settings) => ({
    promptMode: $settings.promptMode,
    inferPrompts: $settings.inferPrompts,
    textPrompt: $settings.textPrompt,
  })
);
