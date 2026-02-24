<script lang="ts">
  /**
   * BatchInferenceMode - Batch image inference component
   *
   * Extracted from capture page (Phase 2) to separate inference mode logic.
   * Handles batch image processing with background job polling.
   */

  import { onDestroy } from "svelte";
  import InferenceAPI from "../../../api/inference";
  import type {
    Model,
    PredictionJob,
    PredictionResult,
  } from "@/lib/types";
  import type { InferencePrompt, InferenceConfig } from "@/lib/types";
  import { drawInferenceResults } from "../../../utils/drawingUtils";
  import {
    processInferenceResponse,
    type ProcessedResults,
  } from "../../../utils/responseProcessor";
  import {
    MODEL_ERRORS,
    VALIDATION_ERRORS,
    INFERENCE_ERRORS,
    getErrorMessage,
  } from "../../../utils/errorMessages";

  // Phase 3: Store integration
  import { inferenceGalleryStore } from "../../../stores/inferenceGalleryStore";
  import { inferenceJobStore } from "../../../stores/inferenceJobStore";

  // Props
  let {
    selectedModelId,
    selectedModel = null,
    selectedFiles = [],
    confidence = 0.5,
    classFilter = [],
    inferPrompts = [],
    promptMode = "auto",
    promptRequired = false,
    campaignId = undefined,
    // Callbacks
    onJobUpdate = undefined,
    onGalleryUpdate = undefined,
    onDetectingChange = undefined,
    onError = undefined,
  }: {
    selectedModelId: number | null;
    selectedModel?: Model | null;
    selectedFiles?: File[];
    confidence?: number;
    classFilter?: string[];
    inferPrompts?: InferencePrompt[];
    promptMode?: "auto" | "text" | "point" | "box";
    promptRequired?: boolean;
    campaignId?: number;
    // Callbacks
    onJobUpdate?: ((job: PredictionJob) => void) | undefined;
    onGalleryUpdate?: ((images: any[]) => void) | undefined;
    onDetectingChange?: ((isDetecting: boolean) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
  } = $props();

  // Local state
  let isDetecting = $state(false);
  let currentJob: PredictionJob | null = $state(null);
  let pollingIntervalId: number | null = null;

  /**
   * Start batch image inference
   */
  export async function startInference() {
    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    if (selectedFiles.length === 0) {
      onError?.(new Error(VALIDATION_ERRORS.NO_FILES_SELECTED.message));
      return;
    }

    isDetecting = true;
    onDetectingChange?.(true);

    try {
      // Validate prompts if needed
      if (promptRequired) {
        if (promptMode !== "auto" && inferPrompts.length === 0) {
          const error = getErrorMessage(VALIDATION_ERRORS.PROMPTS_REQUIRED, {
            promptMode,
          });
          onError?.(new Error(error.message));
          isDetecting = false;
          onDetectingChange?.(false);
          return;
        }
      }

      const inferOptions: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        prompts: promptMode === "auto" ? [] : inferPrompts,
        campaignId: campaignId,
      };

      // Use unified inference API for batch
      currentJob = await InferenceAPI.inferBatch(selectedFiles, inferOptions);

      onJobUpdate?.(currentJob);

      // PHASE 3: Update store
      inferenceJobStore.startJob(currentJob);

      // Poll for job completion
      pollJobStatusForBatch();
    } catch (error) {
      console.error("Batch processing failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.BATCH_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
      throw error;
    }
  }

  /**
   * Poll job status until completion
   */
  function pollJobStatusForBatch() {
    pollingIntervalId = window.setInterval(async () => {
      if (!currentJob) return;

      try {
        const job = await InferenceAPI.getJob(currentJob.id);
        currentJob = job;
        onJobUpdate?.(job);

        if (job.status === "completed" || job.status === "failed") {
          if (pollingIntervalId !== null) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
          }

          // PHASE 3: Update store
          inferenceJobStore.completeJob();
          isDetecting = false;
          onDetectingChange?.(false);

          if (job.status === "completed") {
            // Fetch results and build gallery
            const results = await InferenceAPI.getResults(job.id, 0, 100);
            await buildGalleryFromResults(results);
          }
        }
      } catch (error) {
        console.error("Failed to poll job status:", error);
      }
    }, 2000);
  }

  /**
   * Build gallery from batch results
   */
  async function buildGalleryFromResults(results: PredictionResult[]) {
    const galleryImages: any[] = [];

    for (const result of results) {
      // Create canvas for each result
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;

      // Find the original file
      const originalFile = selectedFiles.find(
        (f) => f.name === result.file_name,
      );
      if (!originalFile) continue;

      const img = new Image();
      const imageUrl = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target?.result as string);
        reader.readAsDataURL(originalFile);
      });

      await new Promise<void>((resolve) => {
        img.onload = async () => {
          canvas.width = img.width;
          canvas.height = img.height;
          ctx.drawImage(img, 0, 0);

          // Use unified drawing utility
          drawInferenceResults(ctx, result, {
            showLabels: true,
            showConfidence: true,
          });

          resolve();
        };
        img.src = imageUrl;
      });

      galleryImages.push({
        original: imageUrl,
        annotated: canvas.toDataURL(),
        fileName: result.file_name,
        detectionData: result, // Use complete API response
      });
    }

    onGalleryUpdate?.(galleryImages);

    // PHASE 3: Also add to inferenceGalleryStore
    inferenceGalleryStore.reset();
    for (const img of galleryImages) {
      inferenceGalleryStore.addImage(img);
    }
    inferenceGalleryStore.navigate(0);
  }

  /**
   * Stop inference
   */
  export async function stopInference() {
    // Stop the backend job if running
    if (currentJob) {
      try {
        await InferenceAPI.stopJob(currentJob.id);
      } catch (error) {
        console.error("Failed to stop job on backend:", error);
      }
    }

    // Clear polling interval
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
      pollingIntervalId = null;
    }

    // Update local state
    isDetecting = false;
    onDetectingChange?.(false);

    // PHASE 3: Update store
    inferenceJobStore.completeJob();

    // Clear current job
    currentJob = null;
  }

  // Cleanup on component destroy
  onDestroy(() => {
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
    }
  });
</script>

<!-- No UI - this is a headless component that only handles logic -->
