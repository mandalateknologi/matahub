<script lang="ts">
  /**
   * WebcamInferenceMode - Webcam inference component
   *
   * Extracted from capture page (Phase 2) to separate inference mode logic.
   * Handles webcam streaming with both continuous and manual capture modes.
   */

  import { onDestroy } from "svelte";
  import InferenceAPI from "../../../api/inference";
  import type { InferenceConfig, InferencePrompt } from "@/lib/types";
  import type {
    Model,
    PredictionJob,
    PredictionResponse,
  } from "@/lib/types";
  import {
    drawPolygonMask,
    drawBoundingBox,
    type DrawOptions,
    type MaskRenderOptions,
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

  // Props
  let {
    selectedModelId,
    selectedModel = null,
    confidence = 0.5,
    classFilter = [],
    inferPrompts = [],
    promptRequired = false,
    captureMode = "manual",
    campaignId = undefined,
    videoElement = undefined,
    canvasElement = undefined,
    canvasOverlay = undefined,
    // Callbacks
    onSessionStart = undefined,
    onFrameCaptured = undefined,
    onGalleryUpdate = undefined,
    onStatsUpdate = undefined,
    onDetectingChange = undefined,
    onError = undefined,
    onFlash = undefined,
    onShutterSound = undefined,
  }: {
    selectedModelId: number | null;
    selectedModel?: Model | null;
    confidence?: number;
    classFilter?: string[];
    inferPrompts?: InferencePrompt[];
    promptRequired?: boolean;
    captureMode?: "manual" | "continuous";
    campaignId?: number;
    videoElement?: HTMLVideoElement;
    canvasElement?: HTMLCanvasElement;
    canvasOverlay?: HTMLCanvasElement;
    // Callbacks
    onSessionStart?: ((session: PredictionJob) => void) | undefined;
    onFrameCaptured?: (() => void) | undefined;
    onGalleryUpdate?: ((images: any[]) => void) | undefined;
    onStatsUpdate?: ((stats: ProcessedResults) => void) | undefined;
    onDetectingChange?: ((isDetecting: boolean) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
    onFlash?: (() => void) | undefined;
    onShutterSound?: (() => void) | undefined;
  } = $props();

  // Local state
  let isDetecting = $state(false);
  let webcamStream: MediaStream | null = null;
  let webcamAbortController: AbortController | null = null;
  let animationFrameId: number | null = null;
  let activeSession: PredictionJob | null = null;
  let lastPredictionResponse: PredictionResponse | null = null;
  let galleryImages: any[] = [];

  /**
   * Start webcam inference
   */
  export async function startInference() {
    if (!selectedModelId) {
      onError?.(new Error(MODEL_ERRORS.NO_MODEL_SELECTED.message));
      return;
    }

    if (!videoElement || !canvasElement) {
      onError?.(new Error("Video or canvas element not available"));
      return;
    }

    // Initialize webcam stream if not already started
    if (!webcamStream) {
      try {
        webcamStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
        });
        if (videoElement) {
          videoElement.srcObject = webcamStream;
          videoElement.play();
        }
      } catch (error) {
        console.error("Failed to access webcam:", error);
        onError?.(new Error(SESSION_ERRORS.WEBCAM_ACCESS_FAILED.message));
        return;
      }
    }

    isDetecting = true;
    onDetectingChange?.(true);

    try {
      // Start inference session using dedicated webcam endpoint
      const inferOptions: InferenceConfig = {
        modelId: selectedModelId,
        confidence: confidence,
        classFilter: classFilter.length > 0 ? classFilter : undefined,
        prompts: promptRequired ? inferPrompts : undefined,
        campaignId: campaignId,
      };
      activeSession = await InferenceAPI.inferWebcam(inferOptions,captureMode);

      if (activeSession) {
        console.log(`Started webcam session with ID: ${activeSession.id}`);
        onSessionStart?.(activeSession);
        startRealtimeCameraInference();
      } else {
        console.error("Failed to start webcam session.");
        onError?.(
          new Error(SESSION_ERRORS.WEBCAM_SESSION_START_FAILED.message),
        );
      }
    } catch (error) {
      console.error("Webcam inference failed:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.WEBCAM_FAILED.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
    }
  }

  /**
   * Start real-time camera inference loop
   */
  function startRealtimeCameraInference() {
    if (!videoElement || !canvasElement || !selectedModelId) return;

    // Validate prompts for continuous mode (required for models requiring prompts)
    if (
      promptRequired &&
      captureMode === "continuous" &&
      inferPrompts.length === 0
    ) {
      onError?.(
        new Error(VALIDATION_ERRORS.PROMPTS_REQUIRED_WEBCAM_CONTINUOUS.message),
      );
      isDetecting = false;
      onDetectingChange?.(false);
      return;
    }

    let frameCount = 0;
    const captureInterval = promptRequired ? 2500 : 500; // Models requiring prompts: 2.5s, Standard models: 500ms
    let lastCaptureTime = 0;

    const detectFrame = async (timestamp: number) => {
      if (!isDetecting) {
        return;
      }

      // Throttle frame capture
      if (timestamp - lastCaptureTime >= captureInterval) {
        lastCaptureTime = timestamp;
        frameCount++;

        try {
          // Check if elements still exist (user might have switched tabs)
          if (!canvasElement || !videoElement) {
            return;
          }

          // Draw video frame to canvas
          const ctx = canvasElement.getContext("2d");
          if (!ctx) return;

          canvasElement.width = videoElement.videoWidth;
          canvasElement.height = videoElement.videoHeight;
          ctx.drawImage(videoElement, 0, 0);

          // Convert canvas to blob
          canvasElement.toBlob(
            async (blob) => {
              if (!blob) return;

              // Create file from blob
              const file = new File([blob], `frame_${frameCount}.jpg`, {
                type: "image/jpeg",
              });

              // Build API options
              const options: InferenceConfig = {
                modelId: selectedModelId!,
                confidence: confidence,
                classFilter: classFilter.length > 0 ? classFilter : undefined,
              };

              // Add prompts for models that require them
              if (promptRequired) {
                options.prompts = inferPrompts;
              }

              try {
                // Run detection for PREVIEW or CAPTURE
                let response: PredictionResponse;

                if (captureMode === "continuous" && activeSession) {
                  // Capture original frame BEFORE running detection
                  const original = canvasElement!.toDataURL();

                  // Continuous mode: save to database
                  response = await InferenceAPI.webcam_capture_frame(
                    activeSession.id,
                    file,
                    options,
                    frameCount,
                  );

                  // Create annotated version by drawing detections on a copy of the canvas
                  const annotatedCanvas = document.createElement("canvas");
                  annotatedCanvas.width = canvasElement!.width;
                  annotatedCanvas.height = canvasElement!.height;
                  const annotatedCtx = annotatedCanvas.getContext("2d");
                  if (annotatedCtx) {
                    // Draw original frame
                    annotatedCtx.drawImage(canvasElement!, 0, 0);

                    // Draw segmentation masks
                    if (response.masks && response.masks.length > 0) {
                      response.masks.forEach((mask, i) => {
                        drawPolygonMask(annotatedCtx, mask.polygon, i);
                      });
                    }

                    // Draw bounding boxes
                    response.boxes?.forEach((box, i) => {
                      const class_name = response.class_names?.[i] || "Object";
                      const score = response.scores?.[i] || 0;
                      const drawOptions: DrawOptions = {
                        showLabels: true,
                        showConfidence: true,
                      };

                      drawBoundingBox(
                        annotatedCtx,
                        box,
                        class_name,
                        score,
                        drawOptions,
                      );
                    });
                  }

                  const annotated = annotatedCanvas.toDataURL();

                  // Add to gallery
                  const galleryEntry = {
                    original: original,
                    annotated: annotated,
                    fileName: `frame_${frameCount}.jpg`,
                    detectionData: response,
                  };
                  galleryImages = [galleryEntry, ...galleryImages];
                  onGalleryUpdate?.(galleryImages);
                } else {
                  // Manual mode: preview only
                  response = await InferenceAPI.inferPreview(file, options);
                }

                // Draw results on overlay canvas
                if (canvasOverlay) {
                  const overlayCtx = canvasOverlay.getContext("2d");
                  if (overlayCtx && videoElement) {
                    canvasOverlay.width = videoElement.clientWidth;
                    canvasOverlay.height = videoElement.clientHeight;
                    overlayCtx.clearRect(
                      0,
                      0,
                      canvasOverlay.width,
                      canvasOverlay.height,
                    );

                    const scaleX =
                      canvasOverlay.width / videoElement.videoWidth;
                    const scaleY =
                      canvasOverlay.height / videoElement.videoHeight;

                    // Draw segmentation masks first (if available)
                    if (response.masks && response.masks.length > 0) {
                      response.masks.forEach((mask, i) => {
                        const scaledPolygon = mask.polygon.map(([x, y]) => [
                          x * scaleX,
                          y * scaleY,
                        ]);

                        drawPolygonMask(overlayCtx, scaledPolygon, i);
                      });
                    }

                    // Draw bounding boxes
                    response.boxes?.forEach((box, i) => {
                      const scaledBox = box.map((coord, idx) =>
                        idx % 2 === 0 ? coord * scaleX : coord * scaleY,
                      );
                      const score = response.scores?.[i] || 0;
                      const className = response.class_names?.[i] || "Object";
                      const drawOptions: DrawOptions = {
                        showLabels: true,
                        showConfidence: true,
                      };

                      drawBoundingBox(
                        overlayCtx,
                        scaledBox,
                        className,
                        score,
                        drawOptions,
                      );
                    });
                  }
                }

                // Process detection results for stats
                const processed = processInferenceResponse(response);
                onStatsUpdate?.(processed);

                // Cache for manual capture
                lastPredictionResponse = response;
              } catch (error) {
                console.error("Webcam frame detection failed:", error);
              }
            },
            "image/jpeg",
            0.8,
          );
        } catch (error) {
          console.error("Frame processing error:", error);
        }
      }

      // Continue capturing frames
      if (isDetecting) {
        animationFrameId = requestAnimationFrame(detectFrame);
      }
    };

    // Start the detection loop
    animationFrameId = requestAnimationFrame(detectFrame);
  }

  /**
   * Capture current camera frame (manual mode only)
   */
  export async function captureFrame() {
    if (
      !canvasElement ||
      !videoElement ||
      !lastPredictionResponse ||
      !selectedModelId
    ) {
      return;
    }

    // Validate prompts for manual mode
    if (promptRequired && inferPrompts.length === 0) {
      onError?.(new Error(VALIDATION_ERRORS.PROMPTS_REQUIRED_AUTO.message));
      return;
    }

    // Trigger flash animation and shutter sound
    onFlash?.();
    onShutterSound?.();

    try {
      // In manual mode, save to database via session capture-frame endpoint
      if (captureMode === "manual" && activeSession) {
        // Capture original frame BEFORE running detection
        const original = canvasElement.toDataURL();

        // Convert canvas to blob and save to database
        const blob = await new Promise<Blob | null>((resolve) =>
          canvasElement.toBlob(resolve, "image/jpeg", 0.8),
        );

        if (blob) {
          const frameNumber = galleryImages.length + 1;
          const file = new File([blob], `frame_${frameNumber}.jpg`, {
            type: "image/jpeg",
          });

          // Use strongly typed inference options, for better clarity and easy to search
          const inferOptions: InferenceConfig = {
            modelId: selectedModelId,
            confidence: confidence,
            classFilter: classFilter.length > 0 ? classFilter : undefined,
            prompts: promptRequired ? inferPrompts : undefined,
          };

          const response = await InferenceAPI.webcam_capture_frame(
            activeSession.id,
            file,
            inferOptions,
            frameNumber,
          );

          // Create annotated version by drawing detections on a copy of the canvas
          const annotatedCanvas = document.createElement("canvas");
          annotatedCanvas.width = canvasElement.width;
          annotatedCanvas.height = canvasElement.height;
          const annotatedCtx = annotatedCanvas.getContext("2d");
          if (annotatedCtx) {
            // Draw original frame
            annotatedCtx.drawImage(canvasElement, 0, 0);

            // Draw segmentation masks
            if (response.masks && response.masks.length > 0) {
              response.masks.forEach((mask, i) => {
                drawPolygonMask(annotatedCtx, mask.polygon, i);
              });
            }

            // Draw bounding boxes
            response.boxes?.forEach((box, i) => {
              const class_name = response.class_names?.[i] || "Object";
              const score = response.scores?.[i] || 0;
              const drawOptions: DrawOptions = {
                showLabels: true,
                showConfidence: true,
              };

              drawBoundingBox(
                annotatedCtx,
                box,
                class_name,
                score,
                drawOptions,
              );
            });
          }

          const annotated = annotatedCanvas.toDataURL();

          // Add to gallery
          const galleryEntry = {
            original: original,
            annotated: annotated,
            fileName: `frame_${frameNumber}.jpg`,
            detectionData: response,
          };
          galleryImages = [galleryEntry, ...galleryImages];
          onGalleryUpdate?.(galleryImages);
          onFrameCaptured?.();
        }
      }
    } catch (error) {
      console.error("Failed to capture frame:", error);
      onError?.(
        error instanceof Error
          ? error
          : new Error(INFERENCE_ERRORS.FRAME_CAPTURE_FAILED.message),
      );
    }
  }

  /**
   * Stop inference
   */
  export async function stopInference() {
    isDetecting = false;
    onDetectingChange?.(false);

    // Cancel animation frame
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }

    // Finish webcam session if applicable
    if (activeSession) {
      try {
        await InferenceAPI.stopJob(activeSession.id);
        activeSession = null;
      } catch (error) {
        console.error("Failed to finish webcam session:", error);
        onError?.(
          new Error(SESSION_ERRORS.WEBCAM_SESSION_FINISH_FAILED.message),
        );
      }
    }

    // Stop webcam stream
    if (webcamStream) {
      webcamStream.getTracks().forEach((track) => track.stop());
      webcamStream = null;
      if (videoElement) {
        videoElement.srcObject = null;
      }
    }

    // Abort pending requests
    if (webcamAbortController) {
      webcamAbortController.abort();
      webcamAbortController = null;
    }
  }

  // Cleanup on component destroy
  onDestroy(() => {
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId);
    }
    if (webcamStream) {
      webcamStream.getTracks().forEach((track) => track.stop());
    }
    if (webcamAbortController) {
      webcamAbortController.abort();
    }
  });
</script>

<!-- No UI - this is a headless component that only handles logic -->
