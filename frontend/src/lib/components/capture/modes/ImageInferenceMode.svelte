<script lang="ts">
  /**
   * ImageInferenceMode - Single image inference component
   *
   * Extracted from capture page (Phase 2) to separate inference mode logic.
   * Handles single image detection with prompt support for both YOLO and SAM3 models.
   */

  import InferenceAPI from "../../../api/inference";
  import type { InferenceConfig, InferencePrompt } from "@/lib/types";
  import type { Model, PredictionResponse } from "@/lib/types";
  import { drawInferenceResultsToDataURL } from "../../../utils/drawingUtils";
  import {
    processInferenceResponse,
    type ProcessedResults,
    type FrameStats,
  } from "../../../utils/responseProcessor";
  import {
    MODEL_ERRORS,
    VALIDATION_ERRORS,
    INFERENCE_ERRORS,
    getErrorMessage,
  } from "../../../utils/errorMessages";

  // Props
  let {
    selectedModelId,
    selectedModel = null,
    selectedFile = null,
    imagePreview = null,
    confidence = 0.5,
    classFilter = [],
    inferPrompts = [],
    promptMode = "auto",
    promptRequired = false,
    campaignId = undefined,
    canvasElement = undefined,
    // Callbacks
    onDetectionComplete = undefined,
    onGalleryUpdate = undefined,
    onDetectingChange = undefined,
    onError = undefined,
  }: {
    selectedModelId: number | null;
    selectedModel?: Model | null;
    selectedFile?: File | null;
    imagePreview?: string | null;
    confidence?: number;
    classFilter?: string[];
    inferPrompts?: InferencePrompt[];
    promptMode?: "auto" | "text" | "point" | "box";
    promptRequired?: boolean;
    campaignId?: number;
    canvasElement?: HTMLCanvasElement;
    // Callbacks
    onDetectionComplete?: ((response: PredictionResponse) => void) | undefined;
    onGalleryUpdate?: ((images: any[]) => void) | undefined;
    onDetectingChange?: ((isDetecting: boolean) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
  } = $props();

  // Local state
  let isDetecting = $state(false);
  let detections: PredictionResponse | null = $state(null);

  /**
   * Start single image inference
   */
  export async function startInference() {
    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    if (!selectedFile) {
      onError?.(new Error(VALIDATION_ERRORS.NO_FILE_SELECTED.message));
      return;
    }

    isDetecting = true;
    onDetectingChange?.(true);

    try {
      // Validate prompts if needed (non-auto modes require prompts)
      if (
        promptRequired &&
        promptMode !== "auto" &&
        inferPrompts.length === 0
      ) {
        const error = getErrorMessage(VALIDATION_ERRORS.PROMPTS_REQUIRED, {
          promptMode,
        });
        onError?.(new Error(error.message));
        isDetecting = false;
        onDetectingChange?.(false);
        return;
      }

      // Build unified inference options
      const options: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        campaignId: campaignId,
        // Only include classFilter if it has values
        ...(classFilter && classFilter.length > 0 && { classFilter }),
        // Include prompts for models that need prompts (auto mode uses empty array)
        ...(promptRequired && {
          prompts: promptMode === "auto" ? [] : inferPrompts,
        }),
      };

      console.log("Starting single image inference with options:", classFilter);

      // Single unified API call for all supported model types
      const response = await InferenceAPI.inferSingle(selectedFile, options);

      // Use response directly - API already provides complete structure
      detections = response;

      // Notify parent with raw response
      onDetectionComplete?.(response);

      // Create annotated image - first load imagePreview into Image element
      const img = new Image();
      img.src = imagePreview!;
      await new Promise((resolve) => (img.onload = resolve));

      const annotatedImage = await drawInferenceResultsToDataURL(
        img,
        response,
        {
          showLabels: true,
          showConfidence: true,
        },
      );

      // Add to gallery with detection data
      const galleryEntry = {
        original: imagePreview!,
        annotated: annotatedImage,
        fileName: selectedFile.name,
        detectionData: detections,
      };

      onGalleryUpdate?.([galleryEntry]);
    } catch (error) {
      console.error("Single image detection failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.SINGLE_IMAGE_FAILED.message),
      );
      throw error;
    } finally {
      isDetecting = false;
      onDetectingChange?.(false);
    }
  }

  /**
   * Stop inference (no-op for single image, but exposed for consistency)
   */
  export function stopInference() {
    isDetecting = false;
    onDetectingChange?.(false);
  }
</script>

<!-- No UI - this is a headless component that only handles logic -->
