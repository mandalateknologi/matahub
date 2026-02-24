<script lang="ts">
  /**
   * RTSPInferenceMode - RTSP stream inference component
   *
   * Extracted from capture page (Phase 2) to separate inference mode logic.
   * Handles RTSP stream URLs with both continuous and manual capture modes.
   * Integrates RTSPViewer for prompt-required models, uses standard API for others.
   */

  import { onDestroy } from "svelte";
  import InferenceAPI from "../../../api/inference";
  import type {
    Model,
    PredictionJob,
    PredictionResponse,
  } from "@/lib/types";
  import type { InferencePrompt, InferenceConfig } from "@/lib/types";
  import RTSPViewer from "../../../components/visionmask/RTSPViewer.svelte";

  import {
    drawPolygonMask,
    drawBoundingBox,
    type DrawOptions,
  } from "../../../utils/drawingUtils";
  import {
    processInferenceResponse,
    type ProcessedResults,
  } from "../../../utils/responseProcessor";
  import {
    MODEL_ERRORS,
    VALIDATION_ERRORS,
    INFERENCE_ERRORS,
    SESSION_ERRORS,
  } from "../../../utils/errorMessages";
  import { inferenceJobStore } from "../../../stores/inferenceJobStore";

  // Props
  let {
    selectedModelId,
    selectedModel = null,
    rtspUrl = "",
    confidence = 0.5,
    classFilter = [],
    inferPrompts = [],
    promptRequired = false,
    captureMode = "manual",
    campaignId = undefined,
    canvasElement = undefined,
    canvasOverlay = undefined,
    skipFrames = undefined,
    // Callbacks
    onSessionStart = undefined,
    onFrameCaptured = undefined,
    onJobUpdate = undefined,
    onGalleryUpdate = undefined,
    onStatsUpdate = undefined,
    onDetectingChange = undefined,
    onError = undefined,
    onFlash = undefined,
    onShutterSound = undefined,
  }: {
    selectedModelId: number | null;
    selectedModel?: Model | null;
    rtspUrl?: string;
    confidence?: number;
    classFilter?: string[];
    inferPrompts?: InferencePrompt[];
    promptRequired?: boolean;
    captureMode?: "manual" | "continuous";
    skipFrames?: number | undefined;
    campaignId?: number;
    canvasElement?: HTMLCanvasElement;
    canvasOverlay?: HTMLCanvasElement;
    // Callbacks
    onSessionStart?: ((session: PredictionJob) => void) | undefined;
    onFrameCaptured?: (() => void) | undefined;
    onJobUpdate?: ((job: PredictionJob) => void) | undefined;
    onGalleryUpdate?: ((images: any[]) => void) | undefined;
    onStatsUpdate?: ((stats: ProcessedResults) => void) | undefined;
    onDetectingChange?: ((isDetecting: boolean) => void) | undefined;
    onFlash?: (() => void) | undefined;
    onShutterSound?: (() => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
  } = $props();

  // Local state
  let isDetecting = $derived($inferenceJobStore.isDetecting);
  let rtspViewerRef: any = $state(null);
  let activeSession: PredictionJob | null = null;
  let galleryImages: any[] = [];
  let processedFrameNumbers = new Set<number>();

  // Interval IDs
  let pollingIntervalId: number | null = null;

  /**
   * Start RTSP inference
   */
  export async function startInference() {
    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    if (!rtspUrl) {
      onError?.(new Error(VALIDATION_ERRORS.NO_RTSP_URL.message));
      return;
    }

    // Validate prompts if required
    if (promptRequired && inferPrompts.length === 0) {
      onError?.(new Error(VALIDATION_ERRORS.PROMPTS_REQUIRED.message));
      return;
    }

    onDetectingChange?.(true);

    try {
      if (promptRequired) {
        // Use RTSPViewer for prompt-required models
        await startRTSPViewerMode();
      } else {
        // Use standard API for models without prompts
        if (captureMode === "continuous") {
          await startContinuousRTSPDetection();
        } else {
          await startRTSPDetectionSession();
        }
      }
    } catch (error) {
      console.error("RTSP inference failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.RTSP_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
    }
  }

  /**
   * Start RTSP viewer mode (for prompt-required models)
   */
  async function startRTSPViewerMode() {
    // RTSPViewer handles its own session and frame processing
    // We just need to set up callbacks and let it run
    console.log("Starting RTSP viewer mode with prompts");
  }

  /**
   * Start continuous RTSP detection (backend processing)
   */
  async function startContinuousRTSPDetection() {
    if (!rtspUrl || !selectedModelId) return;

    try {
      // Build API options
      const options: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        campaignId: campaignId,
      };

      // Start RTSP detection job
      const job = await InferenceAPI.inferRTSP(
        rtspUrl,
        options,
        captureMode,
        skipFrames,
      );

      if (job) {
        console.log(`Started RTSP detection job with ID: ${job.id}`);
        activeSession = job;
        onJobUpdate?.(job);
        onSessionStart?.(job);
        pollJobStatus(job.id);
      } else {
        console.error("Failed to start RTSP detection job.");
        onError?.(new Error(INFERENCE_ERRORS.RTSP_JOB_START_FAILED.message));
      }
    } catch (error) {
      console.error("Continuous RTSP detection failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.RTSP_FAILED.message),
      );

      onDetectingChange?.(false);
    }
  }

  /**
   * Start RTSP detection session (manual mode)
   */
  async function startRTSPDetectionSession() {
    if (!rtspUrl || !selectedModelId) return;

    try {
      // Build API options
      const options: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        campaignId: campaignId,
      };

      // Start RTSP session
      const session = await InferenceAPI.inferRTSP(
        rtspUrl,
        options,
        captureMode,
        skipFrames,
      );

      if (session) {
        console.log(`Started RTSP session with ID: ${session.id}`);
        activeSession = session;
        onSessionStart?.(session);

        // Poll for frames
        pollRTSPFrames(session.id);
      } else {
        console.error("Failed to start RTSP session.");
        onError?.(new Error(SESSION_ERRORS.RTSP_SESSION_START_FAILED.message));
      }
    } catch (error) {
      console.error("RTSP session start failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(SESSION_ERRORS.RTSP_SESSION_START_FAILED.message),
      );
      onDetectingChange?.(false);
    }
  }

  /**
   * Poll job status for continuous mode
   * Incrementally fetches results as they become available (like VideoInferenceMode)
   */
  function pollJobStatus(jobId: number) {
    let lastFetchedCount = 0;
    let processedResultIds = new Set<number>();

    pollingIntervalId = window.setInterval(async () => {
      try {
        const job: PredictionJob = await InferenceAPI.getJob(jobId);
        onJobUpdate?.(job);

        // Check for completion
        const isComplete =
          job.status === "completed" || job.status === "failed";

        // Fetch new results as they become available (incremental loading)
        if (job.results_count && job.results_count > lastFetchedCount) {
          const skip = lastFetchedCount;
          const limit = job.results_count - lastFetchedCount;

          try {
            const newResults = await InferenceAPI.getResults(
              jobId,
              skip,
              limit,
            );
            console.log(
              `[RTSP pollJobStatus] Fetched ${newResults.length} new results (${skip + 1}-${skip + newResults.length} of ${job.results_count})`,
            );

            // Process new frames and add to gallery with deduplication
            for (const result of newResults) {
              // Skip if already processed (prevents duplicates)
              if (processedResultIds.has(result.id || 0)) {
                console.log(`[RTSP] Skipping duplicate result ID ${result.id}`);
                continue;
              }

              processedResultIds.add(result.id || 0);

              // Add to gallery if not already present
              if (
                !galleryImages.some(
                  (img) => img.detectionData?.id === result.id,
                )
              ) {
                try {
                  await updateGalleryFromResults([result]);
                } catch (frameError) {
                  console.error(
                    `[RTSP] Failed to add frame ${result.frame_number}:`,
                    frameError,
                  );
                  // Continue processing other frames even if one fails
                }
              }
            }

            lastFetchedCount = job.results_count;
          } catch (error) {
            console.error("[RTSP] Error fetching results:", error);
            // Still update lastFetchedCount to avoid infinite loop
            lastFetchedCount = job.results_count;
          }
        }

        // Handle job completion
        if (isComplete) {
          console.log(
            "[RTSP pollJobStatus] Job complete detected, clearing interval and updating state",
          );
          if (pollingIntervalId !== null) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
          }

          onDetectingChange?.(false);

          // Fetch any remaining results before finishing
          if (
            job.status === "completed" &&
            job.results_count &&
            job.results_count > lastFetchedCount
          ) {
            const remainingResults = await InferenceAPI.getResults(
              jobId,
              lastFetchedCount,
              job.results_count - lastFetchedCount,
            );

            for (const result of remainingResults) {
              if (!processedResultIds.has(result.id || 0)) {
                processedResultIds.add(result.id || 0);
                try {
                  await updateGalleryFromResults([result]);
                } catch (frameError) {
                  console.error(
                    `[RTSP] Failed to add remaining frame ${result.frame_number}:`,
                    frameError,
                  );
                }
              }
            }
          }

          // Show completion message and emit final stats
          if (job.status === "completed") {
            console.log(
              `[RTSP] Processing completed. Total frames: ${job.results_count || 0}, Gallery images: ${galleryImages.length}`,
            );

            // Emit final stats from last gallery image if available
            if (galleryImages.length > 0) {
              const lastImage = galleryImages[galleryImages.length - 1];
              if (lastImage.detectionData) {
                const processed = processInferenceResponse(
                  lastImage.detectionData,
                );
                onStatsUpdate?.(processed);
              }
            }
          } else {
            console.error(`[RTSP] Job failed with status: ${job.status}`);
            onError?.(new Error(INFERENCE_ERRORS.RTSP_JOB_FAILED.message));
          }
        }
      } catch (error) {
        console.error("[RTSP] Failed to poll job status:", error);
        if (pollingIntervalId !== null) {
          clearInterval(pollingIntervalId);
          pollingIntervalId = null;
        }
        onDetectingChange?.(false);
      }
    }, 2000); // Poll every 2 seconds
  }

  /**
   * Poll RTSP frames for manual mode (live preview only)
   */
  function pollRTSPFrames(sessionId: number) {
    pollingIntervalId = window.setInterval(async () => {
      try {
        // Get latest frame for live preview
        const result = await InferenceAPI.rtsp_get_latest_frame(sessionId);
        if (result) {
          console.log(
            "[RTSP pollRTSPFrames] Fetched latest frame for live preview",
          );
          console.log("[RTSP pollRTSPFrames] canvasElement:", canvasElement);
          console.log("[RTSP pollRTSPFrames] canvasOverlay:", canvasOverlay);

          // result contains: { frame: base64_image, predictions: PredictionResponse }
          const { frame, predictions } = result;

          // Display live frame on both canvases
          const img = new Image();
          img.onload = () => {
            console.log(
              "[RTSP pollRTSPFrames] Image loaded, dimensions:",
              img.width,
              "x",
              img.height,
            );

            // Draw on main canvas
            if (canvasElement) {
              console.log("[RTSP pollRTSPFrames] Drawing to canvasElement");
              const ctx = canvasElement.getContext("2d");
              if (ctx) {
                canvasElement.width = img.width;
                canvasElement.height = img.height;
                ctx.drawImage(img, 0, 0);
                console.log("[RTSP pollRTSPFrames] Drew image to main canvas");
              } else {
                console.error(
                  "[RTSP pollRTSPFrames] Failed to get 2D context for canvasElement",
                );
              }
            } else {
              console.error(
                "[RTSP pollRTSPFrames] canvasElement is undefined!",
              );
            }

            // Draw detections on overlay canvas
            const ctx = canvasOverlay?.getContext("2d");
            if (ctx && canvasOverlay) {
              canvasOverlay.width = img.width;
              canvasOverlay.height = img.height;
              ctx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);

              // Draw detections on live preview (if predictions exist)
              if (predictions) {
                if (predictions.boxes && predictions.boxes.length > 0) {
                  predictions.boxes.forEach((box: number[], i: number) => {
                    const score = predictions.scores?.[i] || 0;
                    const className = predictions.class_names?.[i] || "";
                    const drawOptions: DrawOptions = {
                      showLabels: true,
                      showConfidence: true,
                    };
                    drawBoundingBox(ctx, box, className, score, drawOptions);
                  });
                }

                // Draw masks on live preview
                if (predictions.masks && predictions.masks.length > 0) {
                  predictions.masks.forEach((mask: any, i: number) => {
                    if (mask.polygon) {
                      drawPolygonMask(ctx, mask.polygon, i);
                    }
                  });
                }

                // Update stats with live detections
                const processed = processInferenceResponse(predictions);
                onStatsUpdate?.(processed);
              }
            }
          };
          img.src = frame; // Use base64 frame directly
        }
      } catch (error) {
        console.error("Failed to poll RTSP frames:", error);
      }
    }, 1000); // Poll every second for manual mode
  }

  /**
   * Update gallery from results (continuous mode)
   * Fetches frame images via InferenceAPI.getResultImage for each result
   */
  async function updateGalleryFromResults(results: any[]) {
    console.log(
      `[RTSP updateGalleryFromResults] Processing ${results.length} results`,
    );

    for (const result of results) {
      const frameNumber = result.frame_number || 0;
      const resultId = result.id || 0;

      // Skip if already processed (duplicate prevention)
      if (processedFrameNumbers.has(frameNumber)) {
        console.log(`[RTSP] Skipping duplicate frame ${frameNumber}`);
        continue;
      }

      processedFrameNumbers.add(frameNumber);

      try {
        // CRITICAL: Fetch frame image via authenticated endpoint
        const frameResponse = await InferenceAPI.getResultImage(resultId);
        const frameBlob = frameResponse.data;
        const frameUrl = URL.createObjectURL(frameBlob);

        // Load frame image
        const img = new Image();
        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = frameUrl;
        });

        // Store original frame (before annotations)
        const originalFrame = frameUrl;

        // Create canvas for annotations
        const annotatedCanvas = document.createElement("canvas");
        annotatedCanvas.width = img.width;
        annotatedCanvas.height = img.height;
        const ctx = annotatedCanvas.getContext("2d");
        if (!ctx) {
          console.error(
            `[RTSP] Failed to get canvas context for frame ${frameNumber}`,
          );
          continue;
        }

        // Draw original image
        ctx.drawImage(img, 0, 0);

        // Draw bounding boxes
        if (result.boxes && result.boxes.length > 0) {
          result.boxes.forEach((box: number[], i: number) => {
            const score = result.scores?.[i] || 0;
            const className = result.class_names?.[i] || "";
            const drawOptions: DrawOptions = {
              showLabels: true,
              showConfidence: true,
            };
            drawBoundingBox(ctx, box, className, score, drawOptions);
          });
        }

        // Draw polygon masks
        if (result.masks && result.masks.length > 0) {
          result.masks.forEach((mask: any, i: number) => {
            if (mask.polygon) {
              drawPolygonMask(ctx, mask.polygon, i);
            }
          });
        }

        // Capture annotated frame
        const annotatedFrame = annotatedCanvas.toDataURL();

        const fileName = result.file_name || `rtsp_frame_${frameNumber}.jpg`;
        const galleryEntry = {
          original: originalFrame,
          annotated: annotatedFrame,
          fileName: fileName,
          detectionData: result,
        };

        // Add to gallery (prepend for newest-first order)
        galleryImages = [galleryEntry, ...galleryImages];
        console.log(
          `[RTSP] Added frame ${frameNumber} to gallery. Total images: ${galleryImages.length}`,
        );

        // CRITICAL: Emit callbacks for each frame
        onGalleryUpdate?.(galleryImages);

        // Emit stats for THIS frame (updates main preview)
        const processed = processInferenceResponse(result);
        onStatsUpdate?.(processed);
        console.log(
          `[RTSP] Emitted stats for frame ${frameNumber}: ${result.boxes?.length || 0} detections`,
        );
      } catch (error) {
        console.error(`[RTSP] Failed to process frame ${frameNumber}:`, error);
        // Continue processing other frames
      }
    }

    console.log(
      `[RTSP updateGalleryFromResults] Finished. Final gallery size: ${galleryImages.length}`,
    );
  }

  /**
   * Capture current RTSP frame (manual mode only)
   */
  export async function captureFrame() {
    if (!activeSession) {
      onError?.(new Error(SESSION_ERRORS.NO_ACTIVE_SESSION.message));
      return;
    }

    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    // Trigger flash animation and shutter sound
    onFlash?.();
    onShutterSound?.();

    try {
      const frameNumber = galleryImages.length + 1;

      const inferOptions: InferenceConfig = {
        modelId: 0, // Model ID is not needed for RTSP capture (already in job context)
        prompts: inferPrompts,
        campaignId: campaignId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
      };

      // Capture frame from RTSP stream
      const response = await InferenceAPI.rtsp_capture_frame(
        activeSession.id,
        inferOptions,
      );

      // Process and add to gallery
      if (response && response.id) {
        // Fetch the actual frame image via API
        const frameResponse = await InferenceAPI.getResultImage(response.id);
        const frameBlob = frameResponse.data;
        const frameUrl = URL.createObjectURL(frameBlob);

        // Create canvas for annotation
        const canvas = document.createElement("canvas");
        const img = new Image();

        await new Promise((resolve, reject) => {
          img.onload = resolve;
          img.onerror = reject;
          img.src = frameUrl;
        });

        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0);

          // Draw detections
          if (response.boxes && response.boxes.length > 0) {
            response.boxes.forEach((box, i) => {
              const score = response.scores?.[i] || 0;
              const className = response.class_names?.[i] || "";
              const drawOptions: DrawOptions = {
                showLabels: true,
                showConfidence: true,
              };

              drawBoundingBox(ctx, box, className, score, drawOptions);
            });
          }

          // Draw masks
          if (response.masks && response.masks.length > 0) {
            response.masks.forEach((mask, i) => {
              if (mask.polygon) {
                drawPolygonMask(ctx, mask.polygon, i);
              }
            });
          }
        }

        const galleryEntry = {
          original: frameUrl,
          annotated: canvas.toDataURL(),
          fileName: `frame_${frameNumber}.jpg`,
          detectionData: response,
        };

        galleryImages = [galleryEntry, ...galleryImages];
        console.log(
          `[RTSP Manual] Added frame to gallery. Total: ${galleryImages.length}`,
        );
        onGalleryUpdate?.(galleryImages);
        onFrameCaptured?.();
      }
    } catch (error) {
      console.error("Failed to capture RTSP frame:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.FRAME_CAPTURE_FAILED.message),
      );
    }
  }

  /**
   * Handle frame from RTSPViewer (for prompt-required models)
   */
  function handleRTSPViewerFrame(event: CustomEvent) {
    const { frame, detectionData } = event.detail;

    // Add to gallery
    const frameNumber = galleryImages.length + 1;
    const galleryEntry = {
      original: frame,
      annotated: frame, // RTSPViewer already annotates
      fileName: `frame_${frameNumber}.jpg`,
      detectionData: detectionData,
    };

    galleryImages = [galleryEntry, ...galleryImages];
    onGalleryUpdate?.(galleryImages);
    onFrameCaptured?.();

    // Process stats
    if (detectionData) {
      const processed = processInferenceResponse(detectionData);
      onStatsUpdate?.(processed);
    }
  }

  /**
   * Handle RTSPViewer session start
   */
  function handleRTSPViewerSessionStart(event: CustomEvent) {
    const { session } = event.detail;
    activeSession = session;
    onSessionStart?.(session);
  }

  /**
   * Stop inference
   */
  export async function stopInference() {
    onDetectingChange?.(false);

    // Clear polling interval
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
      pollingIntervalId = null;
    }

    // Stop RTSPViewer if active
    if (promptRequired && rtspViewerRef) {
      rtspViewerRef.stop();
    }

    // Finish session if active
    if (activeSession) {
      try {
        await InferenceAPI.stopJob(activeSession.id);
        console.log(`Stopped RTSP session ${activeSession.id}`);
        activeSession = null;
      } catch (error) {
        console.error("Failed to stop RTSP session:", error);
        onError?.(new Error(SESSION_ERRORS.RTSP_SESSION_FINISH_FAILED.message));
      }
    }

    // Clear processed frames set
    processedFrameNumbers.clear();
  }

  // Reset all state (called during full reset, not stop)
  export function resetState() {
    galleryImages = [];
    onGalleryUpdate?.([]);
  }

  // Cleanup on component destroy
  onDestroy(() => {
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
    }
  });
</script>
