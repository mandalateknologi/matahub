<script lang="ts">
  /**
   * VideoInferenceMode - Video file inference component
   *
   * Extracted from capture page (Phase 2) to separate inference mode logic.
   * Handles video file upload with both continuous and manual capture modes.
   * Most complex mode with session management, heartbeat, and inactivity monitoring.
   */

  import { onDestroy } from "svelte";
  import InferenceAPI from "../../../api/inference";
  import type {
    Model,
    PredictionJob,
    PredictionResponse,
    PredictionResult,
  } from "@/lib/types";
  import type { InferencePrompt, InferenceConfig } from "@/lib/types";
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

  import { uiStore } from "../../../../lib/stores/uiStore";

  // Props
  let {
    selectedModelId,
    selectedModel = null,
    selectedFile = undefined,
    confidence = 0.5,
    classFilter = [],
    inferPrompts = [],
    promptRequired = false,
    captureMode = "manual",
    skipFrames = undefined,
    limitFrames = undefined,
    campaignId = undefined,
    videoElement = undefined,
    canvasElement = undefined,
    canvasOverlay = undefined,
    // Callbacks
    onSessionStart = undefined,
    onFrameCaptured = undefined,
    onJobUpdate = undefined,
    onGalleryUpdate = undefined,
    onStatsUpdate = undefined,
    onDetectingChange = undefined,
    onInactivityWarning = undefined,
    onError = undefined,
    onFlash = undefined,
    onShutterSound = undefined,
  }: {
    selectedModelId: number | null;
    selectedModel?: Model | null;
    selectedFile?: File;
    confidence?: number;
    classFilter?: string[];
    inferPrompts?: InferencePrompt[];
    promptRequired?: boolean;
    captureMode?: "manual" | "continuous";
    skipFrames?: number | undefined;
    limitFrames?: number | undefined;
    campaignId?: number;
    videoElement?: HTMLVideoElement;
    canvasElement?: HTMLCanvasElement;
    canvasOverlay?: HTMLCanvasElement;
    // Callbacks
    onSessionStart?: ((session: PredictionJob) => void) | undefined;
    onFrameCaptured?: (() => void) | undefined;
    onJobUpdate?: ((job: PredictionJob) => void) | undefined;
    onGalleryUpdate?: ((images: any[]) => void) | undefined;
    onStatsUpdate?: ((stats: ProcessedResults) => void) | undefined;
    onDetectingChange?: ((isDetecting: boolean) => void) | undefined;
    onInactivityWarning?: ((show: boolean) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
    onFlash?: (() => void) | undefined;
    onShutterSound?: (() => void) | undefined;
  } = $props();

  // Local state
  let isDetecting = $state(false);
  let activeSession: PredictionJob | null = null;
  let lastPredictionResponse: PredictionResponse | null = null;
  let galleryImages: any[] = [];
  let lastActivityTime: number = Date.now();

  // Interval IDs
  let videoDetectionIntervalId: number | null = null;
  let videoSessionHeartbeatInterval: number | null = null;
  let inactivityWarningTimeout: number | null = null;
  let pollingIntervalId: number | null = null;
  let activityCheckIntervalId: number | null = null; // Separate ID for activity monitoring
  let videoFPS: number = 30; // FPS from backend job metadata (default 30)

  /**
   * Start video inference
   */
  export async function startInference() {
    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    if (!selectedFile) {
      onError?.(new Error(VALIDATION_ERRORS.NO_FILE.message));
      return;
    }

    // Validate prompts if required
    if (promptRequired && inferPrompts.length === 0) {
      onError?.(new Error(VALIDATION_ERRORS.PROMPTS_REQUIRED.message));
      return;
    }

    isDetecting = true;
    onDetectingChange?.(true);

    try {
      if (captureMode === "continuous") {
        // Continuous mode: backend processes video automatically
        await startContinuousVideoDetection();
      } else {
        // Manual mode: session-based with live preview
        await startVideoDetectionSession();
      }
    } catch (error) {
      console.error("Video inference failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.VIDEO_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
    }
  }

  /**
   * Start continuous video detection (backend processing)
   */
  async function startContinuousVideoDetection() {
    if (!selectedFile || !selectedModelId) return;

    try {
      // Load video into video element so we can render frames for gallery
      if (videoElement) {
        const videoUrl = URL.createObjectURL(selectedFile);
        videoElement.src = videoUrl;
        // Wait for video metadata to load
        await new Promise<void>((resolve, reject) => {
          const onLoadedMetadata = () => {
            videoElement.removeEventListener(
              "loadedmetadata",
              onLoadedMetadata,
            );
            videoElement.removeEventListener("error", onError);
            resolve();
          };
          const onError = () => {
            videoElement.removeEventListener(
              "loadedmetadata",
              onLoadedMetadata,
            );
            videoElement.removeEventListener("error", onError);
            reject(new Error("Failed to load video"));
          };
          videoElement.addEventListener("loadedmetadata", onLoadedMetadata);
          videoElement.addEventListener("error", onError);
        });

        // Pause video to prepare for seeking
        videoElement.pause();
        console.log(
          `Video loaded for frame rendering: ${videoElement.videoWidth}x${videoElement.videoHeight}, duration: ${videoElement.duration}s`,
        );
      }

      // Build API options
      const options: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        campaignId: campaignId,
        duration: Math.floor(videoElement?.duration || 0),
        fps: 30, // Could be dynamic
      };

      // Add prompts for models that require them
      if (promptRequired) {
        options.prompts = inferPrompts;
      }

      // Start video detection job (backend processes frames)
      const job = await InferenceAPI.inferVideo(
        selectedFile,
        options,
        captureMode,
        skipFrames,
        limitFrames, // For future use
      );

      if (job) {
        console.log(`Started video detection job with ID: ${job.id}`);
        onJobUpdate?.(job);
        pollJobStatus(job.id);
      } else {
        console.error("Failed to start video detection job.");
        onError?.(new Error(INFERENCE_ERRORS.VIDEO_JOB_START_FAILED.message));
        isDetecting = false;
        onDetectingChange?.(false);
      }
    } catch (error) {
      console.error("Continuous video detection failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.VIDEO_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);

      // Clean up video element on error
      if (videoElement) {
        videoElement.pause();
        videoElement.src = "";
      }
    }
  }

  /**
   * Poll job status for continuous mode
   * Incrementally fetches results as they become available to handle large video files
   */
  function pollJobStatus(jobId: number) {
    let lastFetchedCount = 0;
    let processedResultIds = new Set<number>();

    pollingIntervalId = window.setInterval(async () => {
      try {
        const job: PredictionJob = await InferenceAPI.getJob(jobId);
        onJobUpdate?.(job);

        // Extract FPS from job metadata (accurate from backend)
        if (job.summary_json?.metadata?.fps) {
          videoFPS = job.summary_json.metadata.fps;
          console.log(`[pollJobStatus] Using FPS from backend metadata: ${videoFPS}`);
        }

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
              `[pollJobStatus] Fetched ${newResults.length} new results (${skip + 1}-${skip + newResults.length} of ${job.results_count})`,
            );
            console.log(
              `[pollJobStatus] Current gallery size: ${galleryImages.length}, Video element ready: ${!!videoElement}, Dimensions: ${videoElement?.videoWidth}x${videoElement?.videoHeight}`,
            );

            // Add new frames to gallery with deduplication
            for (const result of newResults) {
              // Skip if already processed (prevents duplicates)
              if (processedResultIds.has(result.id || 0)) {
                console.log(`Skipping duplicate result ID ${result.id}`);
                continue;
              }

              processedResultIds.add(result.id || 0);

              // Add frame to gallery array (will be processed in buildGalleryFromResults)
              if (
                !galleryImages.some(
                  (img) => img.detectionData?.id === result.id,
                )
              ) {
                try {
                  await addFrameToGallery(result);
                } catch (frameError) {
                  console.error(
                    `Failed to add frame ${result.frame_number}:`,
                    frameError,
                  );
                  // Continue processing other frames even if one fails
                }
              }
            }

            lastFetchedCount = job.results_count;
          } catch (error) {
            console.error("Error fetching video results:", error);
            // Still update lastFetchedCount to avoid infinite loop
            lastFetchedCount = job.results_count;
          }
        }

        // Handle job completion
        if (isComplete) {
          console.log(
            "[pollJobStatus] Job complete detected, clearing interval and updating state",
          );
          if (pollingIntervalId !== null) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
          }

          console.log("[pollJobStatus] Setting isDetecting to false");
          isDetecting = false;
          console.log("[pollJobStatus] Calling onDetectingChange(false)");
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
                  await addFrameToGallery(result);
                } catch (frameError) {
                  console.error(
                    `Failed to add remaining frame ${result.frame_number}:`,
                    frameError,
                  );
                  // Continue processing other frames
                }
              }
            }
          }

          // Show completion message and emit final stats
          if (job.status === "completed") {
            console.log(
              `Video processing completed. Total frames: ${job.results_count || 0}, Gallery images: ${galleryImages.length}`,
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

            uiStore.showSuccess(
              `Video processing completed. Total frames: ${job.results_count || 0}, Gallery images: ${galleryImages.length}`,
              "Video Inference Complete",
            );
          } else {
            console.error(`Video job failed with status: ${job.status}`);
            onError?.(new Error(INFERENCE_ERRORS.VIDEO_JOB_FAILED.message));
          }
        }
      } catch (error) {
        console.error("Failed to poll job status:", error);
        if (pollingIntervalId !== null) {
          clearInterval(pollingIntervalId);
          pollingIntervalId = null;
        }
        isDetecting = false;
        onDetectingChange?.(false);
      }
    }, 1000); // Poll every second for faster updates
  }

  /**
   * Add single frame to gallery (helper for incremental loading)
   */
  async function addFrameToGallery(result: PredictionResult) {
    console.log(
      `[addFrameToGallery] Starting for frame ${result.frame_number}`,
    );

    if (!videoElement) {
      console.warn("Video element not available for frame rendering");
      return;
    }

    // Check if video has valid dimensions
    if (!videoElement.videoWidth || !videoElement.videoHeight) {
      console.warn(
        `Video element not ready (dimensions: ${videoElement.videoWidth}x${videoElement.videoHeight}), skipping frame ${result.frame_number}`,
      );
      return;
    }

    try {
      const frameNumber = result.frame_number || 0;
      const fps = videoFPS; // Use FPS from backend metadata
      const timestamp = frameNumber / fps;

      console.log(
        `[addFrameToGallery] Frame ${frameNumber}: seeking to ${timestamp}s (FPS: ${fps}, current: ${videoElement.currentTime}s)`,
      );

      // Create canvases
      const originalCanvas = document.createElement("canvas");
      const annotatedCanvas = document.createElement("canvas");
      const originalCtx = originalCanvas.getContext("2d");
      const annotatedCtx = annotatedCanvas.getContext("2d");
      if (!originalCtx || !annotatedCtx) return;

      // Seek to frame with timeout fallback
      const needsSeek = Math.abs(videoElement.currentTime - timestamp) > 0.1;
      let actualTimestamp = timestamp;

      if (needsSeek) {
        videoElement.currentTime = timestamp;

        try {
          await Promise.race([
            new Promise<void>((resolve) => {
              const onSeeked = () => {
                videoElement.removeEventListener("seeked", onSeeked);
                resolve();
              };
              videoElement.addEventListener("seeked", onSeeked);
            }),
            new Promise<void>((_, reject) =>
              setTimeout(() => reject(new Error("Seek timeout")), 5000),
            ),
          ]);
        } catch (error) {
          // Seek timeout - use current position as fallback
          console.warn(
            `[addFrameToGallery] Seek timeout for frame ${frameNumber} (target: ${timestamp}s), using current position: ${videoElement.currentTime}s`,
          );
          actualTimestamp = videoElement.currentTime;
        }
      }

      // Render frame (whether seek succeeded or used fallback)
      originalCanvas.width = annotatedCanvas.width = videoElement.videoWidth;
      originalCanvas.height = annotatedCanvas.height = videoElement.videoHeight;

      originalCtx.drawImage(videoElement, 0, 0);
      annotatedCtx.drawImage(videoElement, 0, 0);

      // Draw detections
      if (result.boxes && result.boxes.length > 0) {
        result.boxes.forEach((box: number[], i: number) => {
          drawBoundingBox(
            annotatedCtx,
            box,
            result.class_names?.[i] || "",
            result.scores?.[i] || 0,
            { showLabels: true, showConfidence: true },
          );
        });
      }

      if (result.masks && result.masks.length > 0) {
        result.masks.forEach((mask: any, i: number) => {
          if (mask.polygon) {
            drawPolygonMask(annotatedCtx, mask.polygon, i);
          }
        });
      }

      // Add to gallery with actual timestamp (may differ if seek timed out)
      const galleryItem = {
        original: originalCanvas.toDataURL(),
        annotated: annotatedCanvas.toDataURL(),
        fileName: `frame_${frameNumber}.jpg`,
        timestamp: actualTimestamp,
        detectionData: result,
      };

      galleryImages = [...galleryImages, galleryItem];
      console.log(
        `[addFrameToGallery] Frame ${frameNumber} added to gallery. Total images: ${galleryImages.length}`,
      );

      // CRITICAL: Create new array reference for Svelte reactivity
      const updatedGallery = [...galleryImages];
      onGalleryUpdate?.(updatedGallery);

      // Process and emit stats for this result
      if (result.boxes || result.masks) {
        const processed = processInferenceResponse(result);
        onStatsUpdate?.(processed);
      }

      console.log(
        `[addFrameToGallery] Frame ${frameNumber} completed successfully`,
      );
    } catch (error) {
      console.error(`Failed to add frame ${result.frame_number}:`, error);
    }
  }

  /**
   * Build gallery from job results (continuous video mode)
   * Seeks video element to capture frames at specific timestamps
   */
  async function buildGalleryFromResults(results: PredictionResult[]) {
    if (!videoElement) return;

    galleryImages = [];

    for (const result of results) {
      try {
        // Calculate timestamp from frame number
        const frameNumber = result.frame_number || 0;
        const fps = videoFPS; // Use FPS from backend metadata
        const timestamp = frameNumber / fps;

        // Create canvases for original and annotated
        const originalCanvas = document.createElement("canvas");
        const annotatedCanvas = document.createElement("canvas");
        const originalCtx = originalCanvas.getContext("2d");
        const annotatedCtx = annotatedCanvas.getContext("2d");
        if (!originalCtx || !annotatedCtx) continue;

        // Check if we need to seek
        const needsSeek = Math.abs(videoElement.currentTime - timestamp) > 0.1;

        if (needsSeek) {
          videoElement.currentTime = timestamp;
        }

        if (needsSeek) {
          await Promise.race([
            new Promise<void>((resolve) => {
              const onSeeked = () => {
                videoElement.removeEventListener("seeked", onSeeked);

                // Set canvas sizes
                originalCanvas.width = annotatedCanvas.width =
                  videoElement.videoWidth;
                originalCanvas.height = annotatedCanvas.height =
                  videoElement.videoHeight;

                // Draw original frame
                originalCtx.drawImage(videoElement, 0, 0);

                // Draw annotated frame with detections
                annotatedCtx.drawImage(videoElement, 0, 0);

                // Draw bounding boxes
                if (result.boxes && result.boxes.length > 0) {
                  result.boxes.forEach((box: number[], i: number) => {
                    const drawOptions: DrawOptions = {
                      showLabels: true,
                      showConfidence: true,
                    };
                    drawBoundingBox(
                      annotatedCtx,
                      box,
                      result.class_names?.[i] || "",
                      result.scores?.[i] || 0,
                      drawOptions,
                    );
                  });
                }

                // Draw masks
                if (result.masks && result.masks.length > 0) {
                  result.masks.forEach((mask: any, i: number) => {
                    if (mask.polygon) {
                      drawPolygonMask(annotatedCtx, mask.polygon, i);
                    }
                  });
                }

                resolve();
              };
              videoElement.addEventListener("seeked", onSeeked);
            }),
            new Promise<void>((_, reject) =>
              setTimeout(() => reject(new Error("Seek timeout")), 5000),
            ),
          ]);
        } else {
          // Already at correct position
          originalCanvas.width = annotatedCanvas.width =
            videoElement.videoWidth;
          originalCanvas.height = annotatedCanvas.height =
            videoElement.videoHeight;

          // Draw original frame
          originalCtx.drawImage(videoElement, 0, 0);

          // Draw annotated frame
          annotatedCtx.drawImage(videoElement, 0, 0);

          // Draw bounding boxes
          if (result.boxes && result.boxes.length > 0) {
            result.boxes.forEach((box: number[], i: number) => {
              const drawOptions: DrawOptions = {
                showLabels: true,
                showConfidence: true,
              };
              drawBoundingBox(
                annotatedCtx,
                box,
                result.class_names?.[i] || "",
                result.scores?.[i] || 0,
                drawOptions,
              );
            });
          }

          // Draw masks
          if (result.masks && result.masks.length > 0) {
            result.masks.forEach((mask: any, i: number) => {
              if (mask.polygon) {
                drawPolygonMask(annotatedCtx, mask.polygon, i);
              }
            });
          }
        }

        const fileName = `frame_${frameNumber}.jpg`;
        galleryImages.push({
          original: originalCanvas.toDataURL(),
          annotated: annotatedCanvas.toDataURL(),
          fileName: fileName,
          timestamp: timestamp,
          detectionData: result,
        });
      } catch (error) {
        console.error(
          "Failed to process result:",
          error instanceof Error ? error.message : error,
        );
        // Continue to next result instead of failing completely
        continue;
      }
    }

    onGalleryUpdate?.(galleryImages);
  }

  /**
   * Start video detection session (manual mode)
   */
  async function startVideoDetectionSession() {
    if (!selectedFile || !selectedModelId || !videoElement) return;

    try {
      // Create object URL for video preview
      const videoUrl = URL.createObjectURL(selectedFile);
      videoElement.src = videoUrl;
      
      // Wait for metadata to load
      await new Promise<void>((resolve, reject) => {
        const onLoadedMetadata = () => {
          videoElement.removeEventListener("loadedmetadata", onLoadedMetadata);
          videoElement.removeEventListener("error", onError);
          resolve();
        };
        const onError = () => {
          videoElement.removeEventListener("loadedmetadata", onLoadedMetadata);
          videoElement.removeEventListener("error", onError);
          reject(new Error("Failed to load video"));
        };
        videoElement.addEventListener("loadedmetadata", onLoadedMetadata);
        videoElement.addEventListener("error", onError);
      });
      
      await videoElement.play();

      // Build API options
      const options: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        campaignId: campaignId,
        duration: Math.floor(videoElement.duration),
        fps: 30, // Could be dynamic
      };

      // Add prompts for models that require them
      if (promptRequired) {
        options.prompts = inferPrompts;
      }

      // Start session
      const session = await InferenceAPI.inferVideo(
        selectedFile,
        options,
        captureMode,
        skipFrames,
        limitFrames, // For future use
      );

      if (session) {
        console.log(`Started video session with ID: ${session.id}`);
        activeSession = session;
        onSessionStart?.(session);
        lastActivityTime = Date.now();

        // Start heartbeat to keep session alive
        sendVideoSessionHeartbeat();
        videoSessionHeartbeatInterval = window.setInterval(
          sendVideoSessionHeartbeat,
          25000,
        ); // Every 25 seconds

        // Start inactivity monitoring
        checkVideoSessionActivity();

        // Start live preview loop
        startLivePreview();
      } else {
        console.error("Failed to start video session.");
        onError?.(new Error(SESSION_ERRORS.VIDEO_SESSION_START_FAILED.message));
      }
    } catch (error) {
      console.error("Video session start failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(SESSION_ERRORS.VIDEO_SESSION_START_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
    }
  }

  /**
   * Send heartbeat to keep session alive
   */
  async function sendVideoSessionHeartbeat() {
    if (!activeSession) return;

    try {
      await InferenceAPI.sendJobHeartbeat(activeSession.id);
      console.log(`Sent heartbeat for video session ${activeSession.id}`);
    } catch (error) {
      console.error("Failed to send video session heartbeat:", error);
    }
  }

  /**
   * Check session activity and warn if inactive
   */
  function checkVideoSessionActivity() {
    const INACTIVITY_THRESHOLD = 90000; // 90 seconds
    const CHECK_INTERVAL = 10000; // Check every 10 seconds

    const checkActivity = () => {
      const now = Date.now();
      const timeSinceLastActivity = now - lastActivityTime;

      if (timeSinceLastActivity > INACTIVITY_THRESHOLD) {
        console.warn("Video session inactive for too long");
        onInactivityWarning?.(true);

        // Auto-finish session after warning
        inactivityWarningTimeout = window.setTimeout(() => {
          console.log("Auto-finishing inactive video session");
          finishVideoSession();
        }, 30000); // 30 seconds after warning
      }
    };

    // Initial check
    checkActivity();

    // Periodic checks
    const activityCheckInterval = window.setInterval(
      checkActivity,
      CHECK_INTERVAL,
    );

    // Store interval ID for cleanup (using separate variable to avoid conflicts)
    activityCheckIntervalId = activityCheckInterval;
  }

  /**
   * Warn about inactive session
   */
  function warnInactiveVideoSession() {
    onInactivityWarning?.(true);
  }

  /**
   * Start live preview loop
   */
  function startLivePreview() {
    if (!videoElement || !canvasOverlay || !selectedModelId) return;

    const PREVIEW_INTERVAL = promptRequired ? 3000 : 1000; // 3s for prompt models, 1s for standard

    const previewLoop = async () => {
      if (!isDetecting || !activeSession) {
        return;
      }

      try {
        // Capture current frame
        if (!canvasElement || !videoElement) return;

        const ctx = canvasElement.getContext("2d");
        if (!ctx) return;

        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;
        ctx.drawImage(videoElement, 0, 0);

        // Convert to blob
        const blob = await new Promise<Blob | null>((resolve) =>
          canvasElement!.toBlob(resolve, "image/jpeg", 0.8),
        );

        if (blob) {
          const file = new File([blob], "preview_frame.jpg", {
            type: "image/jpeg",
          });

          const inferOptions: InferenceConfig = {
            modelId: selectedModelId!,
            confidence: confidence,
            classFilter: classFilter.length > 0 ? classFilter : undefined,
            prompts: promptRequired ? inferPrompts : undefined,
          };

          // Preview frame (doesn't save to database)
          const response = await InferenceAPI.inferPreview(file, inferOptions);

          // Draw results on overlay canvas (COPIED FROM LEGACY)
          if (canvasOverlay) {
            const overlayCtx = canvasOverlay.getContext("2d");
            if (overlayCtx) {
              canvasOverlay.width = videoElement.clientWidth;
              canvasOverlay.height = videoElement.clientHeight;
              console.log("clearRect", response);
              overlayCtx.clearRect(
                0,
                0,
                canvasOverlay.width,
                canvasOverlay.height,
              );

              const scaleX = canvasOverlay.width / videoElement.videoWidth;
              const scaleY = canvasOverlay.height / videoElement.videoHeight;

              // Draw segmentation masks first (if available)
              if (response.masks && response.masks.length > 0) {
                response.masks.forEach((mask, i) => {
                  // Scale polygon coordinates for overlay canvas
                  const scaledPolygon = mask.polygon.map(([x, y]) => [
                    x * scaleX,
                    y * scaleY,
                  ]);
                  drawPolygonMask(overlayCtx, scaledPolygon, i);
                });
                console.log("Drawing segmentation masks:", response);
              }

              // Draw bounding boxes (for detection/classification tasks)
              response.boxes?.forEach((box, i) => {
                const [x1, y1, x2, y2] = box.map((coord, idx) =>
                  idx % 2 === 0 ? coord * scaleX : coord * scaleY,
                );
                const score = response.scores?.[i];
                const className = response.class_names?.[i];

                overlayCtx.strokeStyle = "#00ff00";
                overlayCtx.lineWidth = 2;
                overlayCtx.strokeRect(x1, y1, x2 - x1, y2 - y1);

                overlayCtx.fillStyle = "#00ff00";
                overlayCtx.font = "14px Arial";
                if (score !== undefined && className) {
                  overlayCtx.fillText(
                    `${className} ${(score * 100).toFixed(1)}%`,
                    x1,
                    y1 - 5,
                  );
                }
              });
            }
          }

          // Process stats
          console.log("Processing stats", response);
          const processed = processInferenceResponse(response);
          onStatsUpdate?.(processed);

          // Cache for manual capture
          lastPredictionResponse = response;
        }
      } catch (error) {
        console.error("Live preview error:", error);
      }
    };

    // Start preview loop
    const intervalId = window.setInterval(previewLoop, PREVIEW_INTERVAL);
    videoDetectionIntervalId = intervalId;
  }

  /**
   * Capture current video frame (manual mode only)
   */
  export async function captureFrame() {
    console.log("[captureFrame] FUNCTION CALLED - Start of captureFrame");
    console.log(
      "[captureFrame] videoElement:",
      !!videoElement,
      "activeSession:",
      !!activeSession,
      "selectedModelId:",
      selectedModelId,
    );

    if (!videoElement || !activeSession || !selectedModelId) {
      console.warn("[captureFrame] Missing requirements - returning early");
      return;
    }

    if (!activeSession) {
      console.error("[captureFrame] No active session");
      onError?.(new Error(SESSION_ERRORS.NO_ACTIVE_SESSION.message));
      return;
    }

    console.log("[captureFrame] All checks passed, proceeding with capture");

    // Trigger flash animation and shutter sound
    onFlash?.();
    onShutterSound?.();

    try {
      // Update activity time
      lastActivityTime = Date.now();
      onInactivityWarning?.(false);

      // Clear inactivity warning timeout
      if (inactivityWarningTimeout !== null) {
        clearTimeout(inactivityWarningTimeout);
        inactivityWarningTimeout = null;
      }

      // Capture current frame from video
      const canvas = document.createElement("canvas");
      canvas.width = videoElement.videoWidth;
      canvas.height = videoElement.videoHeight;
      const ctx = canvas.getContext("2d");

      if (ctx) {
        // Draw current video frame
        ctx.drawImage(videoElement, 0, 0);

        // Convert canvas to blob
        const blob = await new Promise<Blob | null>((resolve) =>
          canvas.toBlob(resolve, "image/jpeg", 0.9),
        );

        if (blob) {
          // Create file from blob with timestamp
          const currentTime = videoElement.currentTime;
          const frameNumber = Math.floor(currentTime * 30); // Estimate frame number (30 fps)
          const timestamp = formatTimestamp(currentTime);
          const file = new File([blob], `frame_${frameNumber}.jpg`, {
            type: "image/jpeg",
          });

          let response: PredictionResponse;
          const originalDataUrl = canvas.toDataURL("image/jpeg");
          let annotatedDataUrl = originalDataUrl;

          // Always capture fresh detections for the exact frame
          // This ensures detections match the captured frame, not stale preview results
          console.log(
            "[captureFrame] Calling API to capture frame with fresh detections",
          );
          response = await InferenceAPI.video_capture_frame(
            activeSession.id,
            file,
            {
              modelId: selectedModelId,
              confidence: confidence,
              classFilter: classFilter.length > 0 ? classFilter : undefined,
              prompts: promptRequired ? inferPrompts : undefined,
            },
            frameNumber,
            timestamp,
          );
          console.log("[captureFrame] API response received:", response);

          // Draw bounding boxes on annotated version
          if (response.boxes && response.boxes.length > 0) {
            response.boxes.forEach((box: number[], i: number) => {
              const drawOptions: DrawOptions = {
                showLabels: true,
                showConfidence: true,
              };
              drawBoundingBox(
                ctx,
                box,
                response.class_names?.[i] || "",
                response.scores?.[i] || 0,
                drawOptions,
              );
            });
          }

          // Draw masks if available
          if (response.masks && response.masks.length > 0) {
            response.masks.forEach((mask: any, i: number) => {
              if (mask.polygon) {
                drawPolygonMask(ctx, mask.polygon, i);
              }
            });
          }

          // Get annotated frame as data URL
          annotatedDataUrl = canvas.toDataURL("image/jpeg");

          // Add to gallery
          galleryImages = [
            {
              original: originalDataUrl,
              annotated: annotatedDataUrl,
              fileName: `Frame at ${timestamp} (${galleryImages.length + 1})`,
              detectionData: response,
              timestamp: currentTime,
            },
            ...galleryImages,
          ];

          onGalleryUpdate?.(galleryImages);
          onFrameCaptured?.();
        }
      }
    } catch (error) {
      console.error("Failed to capture video frame:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.FRAME_CAPTURE_FAILED.message),
      );
    }
  }

  /**
   * Format timestamp for display
   */
  function formatTimestamp(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 10);

    if (hours > 0) {
      return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms}`;
    }
    return `${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms}`;
  }

  /**
   * Finish video session
   */
  async function finishVideoSession() {
    if (!activeSession) return;

    try {
      await InferenceAPI.stopJob(activeSession.id);
      console.log(`Finished video session ${activeSession.id}`);
      activeSession = null;
    } catch (error) {
      console.error("Failed to finish video session:", error);
      onError?.(new Error(SESSION_ERRORS.VIDEO_SESSION_FINISH_FAILED.message));
    }
  }

  /**
   * Stop inference
   */
  export async function stopInference() {
    isDetecting = false;
    onDetectingChange?.(false);

    // Clear all intervals
    if (videoDetectionIntervalId !== null) {
      clearInterval(videoDetectionIntervalId);
      videoDetectionIntervalId = null;
    }

    if (videoSessionHeartbeatInterval !== null) {
      clearInterval(videoSessionHeartbeatInterval);
      videoSessionHeartbeatInterval = null;
    }

    if (inactivityWarningTimeout !== null) {
      clearTimeout(inactivityWarningTimeout);
      inactivityWarningTimeout = null;
    }

    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
      pollingIntervalId = null;
    }

    if (activityCheckIntervalId !== null) {
      clearInterval(activityCheckIntervalId);
      activityCheckIntervalId = null;
    }

    // Finish session if active
    if (activeSession) {
      await finishVideoSession();
    }

    // Stop video playback
    if (videoElement) {
      videoElement.pause();
      videoElement.src = "";
    }

    // Reset FPS for next video
    videoFPS = 30;
  }

  // Cleanup on component destroy
  onDestroy(() => {
    if (videoDetectionIntervalId !== null) {
      clearInterval(videoDetectionIntervalId);
    }
    if (videoSessionHeartbeatInterval !== null) {
      clearInterval(videoSessionHeartbeatInterval);
    }
    if (inactivityWarningTimeout !== null) {
      if (activityCheckIntervalId !== null) {
        clearInterval(activityCheckIntervalId);
      }
      clearTimeout(inactivityWarningTimeout);
    }
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
    }
  });
</script>

<!-- No UI - this is a headless component that only handles logic -->
