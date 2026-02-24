<script lang="ts">
  import { onMount, onDestroy, tick } from "svelte";
  import { modelsAPI } from "../../../lib/api/models";

  import InferenceAPI from "../../../lib/api/inference";
  import type { InferencePrompt, InferenceConfig } from "@/lib/types";

  import {
    drawInferenceResults,
    drawInferenceResultsScaled,
    drawInferenceResultsToDataURL,
    drawPolygonMask,
    drawBoundingBox,
    type DrawOptions,
  } from "../../../lib/utils/drawingUtils";

  import {
    processInferenceResponse,
    normalizeInferenceResponse,
    type ProcessedResults,
    type FrameStats,
  } from "../../../lib/utils/responseProcessor";

  import { campaignsAPI } from "../../../lib/api/campaigns";
  import { playbooksAPI } from "../../../lib/api/playbooks";
  import type {
    Model,
    PredictionResponse,
    PredictionResponseWithFrame,
    PredictionJob,
    MaskData,
    PredictionResult,
  } from "@/lib/types";

  import type { Campaign } from "../../../lib/types/campaign";
  import { uiStore } from "../../../lib/stores/uiStore";
  import RTSPViewer from "../../../lib/components/visionmask/RTSPViewer.svelte";

  // Phase 1 Components
  import SourceTypeSelector from "../../../lib/components/capture/SourceTypeSelector.svelte";
  import ModelSelector from "../../../lib/components/capture/ModelSelector.svelte";
  import SmartSettingsPanel from "../../../lib/components/capture/SmartSettingsPanel.svelte";
  import StatsPanel from "../../../lib/components/capture/StatsPanel.svelte";
  import CaptureGallery from "../../../lib/components/capture/CaptureGallery.svelte";
  import FileUploadControl from "../../../lib/components/capture/FileUploadControl.svelte";
  import CaptureControls from "../../../lib/components/capture/CaptureControls.svelte";

  // Phase 2 Components
  import MediaDisplay from "../../../lib/components/capture/MediaDisplay.svelte";
  import ViewModeSwitcher from "../../../lib/components/capture/ViewModeSwitcher.svelte";

  // Phase 2 Inference Mode Components
  import ImageInferenceMode from "../../../lib/components/capture/modes/ImageInferenceMode.svelte";
  import BatchInferenceMode from "../../../lib/components/capture/modes/BatchInferenceMode.svelte";
  import WebcamInferenceMode from "../../../lib/components/capture/modes/WebcamInferenceMode.svelte";
  import VideoInferenceMode from "../../../lib/components/capture/modes/VideoInferenceMode.svelte";
  import RTSPInferenceMode from "../../../lib/components/capture/modes/RTSPInferenceMode.svelte";

  // Phase 3: Centralized Stores
  import {
    inferenceSettingsStore,
    requiresPrompts as storeRequiresPrompts,
    modelReady,
    effectivePromptMode as getEffectivePromptMode,
  } from "../../../lib/stores/inferenceSettingsStore";
  import {
    inferenceJobStore,
    availableClasses as storeAvailableClasses,
    confidenceStats,
    rtspFrameReady,
  } from "../../../lib/stores/inferenceJobStore";
  import {
    inferenceGalleryStore,
    currentImage as storeCurrentImage,
    hasMultipleImages,
  } from "../../../lib/stores/inferenceGalleryStore";
  import {
    canvasStore,
    hasMainCanvas,
    hasOverlayCanvas,
  } from "../../../lib/stores/canvasStore";

  // Optional session context
  export let campaignId: number | undefined = undefined;
  export let playbookId: number | undefined = undefined;
  let campaign: Campaign | null = null;

  // State
  let models: Model[] = [];
  let selectedModelId: number | null = null;
  let selectedModel: Model | null = null;
  let confidence = 0.5;
  let skipFrames = 5; // Frame skip for video/RTSP (1=all frames, 5=every 5th frame)
  let sourceType: "image" | "batch" | "video" | "webcam" | "rtsp" = "image";

  // Media elements
  let videoElement: HTMLVideoElement;
  let canvasElement: HTMLCanvasElement;
  let canvasOverlay: HTMLCanvasElement;
  let rtspCanvasElement: HTMLCanvasElement;
  let rtspCanvasOverlay: HTMLCanvasElement;
  let fileInputElement: HTMLInputElement | undefined = undefined;
  let imagePreview: string | null = null;
  let selectedFile: File | null = null;
  let selectedFiles: File[] = [];
  let rtspUrl = "";

  // Detection state
  let isDetecting = false;
  let detections: PredictionResponse | null = null;
  let currentJob: PredictionJob | null = null;
  let detectionResults: Array<{ class_name: string; confidence: number }> = [];
  let frameStats: FrameStats = {
    width: 0,
    height: 0,
    fps: 0,
    totalDetections: 0,
    totalMasks: 0,
    avgConfidence: 0,
    task_type: "",
  };
  let classCounts: Record<string, number> = {};

  // Model That Requires Prompts
  let promptRequired = false;
  let inferPrompts: InferencePrompt[] = [];
  let promptMode: "auto" | "text" | "point" | "box" = "auto";
  let textPrompt = "";
  let isDrawingBox = false;
  let boxStartCoords: { x: number; y: number } | null = null;
  let tempBoxCoords: { x1: number; y1: number; x2: number; y2: number } | null =
    null;
  let batchProcessingProgress = { current: 0, total: 0, fileName: "" };

  // Gallery state
  let galleryImages: Array<{
    original: string;
    annotated: string;
    fileName: string;
    timestamp?: number; // For video frames
    detectionData?: PredictionResponse;
  }> = [];
  let currentGalleryIndex = 0;
  let selectedImageIndex = 0; // For webcam gallery view

  // Webcam view mode state (iPhone-style switcher)
  let webcamViewMode: "live" | "gallery" = "live";

  // Webcam capture mode (manual vs continuous)
  let webcamCaptureMode: "continuous" | "manual" = "manual";
  let lastPredictionResponse: PredictionResponse | null = null;
  let isFlashing = false;

  // RTSP view mode and capture mode
  let rtspViewMode: "live" | "gallery" = "live";
  let rtspCaptureMode: "continuous" | "manual" = "manual";
  let rtspLastFrameData: {
    frame: string;
    predictions: PredictionResponse;
  } | null = null;
  let processedFrameNumbers = new Set<number>();
  let rtspFrameStatus: "loading" | "ready" | "error" = "loading";

  // RTSP viewer component reference
  let rtsp_viewer: RTSPViewer | null = null;

  // Phase 2: Inference mode component refs
  let imageInferenceMode: ImageInferenceMode | null = null;
  let batchInferenceMode: BatchInferenceMode | null = null;
  let webcamInferenceMode: WebcamInferenceMode | null = null;
  let videoInferenceMode: VideoInferenceMode | null = null;
  let rtspInferenceMode: RTSPInferenceMode | null = null;

  // Video capture mode (manual vs continuous)
  let videoCaptureMode: "manual" | "continuous" = "manual";
  let videoDetectionIntervalId: number | null = null;

  // Video session state (for manual mode)
  let activeVideoSession: PredictionJob | null = null;
  let videoSessionHeartbeatInterval: number | null = null;
  let showInactivityModal = false;
  let inactivityWarningTimeout: number | null = null;

  // Webcam session state (for manual mode)
  let activeWebcamSession: PredictionJob | null = null;

  // Reactive statement to render RTSP polygon masks when frame data updates
  $: if (
    rtspLastFrameData &&
    rtspCanvasElement &&
    rtspCanvasOverlay &&
    sourceType === "rtsp" &&
    rtspViewMode === "live" &&
    $rtspFrameReady &&
    $inferenceJobStore.rtspLastFrameData
  ) {
    // Use store's rtspFrameReady derived (boolean check) + rtspLastFrameData
    drawRTSPLiveFrame($inferenceJobStore.rtspLastFrameData);
  }

  // Reactive statement to update current frame stats when gallery index changes
  // RS2 FIX: Cancel pending overlay updates to prevent desync
  $: if (
    galleryImages.length > 0 &&
    galleryImages[currentGalleryIndex]?.detectionData &&
    $storeCurrentImage
  ) {
    // Use store's currentImage derived
    const data = $storeCurrentImage.detectionData!;
    updateCurrentFrameStats(data);

    // If video mode and timestamp exists, seek to that position and update overlay
    if (
      sourceType === "video" &&
      $storeCurrentImage.timestamp !== undefined &&
      videoElement
    ) {
      // Cancel pending overlay update
      if (overlayUpdateTimer) {
        clearTimeout(overlayUpdateTimer);
        overlayUpdateTimer = null;
      }

      videoElement.currentTime = $storeCurrentImage.timestamp;
      // Schedule new overlay update
      if (videoCaptureMode === "continuous") {
        overlayUpdateTimer = window.setTimeout(() => {
          updateVideoOverlay();
          overlayUpdateTimer = null;
        }, 100);
      }
    }
  }

  // Reactive statement to handle webcam access when source type changes
  // RS3 FIX: Use AbortController to prevent stream orphaning on rapid mode switches
  $: if (sourceType === "webcam") {
    // Start webcam preview when user selects webcam source (before detection)
    if (!webcamStream && !isDetecting) {
      // Cancel previous request if still pending
      if (webcamAbortController) {
        webcamAbortController.abort();
      }
      webcamAbortController = new AbortController();
      const currentController = webcamAbortController;

      (async () => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 },
          });

          // Check if this request was aborted
          if (currentController.signal.aborted) {
            stream.getTracks().forEach((track) => track.stop());
            return;
          }

          webcamStream = stream;
          if (videoElement) {
            videoElement.srcObject = webcamStream;
            videoElement.play();
            frameStats.width = 640;
            frameStats.height = 480;
          }
        } catch (error: any) {
          if (error.name === "AbortError") return;
          console.error("Failed to access webcam:", error);
          uiStore.showError(
            "Failed to access webcam. Please check permissions.",
            "Webcam Access Error",
          );
        }
      })();
    }
  } else {
    // Stop webcam when user switches away from webcam source
    if (webcamAbortController) {
      webcamAbortController.abort();
      webcamAbortController = null;
    }
    if (webcamStream) {
      webcamStream.getTracks().forEach((track) => track.stop());
      webcamStream = null;
      if (videoElement) {
        videoElement.srcObject = null;
      }
    }
  }

  // Auto-switch prompt mode to "text" for RTSP (since point/box are disabled)
  $: if (promptRequired && sourceType === "rtsp") {
    if (promptMode !== "text") {
      promptMode = "text";
    }
  }

  // RS7+RS8 FIX: Canvas draw queue to prevent overlapping draws
  async function processCanvasQueue() {
    if (canvasDrawing || canvasDrawQueue.length === 0) return;
    canvasDrawing = true;

    while (canvasDrawQueue.length > 0) {
      const draw = canvasDrawQueue.shift()!;
      draw();
      await tick(); // Allow DOM to update
    }

    canvasDrawing = false;
  }

  function queueCanvasDraw(drawFn: () => void) {
    canvasDrawQueue.push(drawFn);
    processCanvasQueue();
  }

  // Draw model prompts when image preview or prompts change (for models requiring prompts)
  // RS7: Queue image load and initial draw
  $: if (
    imagePreview &&
    canvasElement &&
    promptRequired &&
    sourceType === "image"
  ) {
    queueCanvasDraw(() => {
      const ctx = canvasElement?.getContext("2d");
      if (ctx && imagePreview) {
        const img = new Image();
        img.onload = () => {
          canvasElement!.width = img.width;
          canvasElement!.height = img.height;
          ctx.drawImage(img, 0, 0);

          // Draw detections first (if available) so they're underneath prompts
          if (detections) {
            drawInferenceResults(ctx, detections, {
              showLabels: true,
              showConfidence: true,
              selectedClasses:
                selectedClasses.size > 0 ? selectedClasses : undefined,
            });
          }

          // Then draw prompts on top
          drawInferencePrompts();
        };
        img.src = imagePreview;
      }
    });
  }

  // Redraw prompts component when prompts, temp box, or drawing state changes
  // RS8: Queue prompt overlay redraw with RAF throttling
  let promptDrawPending = false;
  $: if (
    canvasElement &&
    promptRequired &&
    imagePreview &&
    (inferPrompts || tempBoxCoords || isDrawingBox)
  ) {
    if (!promptDrawPending) {
      promptDrawPending = true;
      requestAnimationFrame(() => {
        queueCanvasDraw(() => drawInferencePrompts());
        promptDrawPending = false;
      });
    }
  }

  // Draw detections on canvas when detection completes in image mode
  // Only redraw if detection data actually changed (prevent infinite loop)
  $: if (
    sourceType === "image" &&
    detections &&
    imagePreview &&
    canvasElement &&
    detections !== lastDrawnDetection
  ) {
    lastDrawnDetection = detections;
    queueCanvasDraw(() => {
      drawDetections();
    });
  }

  // Draw image preview on canvas for image mode (before detection)
  // Only redraw if preview URL actually changed
  $: if (
    sourceType === "image" &&
    !detections &&
    imagePreview &&
    canvasElement &&
    galleryImages.length === 0 &&
    imagePreview !== lastDrawnImagePreview
  ) {
    lastDrawnImagePreview = imagePreview;
    queueCanvasDraw(() => {
      const ctx = canvasElement?.getContext("2d");
      if (ctx && imagePreview) {
        const img = new Image();
        img.onload = () => {
          canvasElement!.width = img.width;
          canvasElement!.height = img.height;
          ctx.drawImage(img, 0, 0);
        };
        img.src = imagePreview;
      }
    });
  }

  // Filters
  let selectedClasses: Set<string> = new Set();
  let availableClasses: string[] = [];
  let classFilter: string[] = []; // Pre-detection class filter
  let newClassTag = ""; // Input for adding new class filter tags

  // UI state
  let isTipsCollapsed = false; // Collapsible tips section

  // Zoom state
  let zoomLevel = 1;
  let isPanning = false;
  let panStart = { x: 0, y: 0 };
  let panOffset = { x: 0, y: 0 };

  // Animation & polling
  let animationFrameId: number | undefined;
  let pollingIntervalId: number | undefined;
  let webcamStream: MediaStream | null = null;

  // Reactive statement fix variables
  let webcamAbortController: AbortController | null = null; // RS3 fix
  let overlayUpdateTimer: number | null = null; // RS2 fix
  let canvasDrawQueue: Array<() => void> = []; // RS7+RS8 fix
  let canvasDrawing = false; // RS7+RS8 fix
  let lastDrawnDetection: PredictionResponse | null = null; // Prevent infinite loop
  let lastDrawnImagePreview: string | null = null; // Prevent unnecessary preview redraws

  // Sync local zoom/pan state with canvasStore
  $: zoomLevel = $canvasStore.zoomLevel;
  $: panOffset = $canvasStore.panOffset;

  // Sync local promptMode and inferPrompts with inferenceSettingsStore
  $: promptMode = $inferenceSettingsStore.promptMode;
  $: inferPrompts = $inferenceSettingsStore.inferPrompts || [];
  $: classFilter = $inferenceSettingsStore.classFilter || [];

  onMount(() => {
    // Load data asynchronously (fire and forget)
    (async () => {
      // Load campaign first if campaignId is provided
      if (campaignId) {
        await loadCampaign();
      }
      await loadModels();

      // PHASE 3: Restore last selected model from store persistence
      const lastModelId = $inferenceSettingsStore.selectedModelId;
      if (lastModelId && models.length > 0) {
        const lastModel = models.find((m) => m.id === lastModelId);
        if (lastModel) {
          console.log(
            "[onMount] Restoring last selected model:",
            lastModel.name,
          );
          selectedModelId = lastModelId;
          selectedModel = lastModel;
          promptRequired = lastModel.requires_prompts || false;
        }
      }
    })();

    // PHASE 3: Register canvas elements with canvasStore when useStores is enabled
    // This allows store-based drawing methods to work
    // Wait for next tick to ensure canvas elements are bound
    tick().then(() => {
      if (canvasElement) {
        canvasStore.setCanvas("main", canvasElement);
      }
      if (canvasOverlay) {
        canvasStore.setCanvas("overlay", canvasOverlay);
      }
      if (rtspCanvasElement) {
        canvasStore.setCanvas("rtsp", rtspCanvasElement);
      }
      if (rtspCanvasOverlay) {
        canvasStore.setCanvas("rtspOverlay", rtspCanvasOverlay);
      }
    });

    // Add keyboard listener for capture shortcut
    const handleKeyPress = (e: KeyboardEvent) => {
      // For video manual capture mode, prevent space bar from controlling video playback
      if (
        e.code === "Space" &&
        isDetecting &&
        sourceType === "video" &&
        videoCaptureMode === "manual"
      ) {
        e.preventDefault();
        e.stopPropagation();
        if (videoInferenceMode) {
          if (activeVideoSession && videoElement) {
            videoInferenceMode.captureFrame();
          } else {
            uiStore.showError(
              "No active video session. Please start inference first.",
              "Video Capture Error",
            );
          }
        }
        return;
      }

      if ((e.code === "Space" || e.code === "Enter") && isDetecting) {
        if (sourceType === "webcam" && webcamCaptureMode === "manual") {
          e.preventDefault();
          if (webcamInferenceMode) {
            webcamInferenceMode.captureFrame();
          } else {
            uiStore.showError(
              "No active webcam session. Please start inference first.",
              "Webcam Capture Error",
            );
          }
        } else if (sourceType === "rtsp" && rtspCaptureMode === "manual") {
          e.preventDefault();
          if (rtspInferenceMode) {
            rtspInferenceMode.captureFrame();
          } else {
            uiStore.showError(
              "No active RTSP session. Please start inference first.",
              "RTSP Capture Error",
            );
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyPress);

    return () => {
      window.removeEventListener("keydown", handleKeyPress);
    };
  });

  onDestroy(() => {
    cleanup();
  });

  async function loadCampaign() {
    if (!campaignId) return;

    try {
      campaign = await campaignsAPI.getCampaign(campaignId);
    } catch (error) {
      console.error("Failed to load campaign:", error);
      uiStore.showError(
        "Failed to load campaign details. Please try again later.",
        "Campaign Load Error",
      );
    }
  }

  async function loadModels() {
    try {
      let availableModels: any[] = [];

      if (playbookId) {
        // If playbookId is provided, load only models from that playbook
        const playbookModels = await playbooksAPI.getModels(playbookId);
        const playbookModelIds = playbookModels.map((pm) => pm.model_id);

        // Load all ready models and filter by playbook
        const allModels = await modelsAPI.list(0, 100);
        availableModels = allModels.filter(
          (m) => m.status === "ready" && playbookModelIds.includes(m.id),
        );
      } else {
        // Load all ready models (no playbook filter)
        const allModels = await modelsAPI.list(0, 100);
        availableModels = allModels.filter((m) => m.status === "ready");
      }

      models = availableModels;
    } catch (error) {
      console.error("Failed to load models:", error);
      uiStore.showError(
        "Failed to load models. Please try again later.",
        "Model Load Error",
      );
    }
  }

  // LEGACY FUNCTION REMOVED: handleModelSelect() - ModelSelector component handles this via handleComponentModelChange()

  // Event handler adapters for new components (Phase 1)
  function handleComponentModelChange(detail: {
    modelId: number;
    model: Model | null;
  }) {
    // ONLY update store - reactive block will sync to local variables
    // DO NOT update selectedModelId/selectedModel here to avoid race with reactive block
    inferenceSettingsStore.selectModel(detail.model);

    console.log(
      "[handleComponentModelChange] Called selectModel, store should now have:",
      $inferenceSettingsStore.selectedModelId,
      $inferenceSettingsStore.selectedModel?.name,
    );

    // ALSO update local variables since bind:selectedModelId depends on them
    selectedModelId = detail.modelId;
    selectedModel = detail.model;

    // Manually update promptRequired since we removed it from reactive block
    promptRequired = detail.model?.requires_prompts || false;
    if (promptRequired) {
      console.log(
        "[handleComponentModelChange] Updated local vars, promptRequired:",
        promptRequired,
      );
    } else {
      console.log(
        "          [handleComponentModelChange] Resetting prompts because model does not require them",
      );
      inferPrompts = [];
      promptMode = "auto";
    }

    // Load Smart Settings for this model (including confidence)
  }

  function handleComponentFileSelect(file: File) {
    selectedFile = file;
    if (sourceType === "image" && file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => {
        imagePreview = e.target?.result as string;
        // Update frame stats
        const img = new Image();
        img.onload = () => {
          frameStats.width = img.width;
          frameStats.height = img.height;
        };
        img.src = imagePreview;
      };
      reader.readAsDataURL(file);
    } else if (sourceType === "video" && file.type.startsWith("video/")) {
      const url = URL.createObjectURL(file);
      if (videoElement) {
        // Set crossOrigin to prevent canvas tainting
        videoElement.crossOrigin = "anonymous";
        videoElement.src = url;
        videoElement.onloadedmetadata = () => {
          frameStats.width = videoElement.videoWidth;
          frameStats.height = videoElement.videoHeight;
        };
      }
    }
  }

  function handleComponentFilesSelect(files: File[]) {
    selectedFiles = files;
  }

  function handleComponentClearPreview() {
    selectedFile = null;
    selectedFiles = [];
    imagePreview = null;
    galleryImages = [];
    currentGalleryIndex = 0;
    lastDrawnDetection = null;
    lastDrawnImagePreview = null;
  }

  function handleComponentGalleryClear() {
    galleryImages = [];
    selectedImageIndex = 0;
  }

  // Prompts Management Functions
  function addtextPrompt() {
    if (!textPrompt.trim()) return;

    const newPrompts: InferencePrompt[] = [
      ...inferPrompts,
      {
        type: "text" as const,
        value: textPrompt.trim(),
      },
    ];

    inferenceSettingsStore.setInferPrompts(newPrompts);

    textPrompt = ""; // Clear input
  }

  function removeInferencePrompt(index: number) {
    const newPrompts = inferPrompts.filter((_, i) => i !== index);

    inferenceSettingsStore.setInferPrompts(newPrompts);
  }

  function clearInferencePrompts() {
    inferenceSettingsStore.setInferPrompts([]);
    inferenceSettingsStore.setPromptMode("auto");
  }

  function handleCanvasClick(event: MouseEvent) {
    if (!canvasElement || !promptRequired) return;

    const rect = canvasElement.getBoundingClientRect();
    const canvasWidth = canvasElement.width;
    const canvasHeight = canvasElement.height;
    const rectWidth = rect.width;
    const rectHeight = rect.height;

    // Calculate accurate image coordinates with scaling
    const x = Math.round(
      (event.clientX - rect.left) * (canvasWidth / rectWidth),
    );
    const y = Math.round(
      (event.clientY - rect.top) * (canvasHeight / rectHeight),
    );

    if (promptMode === "point") {
      // Foreground point (green) by default, background (red) with Shift key
      const label = event.shiftKey ? 0 : 1;

      const newPrompts: InferencePrompt[] = [
        ...inferPrompts,
        {
          type: "point" as const,
          coords: [x, y],
          label,
        },
      ];

      inferenceSettingsStore.setInferPrompts(newPrompts);
    } else if (promptMode === "box") {
      if (!isDrawingBox) {
        // Start drawing box
        isDrawingBox = true;
        boxStartCoords = { x, y };
        tempBoxCoords = { x1: x, y1: y, x2: x, y2: y };
      } else {
        // Finish drawing box
        if (boxStartCoords) {
          const x1 = Math.min(boxStartCoords.x, x);
          const y1 = Math.min(boxStartCoords.y, y);
          const x2 = Math.max(boxStartCoords.x, x);
          const y2 = Math.max(boxStartCoords.y, y);

          const newPrompts: InferencePrompt[] = [
            ...inferPrompts,
            {
              type: "box" as const,
              coords: [x1, y1, x2, y2],
            },
          ];

          inferenceSettingsStore.setInferPrompts(newPrompts);
        }

        // Reset box drawing state
        isDrawingBox = false;
        boxStartCoords = null;
        tempBoxCoords = null;
      }
    }
  }

  function handleCanvasMouseMove(event: MouseEvent) {
    if (!canvasElement || !promptRequired || !isDrawingBox || !boxStartCoords)
      return;

    const rect = canvasElement.getBoundingClientRect();
    const canvasWidth = canvasElement.width;
    const canvasHeight = canvasElement.height;
    const rectWidth = rect.width;
    const rectHeight = rect.height;

    // Calculate accurate image coordinates with scaling
    const x = Math.round(
      (event.clientX - rect.left) * (canvasWidth / rectWidth),
    );
    const y = Math.round(
      (event.clientY - rect.top) * (canvasHeight / rectHeight),
    );

    // Update temp box preview
    tempBoxCoords = {
      x1: Math.min(boxStartCoords.x, x),
      y1: Math.min(boxStartCoords.y, y),
      x2: Math.max(boxStartCoords.x, x),
      y2: Math.max(boxStartCoords.y, y),
    };
  }

  async function stopInference() {
    try {
      console.log(
        "[stopInference] Called, sourceType:",
        sourceType,
        "isDetecting BEFORE:",
        isDetecting,
      );

      // Call stop on the active mode component
      if (sourceType === "image" && imageInferenceMode) {
        await imageInferenceMode.stopInference();
      } else if (sourceType === "batch" && batchInferenceMode) {
        await batchInferenceMode.stopInference();
      } else if (sourceType === "webcam" && webcamInferenceMode) {
        await webcamInferenceMode.stopInference();
      } else if (sourceType === "video" && videoInferenceMode) {
        await videoInferenceMode.stopInference();
      } else if (sourceType === "rtsp" && rtspInferenceMode) {
        await rtspInferenceMode.stopInference();
      }

      console.log(
        "[stopInference] Component stop complete, isDetecting:",
        isDetecting,
        "store isDetecting:",
        $inferenceJobStore.isDetecting,
      );

      // REMOVED: Don't set isDetecting here - let the callback handle it
      // The onDetectingChange callback already updates both store and local variable
      // Setting it here creates a race condition with the reactive statement
      // isDetecting = false;

      console.log(
        "[stopInference] After cleanup, isDetecting:",
        isDetecting,
        "galleryCount:",
        galleryImages.length,
      );
    } catch (error) {
      console.error("Failed to stop inference:", error);
      uiStore.showError("Failed to stop inference", "Stop Error");
    }
  }

  async function startPrediction() {
    if (!selectedModelId) {
      uiStore.showWarning("Please select a model first", "Model Required");
      return;
    }

    // PHASE 3: Use store to track detection state
    // Create a minimal job object for tracking
    const job: PredictionJob = {
      id: Date.now(), // Temporary ID until server responds
      model_id: selectedModelId,
      status: "running",
      created_at: new Date().toISOString(),
      source_type: sourceType,
    } as PredictionJob;
    inferenceJobStore.startJob(job);

    try {
      // Phase 2: Delegate to new mode components
      if (sourceType === "image" && imageInferenceMode) {
        await imageInferenceMode.startInference();
      } else if (sourceType === "batch" && batchInferenceMode) {
        await batchInferenceMode.startInference();
      } else if (sourceType === "webcam" && webcamInferenceMode) {
        // Switch to live mode BEFORE starting to ensure video element is available
        inferenceGalleryStore.setWebcamViewMode("live");
        // Wait for Svelte to update DOM and render video/canvas elements
        await tick();
        await webcamInferenceMode.startInference();
      } else if (sourceType === "video" && videoInferenceMode) {
        await videoInferenceMode.startInference();
      } else if (sourceType === "rtsp" && rtspInferenceMode) {
        // Switch to live mode BEFORE starting to ensure canvas elements are available
        inferenceGalleryStore.setRTSPViewMode("live");
        // Wait for Svelte to update DOM and render canvas elements
        await tick();
        await rtspInferenceMode.startInference();
      } else {
        if (sourceType === "rtsp") {
          uiStore.showWarning(
            "Please provide a valid RTSP URL!",
            "Input Required",
          );
        } else {
          uiStore.showWarning(
            "Please select a file to proceed!",
            "Input Required",
          );
        }
        isDetecting = false;
      }
    } catch (error) {
      console.error("Detection error:", error);
      uiStore.showError(
        "Detection failed. Please try again.",
        "Detection Error",
      );
      isDetecting = false;
    }
  }

  // LEGACY FUNCTIONS REMOVED (Phase 2 - Replaced by Mode Components):
  // - inferSingleImage() → ImageInferenceMode.startInference()
  // - inferBatchImage() → BatchInferenceMode.startInference()
  // - pollJobStatusForBatch() → BatchInferenceMode handles polling
  // - buildGalleryFromResults() → BatchInferenceMode handles gallery
  // - inferVideo() → VideoInferenceMode.startInference()
  // - startInactivityMonitoring() → VideoInferenceMode handles sessions
  // - finishVideoSession() → VideoInferenceMode handles cleanup
  // - continueSession() → VideoInferenceMode handles heartbeat
  // - startVideoManualDetection() → VideoInferenceMode handles preview
  // - pollVideoJobStatus() → VideoInferenceMode handles polling
  // - addVideoFrameToGallery() → VideoInferenceMode handles gallery
  // - inferRTSP() → RTSPInferenceMode.startInference()
  // - pollJobStatus() → RTSPInferenceMode handles polling
  // - stopRtspInference() → Unified stopInference()
  // - inferWebCam() → WebcamInferenceMode.startInference()
  // - startRealtimeCameraInference() → WebcamInferenceMode handles detection loop
  // - captureCurrentCameraFrame() → WebcamInferenceMode.captureFrame()
  // LEGACY FUNCTION REMOVED: captureCurrentRTSPFrame() - RTSPInferenceMode has own captureFrame() method

  function playShutterSound() {
    try {
      const audioContext = new (window.AudioContext ||
        (window as any).webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);

      oscillator.frequency.value = 800;
      oscillator.type = "sine";

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(
        0.01,
        audioContext.currentTime + 0.1,
      );

      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
      console.warn("Audio feedback not available:", error);
    }
  }

  // Continuously update video overlay with bounding boxes during playback
  function updateVideoOverlay() {
    if (
      !videoElement ||
      !canvasOverlay ||
      sourceType !== "video" ||
      videoCaptureMode !== "continuous" ||
      galleryImages.length === 0
    ) {
      return;
    }

    const currentTime = videoElement.currentTime;

    // Find the closest gallery item to current video timestamp
    let closestItem = galleryImages[0];
    let minDiff = Math.abs((closestItem.timestamp || 0) - currentTime);

    for (const item of galleryImages) {
      const diff = Math.abs((item.timestamp || 0) - currentTime);
      if (diff < minDiff) {
        minDiff = diff;
        closestItem = item;
      }
    }

    // Only draw if we have a reasonably close match (within 1 second)
    if (minDiff < 1.0 && closestItem.detectionData) {
      drawVideoFrameBoxes(closestItem.detectionData);
    } else {
      // Clear overlay if no close match
      const ctx = canvasOverlay.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);
      }
    }
  }

  function drawRTSPLiveFrame(frameData: PredictionResponseWithFrame) {
    if (!rtspCanvasElement || !rtspCanvasOverlay) return;

    const img = new Image();
    img.onload = () => {
      if (!rtspCanvasElement || !rtspCanvasOverlay) return; // Re-check in case of async load

      // Draw frame on main canvas
      const ctx = rtspCanvasElement.getContext("2d");
      if (ctx) {
        rtspCanvasElement.width = img.width;
        rtspCanvasElement.height = img.height;
        ctx.drawImage(img, 0, 0);
      }

      // Draw detections on overlay canvas
      const overlayCtx = rtspCanvasOverlay.getContext("2d");
      if (overlayCtx) {
        rtspCanvasOverlay.width = img.width;
        rtspCanvasOverlay.height = img.height;
        overlayCtx.clearRect(
          0,
          0,
          rtspCanvasOverlay.width,
          rtspCanvasOverlay.height,
        );
        drawBoundingBoxes(overlayCtx, frameData.predictions);
      }
    };
    img.src = frameData.frame;
  }

  function drawBoundingBoxes(
    ctx: CanvasRenderingContext2D,
    response: PredictionResponse,
  ) {
    // Use unified drawing utility
    drawInferenceResults(ctx, response, {
      showLabels: true,
      showConfidence: true,
      selectedClasses: selectedClasses.size > 0 ? selectedClasses : undefined,
    });
  }

  function updateCurrentFrameStats(detectionData: PredictionResponse) {
    // Use unified processing utility
    const canvasWidth = canvasElement?.width || 0;
    const canvasHeight = canvasElement?.height || 0;
    const videoFps = videoElement?.playbackRate ? 30 : undefined;

    const processed = processInferenceResponse(
      detectionData,
      canvasWidth,
      canvasHeight,
      videoFps,
    );

    detectionResults = processed.detectionResults;
    classCounts = processed.classCounts;
    availableClasses = processed.availableClasses;
    frameStats = processed.frameStats;

    // Draw bounding boxes on video canvas if in video mode
    if (sourceType === "video" && canvasElement && videoElement) {
      drawVideoFrameBoxes(detectionData);
    }
  }

  function drawVideoFrameBoxes(detectionData: PredictionResponse) {
    if (!canvasOverlay || !videoElement) return;

    const ctx = canvasOverlay.getContext("2d");
    if (!ctx) return;

    // Set overlay canvas size to match displayed video element size
    const rect = videoElement.getBoundingClientRect();
    canvasOverlay.width = rect.width;
    canvasOverlay.height = rect.height;

    // Clear previous drawings
    ctx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);

    // Calculate scaling factors
    const scaleX = rect.width / videoElement.videoWidth;
    const scaleY = rect.height / videoElement.videoHeight;

    // Draw bounding boxes with scaling
    drawInferenceResultsScaled(ctx, detectionData, scaleX, scaleY, {
      showLabels: true,
      showConfidence: true,
      selectedClasses: selectedClasses.size > 0 ? selectedClasses : undefined,
    });
  }

  function drawDetections() {
    if (!canvasElement || !detections || !imagePreview) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvasElement.width = img.width;
      canvasElement.height = img.height;
      ctx.drawImage(img, 0, 0);

      // Use unified drawing utility
      drawInferenceResults(ctx, detections!, {
        showLabels: true,
        showConfidence: true,
        selectedClasses: selectedClasses.size > 0 ? selectedClasses : undefined,
      });
    };
    img.src = imagePreview;
  }

  function drawInferencePrompts() {
    if (!canvasElement || !promptRequired) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const rect = canvasElement.getBoundingClientRect();
    const canvasWidth = canvasElement.width;
    const canvasHeight = canvasElement.height;
    const rectWidth = rect.width;
    const rectHeight = rect.height;

    // Draw existing prompts
    inferPrompts.forEach((prompt) => {
      if (prompt.type === "point") {
        // Scale coordinates for rendering
        if (!prompt.coords || prompt.coords.length < 2) return;
        const coords = prompt.coords;
        const x = (coords[0] * rectWidth) / canvasWidth;
        const y = (coords[1] * rectHeight) / canvasHeight;

        ctx.fillStyle = prompt.label === 1 ? "#22c55e" : "#ef4444"; // Green for foreground, red for background
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fill();

        // Draw outline
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (prompt.type === "box") {
        // Scale coordinates for rendering
        if (!prompt.coords || prompt.coords.length < 4) return;
        const coords = prompt.coords;
        const x1 = (coords[0] * rectWidth) / canvasWidth;
        const y1 = (coords[1] * rectHeight) / canvasHeight;
        const x2 = (coords[2] * rectWidth) / canvasWidth;
        const y2 = (coords[3] * rectHeight) / canvasHeight;

        ctx.strokeStyle = "#3b82f6"; // Blue for boxes
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

        // Draw corner handles
        const handleSize = 8;
        ctx.fillStyle = "#3b82f6";
        [
          [x1, y1],
          [x2, y1],
          [x1, y2],
          [x2, y2],
        ].forEach(([hx, hy]) => {
          ctx.fillRect(
            hx - handleSize / 2,
            hy - handleSize / 2,
            handleSize,
            handleSize,
          );
        });
      }
    });

    // Draw temp box preview
    if (tempBoxCoords && isDrawingBox) {
      const x1 = (tempBoxCoords.x1 * rectWidth) / canvasWidth;
      const y1 = (tempBoxCoords.y1 * rectHeight) / canvasHeight;
      const x2 = (tempBoxCoords.x2 * rectWidth) / canvasWidth;
      const y2 = (tempBoxCoords.y2 * rectHeight) / canvasHeight;

      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.setLineDash([]);
    }
  }

  function resetDetection() {
    cleanup();

    // Stop all inference mode components to clear their internal state
    if (imageInferenceMode) imageInferenceMode.stopInference?.();
    if (batchInferenceMode) batchInferenceMode.stopInference?.();
    if (webcamInferenceMode) webcamInferenceMode.stopInference?.();
    if (videoInferenceMode) videoInferenceMode.stopInference?.();
    if (rtspInferenceMode) rtspInferenceMode.stopInference?.();

    // Reset internal state of mode components (clear galleries, etc.)
    if (imageInferenceMode) imageInferenceMode.resetState?.();
    if (batchInferenceMode) batchInferenceMode.resetState?.();
    if (webcamInferenceMode) webcamInferenceMode.resetState?.();
    if (videoInferenceMode) videoInferenceMode.resetState?.();
    if (rtspInferenceMode) rtspInferenceMode.resetState?.();

    selectedFile = null;
    selectedFiles = [];
    imagePreview = null;
    detections = null;
    lastDrawnDetection = null;
    lastDrawnImagePreview = null;
    detectionResults = [];
    rtspLastFrameData = null;
    processedFrameNumbers.clear();
    classCounts = {};
    currentJob = null;
    isDetecting = false;
    rtspUrl = "";
    galleryImages = [];
    currentGalleryIndex = 0;
    selectedClasses.clear();
    selectedClasses = selectedClasses; // Trigger Svelte reactivity
    availableClasses = []; // Clear available classes from previous detection

    // Clear file input to allow re-selection
    if (fileInputElement) {
      fileInputElement.value = "";
    }

    // Clear main canvas (original frame)
    if (canvasElement) {
      const ctx = canvasElement.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvasElement.width, canvasElement.height);
      }
    }

    // Clear canvas overlay (bounding boxes and masks for video)
    if (canvasOverlay) {
      const overlayCtx = canvasOverlay.getContext("2d");
      if (overlayCtx) {
        overlayCtx.clearRect(0, 0, canvasOverlay.width, canvasOverlay.height);
      }
    }

    // Clear RTSP canvas overlay
    if (rtspCanvasOverlay) {
      const rtspOverlayCtx = rtspCanvasOverlay.getContext("2d");
      if (rtspOverlayCtx) {
        rtspOverlayCtx.clearRect(
          0,
          0,
          rtspCanvasOverlay.width,
          rtspCanvasOverlay.height,
        );
      }
    }

    // Clear RTSP canvas element
    if (rtspCanvasElement) {
      const rtspCtx = rtspCanvasElement.getContext("2d");
      if (rtspCtx) {
        rtspCtx.clearRect(
          0,
          0,
          rtspCanvasElement.width,
          rtspCanvasElement.height,
        );
      }
    }

    // Clear video element source (prevents sticky frames)
    if (videoElement) {
      videoElement.pause();
      videoElement.src = "";
      videoElement.load(); // Reset video element
    }

    // Clear stores
    inferenceGalleryStore.reset();
    inferenceJobStore.completeJob();
  }

  function cleanup() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
    }
    if (videoDetectionIntervalId) {
      clearInterval(videoDetectionIntervalId);
      videoDetectionIntervalId = null;
    }
    if (webcamStream) {
      webcamStream.getTracks().forEach((track) => track.stop());
      webcamStream = null;
    }
  }

  function toggleClassFilter(className: string) {
    if (selectedClasses.has(className)) {
      selectedClasses.delete(className);
    } else {
      selectedClasses.add(className);
    }
    selectedClasses = selectedClasses;
    drawDetections();
  }
</script>

<!-- Inference Mode Components (Headless) -->
{#if sourceType === "image"}
  <ImageInferenceMode
    bind:this={imageInferenceMode}
    {selectedModelId}
    selectedFile={selectedFile ?? undefined}
    {imagePreview}
    {confidence}
    {classFilter}
    {inferPrompts}
    {promptMode}
    {promptRequired}
    {campaignId}
    {canvasElement}
    onDetectionComplete={(response) => {
      detections = response;
      updateCurrentFrameStats(response);
    }}
    onGalleryUpdate={(images) => {
      inferenceGalleryStore.reset();
      images.forEach((img) => inferenceGalleryStore.addImage(img));
    }}
    onDetectingChange={(detecting) => {
      // Update store instead of local variable to prevent sync conflict
      if (detecting) {
        const job: PredictionJob = {
          id: Date.now(),
          model_id: selectedModelId!,
          status: "running",
          created_at: new Date().toISOString(),
          source_type: sourceType,
        } as PredictionJob;
        inferenceJobStore.startJob(job);
      } else {
        inferenceJobStore.completeJob();
      }
      isDetecting = detecting;
    }}
    onError={(error) => {
      uiStore.showError(error.message, "Detection Error");
      inferenceJobStore.completeJob();
    }}
  />
{:else if sourceType === "batch"}
  <BatchInferenceMode
    bind:this={batchInferenceMode}
    {selectedModelId}
    {selectedFiles}
    {confidence}
    classFilter={Array.from(selectedClasses)}
    {inferPrompts}
    {promptMode}
    {promptRequired}
    {campaignId}
    onJobUpdate={(job) => {
      currentJob = job;
      batchProcessingProgress = {
        current: job.progress || 0,
        total: selectedFiles.length,
        fileName: "",
      };
    }}
    onGalleryUpdate={(images) => {
      galleryImages = images;
    }}
    onDetectingChange={(detecting) => {
      isDetecting = detecting;
    }}
    onError={(error) => {
      uiStore.showError(error.message, "Batch Detection Error");
      isDetecting = false;
    }}
  />
{:else if sourceType === "webcam"}
  <WebcamInferenceMode
    bind:this={webcamInferenceMode}
    {selectedModelId}
    {selectedModel}
    {confidence}
    classFilter={Array.from(selectedClasses)}
    {inferPrompts}
    {promptRequired}
    captureMode={webcamCaptureMode}
    {campaignId}
    {videoElement}
    {canvasElement}
    {canvasOverlay}
    onSessionStart={(session) => {
      activeWebcamSession = session;
      // Auto-switch to Live view when starting session (prevents canvas errors)
      inferenceGalleryStore.setWebcamViewMode("live");
    }}
    onFrameCaptured={() => {
      isFlashing = true;
      setTimeout(() => (isFlashing = false), 200);
    }}
    onGalleryUpdate={(images) => {
      inferenceGalleryStore.reset();
      images.forEach((img) => inferenceGalleryStore.addImage(img));
      console.log(
        "[Webcam Parent] Updated inferenceGalleryStore with",
        images.length,
        "images",
      );
      galleryImages = images;
    }}
    onStatsUpdate={(stats) => {
      // Mode component emits ProcessedResults, extract the data
      detectionResults = stats.detectionResults;
      classCounts = stats.classCounts;
      availableClasses = stats.availableClasses;
      frameStats = stats.frameStats;
    }}
    onDetectingChange={(detecting) => {
      if (detecting) {
        const job: PredictionJob = {
          id: activeWebcamSession?.id || Date.now(),
          model_id: selectedModelId!,
          status: "running",
          created_at: new Date().toISOString(),
          source_type: sourceType,
        } as PredictionJob;
        inferenceJobStore.startJob(job);
        console.log("[Webcam Parent] Job store updated to running");
      } else {
        inferenceJobStore.completeJob();
        console.log("[Webcam Parent] Job store updated to completed");
      }
      isDetecting = detecting;
    }}
    onError={(error) => {
      uiStore.showError(error.message, "Webcam Error");
      inferenceJobStore.completeJob();
    }}
    onFlash={() => {
      isFlashing = true;
      setTimeout(() => (isFlashing = false), 300);
    }}
    onShutterSound={() => {
      playShutterSound();
    }}
  />
{:else if sourceType === "video"}
  <VideoInferenceMode
    bind:this={videoInferenceMode}
    {selectedModelId}
    {selectedModel}
    selectedFile={selectedFile ?? undefined}
    {confidence}
    classFilter={Array.from(selectedClasses)}
    {inferPrompts}
    {promptRequired}
    captureMode={videoCaptureMode}
    skipFrames={$inferenceSettingsStore.skipFrames}
    {campaignId}
    {videoElement}
    {canvasElement}
    {canvasOverlay}
    onSessionStart={(session) => {
      activeVideoSession = session;
    }}
    onFrameCaptured={() => {
      // Video frame captured
    }}
    onJobUpdate={(job) => {
      currentJob = job;
    }}
    onGalleryUpdate={(images) => {
      console.log(
        "[Parent] onGalleryUpdate called with",
        images.length,
        "images",
      );
      // Update store
      inferenceGalleryStore.reset();
      images.forEach((img) => inferenceGalleryStore.addImage(img));
      console.log(
        "[Parent] Gallery store updated, length:",
        $inferenceGalleryStore.images.length,
      );
      // CRITICAL: Also update local variable for UI reactivity
      galleryImages = images;
    }}
    onStatsUpdate={(stats) => {
      console.log("[Parent] onStatsUpdate called");
      // Mode component emits ProcessedResults, extract the data
      detectionResults = stats.detectionResults;
      classCounts = stats.classCounts;
      availableClasses = stats.availableClasses;
      frameStats = stats.frameStats;
    }}
    onDetectingChange={(detecting) => {
      console.log("[Parent] onDetectingChange called, detecting:", detecting);
      // Update store
      if (detecting) {
        const job: PredictionJob = {
          id: currentJob?.id || Date.now(),
          model_id: selectedModelId!,
          status: "running",
          created_at: new Date().toISOString(),
          source_type: sourceType,
        } as PredictionJob;
        inferenceJobStore.startJob(job);
        console.log("[Parent] Job store updated to running");
      } else {
        inferenceJobStore.completeJob();
        console.log("[Parent] Job store updated to completed");
      }
      // CRITICAL: Also update local variable for UI reactivity
      isDetecting = detecting;
    }}
    onInactivityWarning={(show) => {
      showInactivityModal = show;
    }}
    onError={(error) => {
      uiStore.showError(error.message, "Video Error");
      isDetecting = false;
    }}
    onFlash={() => {
      isFlashing = true;
      setTimeout(() => (isFlashing = false), 300);
    }}
    onShutterSound={() => {
      playShutterSound();
    }}
  />
{:else if sourceType === "rtsp"}
  <RTSPInferenceMode
    bind:this={rtspInferenceMode}
    {selectedModelId}
    {selectedModel}
    {rtspUrl}
    {confidence}
    classFilter={Array.from(selectedClasses)}
    {inferPrompts}
    {promptRequired}
    captureMode={rtspCaptureMode}
    skipFrames={$inferenceSettingsStore.skipFrames}
    {campaignId}
    canvasElement={rtspCanvasElement}
    canvasOverlay={rtspCanvasOverlay}
    onSessionStart={(session) => {
      currentJob = session;
      rtspFrameStatus = "loading"; // Reset status for new session
      // Auto-switch to Live view when starting session (prevents canvas errors)
      rtspViewMode = "live"; // Update local variable for UI reactivity
      inferenceGalleryStore.setRTSPViewMode("live");
    }}
    onFrameCaptured={() => {
      // RTSP frame captured
    }}
    onJobUpdate={(job) => {
      currentJob = job;
    }}
    onGalleryUpdate={(images) => {
      inferenceGalleryStore.reset();
      images.forEach((img) => inferenceGalleryStore.addImage(img));
      console.log(
        "[RTSP Parent] Updated inferenceGalleryStore with",
        images.length,
        "images",
      );
      // Also update local variable immediately to avoid race condition
      galleryImages = images;
    }}
    onStatsUpdate={(stats) => {
      // Mode component emits ProcessedResults, extract the data
      detectionResults = stats.detectionResults;
      classCounts = stats.classCounts;
      availableClasses = stats.availableClasses;
      frameStats = stats.frameStats;

      // Mark frame as ready when we receive stats (frames are being processed)
      if (rtspFrameStatus === "loading") {
        rtspFrameStatus = "ready";
      }
    }}
    onDetectingChange={(detecting) => {
      isDetecting = detecting;

      if (!currentJob) return;
      // Update store if enabled
      if (detecting) {
        inferenceJobStore.startJob(currentJob);
      } else {
        inferenceJobStore.completeJob();
      }
    }}
    onError={(error) => {
      uiStore.showError(error.message, "RTSP Error");
      isDetecting = false;

      // Update store if enabled
      inferenceJobStore.completeJob();
    }}
    onFlash={() => {
      isFlashing = true;
      setTimeout(() => (isFlashing = false), 300);
    }}
    onShutterSound={() => {
      playShutterSound();
    }}
  />
{/if}

<div class="detection-page">
  <!-- Header -->
  <header class="detection-header">
    <div class="header-left">
      <h1>New Prediction</h1>
    </div>
  </header>

  <!-- Main Content -->
  <div class="detection-content">
    <!-- Video/Image Area -->
    <div class="media-area">
      <!-- Mode Switchers -->

      <!-- Phase 2: New ViewModeSwitcher Component -->
      {#if sourceType === "rtsp"}
        <ViewModeSwitcher
          sourceType="rtsp"
          viewMode={rtspViewMode}
          galleryCount={galleryImages.length}
          {isDetecting}
          isRecording={isDetecting && rtspViewMode !== "live"}
          onModeChange={(detail) => {
            rtspViewMode = detail.mode; // Update local variable for UI reactivity
            inferenceGalleryStore.setRTSPViewMode(detail.mode);
          }}
        />
      {:else if sourceType === "webcam"}
        <ViewModeSwitcher
          sourceType="webcam"
          viewMode={webcamViewMode}
          galleryCount={galleryImages.length}
          {isDetecting}
          isRecording={isDetecting && webcamViewMode !== "live"}
          onModeChange={(detail) => {
            webcamViewMode = detail.mode; // Update local variable for UI reactivity
            inferenceGalleryStore.setWebcamViewMode(detail.mode);
          }}
        />
      {/if}

      <!-- Phase 2: MediaDisplay Component handles all source types -->
      <MediaDisplay
        {sourceType}
        {galleryImages}
        {currentGalleryIndex}
        {zoomLevel}
        bind:panOffset
        bind:isPanning
        bind:panStart
        bind:videoElement
        bind:canvasElement
        bind:canvasOverlay
        bind:isFlashing
        {rtspViewMode}
        bind:rtspCanvasElement
        bind:rtspCanvasOverlay
        {rtspFrameStatus}
        {rtspCaptureMode}
        {promptRequired}
        bind:rtsp_viewer
        {rtspUrl}
        {selectedModelId}
        {inferPrompts}
        {webcamViewMode}
        {videoCaptureMode}
        onUpdateOverlay={updateVideoOverlay}
      />

      <!-- Navigation arrows for gallery (image/batch mode) -->
      {#if galleryImages.length > 1 && (sourceType === "image" || sourceType === "batch")}
        <button
          class="gallery-nav gallery-nav-prev"
          on:click={() =>
            (currentGalleryIndex = Math.max(0, currentGalleryIndex - 1))}
          disabled={currentGalleryIndex === 0}
        >
          ‹
        </button>
        <button
          class="gallery-nav gallery-nav-next"
          on:click={() =>
            (currentGalleryIndex = Math.min(
              galleryImages.length - 1,
              currentGalleryIndex + 1,
            ))}
          disabled={currentGalleryIndex === galleryImages.length - 1}
        >
          ›
        </button>
      {/if}

      <!-- Image Gallery Controls (thumbnails and indicators) -->
      {#if sourceType === "webcam" && webcamViewMode === "gallery" && galleryImages.length > 0}
        <!-- NEW: CaptureGallery Component for Webcam Thumbnails -->
        <CaptureGallery
          images={galleryImages}
          bind:selectedIndex={currentGalleryIndex}
          showMainPreview={false}
          onSelect={(index) => {
            inferenceGalleryStore.navigate(index);
          }}
          onClear={handleComponentGalleryClear}
        />
      {:else if sourceType === "rtsp" && rtspViewMode === "gallery" && galleryImages.length > 0}
        <!-- NEW: CaptureGallery Component for RTSP Thumbnails -->
        <CaptureGallery
          images={galleryImages}
          bind:selectedIndex={currentGalleryIndex}
          showMainPreview={false}
          onSelect={(index) => {
            inferenceGalleryStore.navigate(index);
          }}
          onClear={handleComponentGalleryClear}
        />
      {:else if galleryImages.length > 1 && (sourceType === "image" || sourceType === "batch" || sourceType === "video")}
        <div class="gallery-controls">
          <div class="gallery-thumbnails">
            {#each galleryImages as image, idx}
              <button
                class="gallery-thumbnail {idx === currentGalleryIndex
                  ? 'active'
                  : ''}"
                on:click={() => {
                  currentGalleryIndex = idx;
                  inferenceGalleryStore.navigate(idx);
                }}
                title={image.timestamp !== undefined
                  ? `Time: ${image.timestamp.toFixed(1)}s`
                  : image.fileName}
              >
                <img src={image.annotated} alt="Thumbnail {idx + 1}" />
                {#if image.timestamp !== undefined}
                  <span class="thumbnail-timestamp"
                    >{image.timestamp.toFixed(1)}s</span
                  >
                {/if}
              </button>
            {/each}
          </div>

          <div class="gallery-indicators">
            {#each galleryImages as _, idx}
              <button
                class="indicator {idx === currentGalleryIndex ? 'active' : ''}"
                on:click={() => {
                  currentGalleryIndex = idx;
                  inferenceGalleryStore.navigate(idx);
                }}
                aria-label="Go to image {idx + 1}"
              ></button>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Detection Results -->

      <!-- NEW: StatsPanel Component -->
      <StatsPanel
        {detectionResults}
        showFrameStats={sourceType === "video" ||
          sourceType === "webcam" ||
          sourceType === "rtsp"}
        frameWidth={frameStats.width}
        frameHeight={frameStats.height}
        fps={frameStats.fps}
      />
    </div>

    <!-- Right Sidebar -->
    <aside class="control-sidebar">
      <!-- Detection Controls -->
      <section class="control-section">
        <h3>Controls</h3>

        <!-- NEW: ModelSelector Component -->
        <ModelSelector
          {models}
          bind:selectedModelId
          {selectedModel}
          disabled={isDetecting}
          showTaskInstructions={true}
          onModelChange={handleComponentModelChange}
        />

        <!-- NEW: SourceTypeSelector Component -->
        <SourceTypeSelector bind:sourceType disabled={isDetecting} />

        {#if sourceType === "rtsp"}
          <div class="form-group">
            <label>
              <span>RTSP URL:</span>
              <input
                type="text"
                bind:value={rtspUrl}
                placeholder="rtsp://..."
                disabled={isDetecting}
              />
            </label>
          </div>
          <!-- RTSP Capture Mode Toggle -->
          <div class="form-group">
            <div style="margin-bottom: 0.5rem; display: block;">
              <span
                style="font-size: 0.875rem; color: var(--color-text-secondary);"
                >Capture Mode:</span
              >
            </div>
            <div class="segmented-control" style="margin-bottom: 0.5rem;">
              <button
                class="segment"
                class:active={rtspCaptureMode === "manual"}
                on:click={() => (rtspCaptureMode = "manual")}
                disabled={isDetecting}
              >
                📸 Manual Capture
              </button>
              <button
                class="segment"
                class:active={rtspCaptureMode === "continuous"}
                on:click={() => (rtspCaptureMode = "continuous")}
                disabled={isDetecting}
              >
                📹 Continuous Recording
              </button>
            </div>
            {#if rtspCaptureMode === "continuous"}
              <p
                class="warning-text"
                style="font-size: 0.8rem; color: #ff9500; margin: 0.5rem 0 0 0;"
              >
                ⚠️ Continuous mode stores unlimited frames. Storage costs may
                apply.
              </p>
            {/if}
          </div>
        {:else if sourceType === "webcam"}
          <!-- Capture Mode Toggle -->
          <div class="form-group">
            <div style="margin-bottom: 0.5rem; display: block;">
              <span
                style="font-size: 0.875rem; color: var(--color-text-secondary);"
                >Capture Mode:</span
              >
            </div>
            <div class="segmented-control" style="margin-bottom: 0.5rem;">
              <button
                class="segment"
                class:active={webcamCaptureMode === "manual"}
                on:click={() => (webcamCaptureMode = "manual")}
                disabled={isDetecting}
              >
                📸 Manual Capture
              </button>
              <button
                class="segment"
                class:active={webcamCaptureMode === "continuous"}
                on:click={() => (webcamCaptureMode = "continuous")}
                disabled={isDetecting}
              >
                📹 Continuous Recording
              </button>
            </div>
          </div>
        {:else}
          <!-- NEW: FileUploadControl Component -->
          <FileUploadControl
            {sourceType}
            {selectedFile}
            {selectedFiles}
            {imagePreview}
            disabled={isDetecting}
            onFileSelect={handleComponentFileSelect}
            onFilesSelect={handleComponentFilesSelect}
            onClearPreview={handleComponentClearPreview}
          />

          <!-- Video Capture Mode Toggle -->
          {#if sourceType === "video" && selectedFile}
            <div class="form-group">
              <div style="margin-bottom: 0.5rem; display: block;">
                <span
                  style="font-size: 0.875rem; color: var(--color-text-secondary);"
                  >Detection Mode:</span
                >
              </div>
              <div class="segmented-control" style="margin-bottom: 0.5rem;">
                <button
                  class="segment"
                  class:active={videoCaptureMode === "manual"}
                  on:click={() => (videoCaptureMode = "manual")}
                  disabled={isDetecting}
                >
                  📸 Manual Capture
                </button>
                <button
                  class="segment"
                  class:active={videoCaptureMode === "continuous"}
                  on:click={() => (videoCaptureMode = "continuous")}
                  disabled={isDetecting}
                >
                  🎬 Detect All Frames
                </button>
              </div>
              {#if videoCaptureMode === "manual"}
                <p
                  class="help-text"
                  style="font-size: 0.8rem; margin: 0.5rem 0 0 0;"
                >
                  Use video controls to navigate, then capture frames with Space
                  bar
                </p>
              {:else}
                <p
                  class="help-text"
                  style="font-size: 0.8rem; margin: 0.5rem 0 0 0;"
                >
                  Processes video in background using Skip Frames setting
                </p>
              {/if}
            </div>
          {/if}
        {/if}

        <!-- Batch Progress Indicator -->
        {#if promptRequired && sourceType === "batch" && isDetecting && batchProcessingProgress.total > 0}
          <div class="batch-progress-indicator">
            <div class="progress-header">
              <span>Processing...</span>
              <span class="progress-count"
                >{batchProcessingProgress.current} / {batchProcessingProgress.total}</span
              >
            </div>
            <div class="progress-bar">
              <div
                class="progress-fill"
                style="width: {(batchProcessingProgress.current /
                  batchProcessingProgress.total) *
                  100}%"
              ></div>
            </div>
            <p class="progress-file">{batchProcessingProgress.fileName}</p>
          </div>
        {/if}

        <!-- NEW: CaptureControls Component -->
        <CaptureControls
          {sourceType}
          captureMode={sourceType === "video"
            ? videoCaptureMode
            : sourceType === "rtsp"
              ? rtspCaptureMode
              : sourceType === "webcam"
                ? webcamCaptureMode
                : "manual"}
          {isDetecting}
          hasFile={sourceType === "batch"
            ? selectedFiles.length > 0
            : selectedFile !== null}
          hasUrl={rtspUrl.trim() !== ""}
          onStart={startPrediction}
          onStop={stopInference}
          onCapture={() => {
            console.log("[Parent onCapture] Called - sourceType:", sourceType);
            // Phase 2: Delegate to mode components
            if (sourceType === "webcam" && webcamInferenceMode) {
              console.log(
                "[Parent onCapture] Calling webcamInferenceMode.captureFrame()",
              );
              webcamInferenceMode.captureFrame();
            } else if (sourceType === "video" && videoInferenceMode) {
              console.log(
                "[Parent onCapture] Calling videoInferenceMode.captureFrame()",
              );
              videoInferenceMode.captureFrame();
            } else if (sourceType === "rtsp" && rtspInferenceMode) {
              console.log(
                "[Parent onCapture] Calling rtspInferenceMode.captureFrame()",
              );
              rtspInferenceMode.captureFrame();
            }
          }}
          onReset={resetDetection}
        />
      </section>

      <!-- Smart Settings -->
      <section class="control-section">
        <h3>Smart Settings</h3>

        <!-- SmartSettingsPanel -->
        <SmartSettingsPanel
          confidence={$inferenceSettingsStore.confidence}
          classFilter={$inferenceSettingsStore.classFilter}
          skipFrames={$inferenceSettingsStore.skipFrames}
          disabled={isDetecting}
          showSkipFrames={sourceType === "video" || sourceType === "rtsp"}
          onConfidenceChange={(val) =>
            inferenceSettingsStore.setConfidence(val)}
          onClassFilterChange={(val) =>
            inferenceSettingsStore.setClassFilter(val)}
          onSkipFramesChange={(val) =>
            inferenceSettingsStore.setSkipFrames(val)}
        />

        <!-- Unified Prompt Controls (all source types) -->
        {#if promptRequired && selectedModelId}
          <div class="segment-controls">
            <div class="section-header">
              <span>🎭 Prompts</span>
            </div>

            <!-- Prompt Validation Banner -->
            {#if promptMode !== "auto" && inferPrompts.length === 0}
              <div class="warning-box" style="margin-bottom: 0.75rem;">
                ⚠️ This model requires at least one prompt. Add a {promptMode} prompt
                below.
              </div>
            {/if}

            <!-- Prompt Mode Selector -->
            <div class="prompt-mode-selector">
              <!-- Auto mode only for image/batch -->
              {#if sourceType === "image" || sourceType === "batch"}
                <button
                  class="prompt-mode-btn {promptMode === 'auto'
                    ? 'active'
                    : ''}"
                  on:click={() => inferenceSettingsStore.setPromptMode("auto")}
                  disabled={isDetecting}
                  type="button"
                >
                  🤖 Auto
                </button>
              {/if}

              <!-- Text mode for all sources -->
              <button
                class="prompt-mode-btn {promptMode === 'text' ? 'active' : ''}"
                on:click={() => inferenceSettingsStore.setPromptMode("text")}
                disabled={isDetecting}
                type="button"
              >
                ✍️ Text
              </button>

              <!-- Point mode only for image/batch/video (not webcam/rtsp) -->
              <button
                class="prompt-mode-btn {promptMode === 'point' ? 'active' : ''}"
                on:click={() => inferenceSettingsStore.setPromptMode("point")}
                disabled={isDetecting ||
                  sourceType === "webcam" ||
                  sourceType === "rtsp"}
                type="button"
              >
                📍 Point
              </button>

              <!-- Box mode only for image/batch/video (not webcam/rtsp) -->
              <button
                class="prompt-mode-btn {promptMode === 'box' ? 'active' : ''}"
                on:click={() => inferenceSettingsStore.setPromptMode("box")}
                disabled={isDetecting ||
                  sourceType === "webcam" ||
                  sourceType === "rtsp"}
                type="button"
              >
                ⬜ Box
              </button>
            </div>

            <!-- Mode-specific help text -->
            <p class="help-text prompt-hint">
              {#if promptMode === "auto"}
                🤖 No prompts needed - automatically segments all objects
              {:else if promptMode === "text"}
                ✍️ Describe what to segment (e.g., "person", "car", "building")
              {:else if promptMode === "point"}
                📍 Click on {sourceType === "video" ? "video frame" : "canvas"} to
                add points • Shift+Click for background
              {:else if promptMode === "box"}
                ⬜ Click and drag on {sourceType === "video"
                  ? "video frame"
                  : "canvas"} to draw bounding boxes
              {/if}
            </p>

            <!-- Text Prompt Input -->
            {#if promptMode === "text"}
              <div class="text-prompt-input">
                <input
                  type="text"
                  placeholder="e.g., person, car, tree"
                  bind:value={textPrompt}
                  disabled={isDetecting}
                  on:keydown={(e) => {
                    if (e.key === "Enter" && textPrompt.trim()) {
                      e.preventDefault();
                      addtextPrompt();
                    }
                  }}
                />
                <button
                  class="btn btn-sm btn-accent"
                  on:click={addtextPrompt}
                  disabled={isDetecting || !textPrompt.trim()}
                  type="button"
                >
                  Add
                </button>
              </div>
            {/if}

            <!-- Prompts List -->
            {#if inferPrompts.length > 0}
              <div class="prompts-list">
                <div class="prompts-header">
                  <span>Added Prompts ({inferPrompts.length})</span>
                  <button
                    class="btn-clear"
                    on:click={clearInferencePrompts}
                    disabled={isDetecting}
                    type="button"
                    title="Clear all prompts"
                  >
                    Clear All
                  </button>
                </div>
                <div class="prompts-items">
                  {#each inferPrompts as prompt, index}
                    <div class="prompt-item">
                      {#if prompt.type === "text"}
                        <span class="prompt-icon">✍️</span>
                        <span class="prompt-label">"{prompt.value}"</span>
                      {:else if prompt.type === "point"}
                        <span
                          class="prompt-icon"
                          style="color: {prompt.label === 1
                            ? '#22c55e'
                            : '#ef4444'}"
                        >
                          {prompt.label === 1 ? "●" : "●"}
                        </span>
                        <span class="prompt-label">
                          {prompt.label === 1 ? "Foreground" : "Background"} ({prompt
                            .coords?.[0] || 0}, {prompt.coords?.[1] || 0})
                        </span>
                      {:else if prompt.type === "box"}
                        <span class="prompt-icon">⬜</span>
                        <span class="prompt-label">
                          Box ({prompt.coords?.[0] || 0}, {prompt.coords?.[1] ||
                            0}) → ({prompt.coords?.[2] || 0}, {prompt
                            .coords?.[3] || 0})
                        </span>
                      {/if}
                      <button
                        class="btn-remove"
                        on:click={() => removeInferencePrompt(index)}
                        disabled={isDetecting}
                        type="button"
                        title="Remove prompt"
                      >
                        ×
                      </button>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}

        {#if (galleryImages.length > 0 || (sourceType === "image" && (imagePreview || detections))) && (sourceType === "image" || sourceType === "batch" || sourceType === "video" || (sourceType === "webcam" && webcamViewMode === "gallery") || (sourceType === "rtsp" && rtspViewMode === "gallery"))}
          <div class="zoom-control">
            <label>
              <span>Zoom: {zoomLevel.toFixed(1)}x</span>
              <input
                type="range"
                min="1"
                max="5"
                step="0.1"
                value={zoomLevel}
                on:input={(e) => {
                  const newZoom = parseFloat(e.currentTarget.value);
                  canvasStore.setZoom(newZoom);
                  if (newZoom === 1) {
                    canvasStore.setPan({ x: 0, y: 0 });
                  }
                }}
              />
            </label>
            <p class="help-text">Scroll to zoom image and bounding boxes</p>
            {#if zoomLevel > 1}
              <button
                class="btn btn-sm btn-outline"
                on:click={() => {
                  canvasStore.setZoom(1);
                  canvasStore.setPan({ x: 0, y: 0 });
                }}
              >
                Reset Zoom
              </button>
            {/if}
          </div>
        {/if}

        {#if availableClasses.length > 0}
          <div class="class-filters">
            <span class="filter-label">Classes:</span>
            <div class="filter-buttons">
              <button
                class="filter-btn {selectedClasses.size === 0 ? 'active' : ''}"
                on:click={() => {
                  selectedClasses.clear();
                  selectedClasses = selectedClasses;
                  drawDetections();
                }}
              >
                All
              </button>
              {#each availableClasses as className}
                <button
                  class="filter-btn {selectedClasses.has(className)
                    ? 'active'
                    : ''}"
                  on:click={() => toggleClassFilter(className)}
                >
                  {className}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </section>

      <!-- Current Frame Stats -->
      {#if Object.keys(classCounts).length > 0}
        <section class="control-section">
          <h3>Current Frame</h3>
          <div class="frame-stats">
            {#each Object.entries(classCounts) as [className, count]}
              <div class="stat-row">
                <span class="stat-label">{className}:</span>
                <span class="stat-value">{count}</span>
              </div>
            {/each}
            {#if Object.keys(classCounts).length === 0}
              <p class="text-muted">No detections</p>
            {/if}
          </div>
        </section>
      {/if}

      <!-- Job Status (if batch/video/rtsp) -->
      {#if currentJob}
        <section class="control-section">
          <h3>Job Status</h3>
          <div class="job-status">
            <div class="status-badge badge-{currentJob.status}">
              {currentJob.status}
            </div>
            {#if currentJob.progress !== undefined}
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  style="width: {currentJob.progress}%"
                ></div>
              </div>
              {#if currentJob.mode === "webcam" || currentJob.mode === "rtsp"}
                <p class="progress-text">
                  {currentJob.progress} frames processed
                </p>
              {:else}
                <p class="progress-text">{currentJob.progress}%</p>
              {/if}
            {/if}
          </div>
        </section>
      {/if}
    </aside>
  </div>
</div>

<style>
  .detection-page {
    height: 92vh;
    display: flex;
    flex-direction: column;
    border-radius: var(--radius-lg);
    background-color: var(--color-bg-card);
    color: var(--color-white);
  }

  /* Header */
  .detection-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-md) var(--spacing-lg);
    background: var(--color-bg-primary);
    color: var(--color-accent);
    border-radius: var(--radius-lg);
    border-bottom: 2px solid rgba(225, 96, 76, 0.3);
  }

  .header-left h1 {
    font-size: var(--font-size-xl);
    margin: 0;
    color: var(--color-accent);
    font-weight: 700;
  }

  /* Main Content */
  .detection-content {
    flex: 1;
    display: flex;
    gap: var(--spacing-lg);
    padding: var(--spacing-lg);
    overflow: hidden;
  }

  /* Media Area */
  .media-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    min-width: 0;
  }

  .media-container {
    position: relative;
    flex: 1;
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: var(--radius-md);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .media-container.zoomed {
    overflow: auto;
  }

  .media-placeholder {
    text-align: center;
    color: var(--color-text-light);
  }

  .placeholder-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-md);
    opacity: 0.5;
  }

  .detection-canvas {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .detection-canvas.segment-canvas {
    cursor: crosshair;
  }

  .detection-canvas.overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .rtsp-stream-container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .rtsp-frame-status-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10;
    background: rgba(29, 47, 67, 0.95);
    backdrop-filter: blur(10px);
    padding: 2rem 3rem;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .status-message {
    text-align: center;
    color: white;
  }

  .status-message.loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255, 255, 255, 0.2);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .video-display {
    max-width: 100%;
    max-height: 100%;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .segmented-control {
    display: inline-flex;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(10px);
  }

  .segment-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.95rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    min-width: 120px;
    justify-content: center;
  }

  .segment-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .segment-button:not(:disabled):hover {
    color: rgba(255, 255, 255, 0.8);
  }

  .segment-button.active {
    background: rgba(255, 255, 255, 0.95);
    color: var(--color-navy);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  }

  /* Capture Mode Toggle - Enhanced Active State */
  .segment {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border: 2px solid transparent;
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.9rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.25s ease;
    position: relative;
    flex: 1;
    justify-content: center;
  }

  .segment:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .segment:not(:disabled):hover {
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.7);
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  .segment.active {
    background: linear-gradient(135deg, var(--color-accent), #d55540);
    color: white;
    font-weight: 600;
    border-color: var(--color-accent);
    box-shadow:
      0 4px 12px rgba(225, 96, 76, 0.4),
      0 0 0 3px rgba(225, 96, 76, 0.1);
    transform: scale(1.02);
  }

  .segment.active:hover {
    background: linear-gradient(135deg, #d55540, var(--color-accent));
    transform: scale(1.02);
  }

  .segment-icon {
    font-size: 1.1rem;
    line-height: 1;
  }

  .segment-label {
    font-weight: 600;
  }

  .rec-badge {
    position: absolute;
    top: 6px;
    right: 6px;
    background: #ff3b30;
    color: white;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 8px;
    letter-spacing: 0.5px;
    animation: pulse 2s ease-in-out infinite;
  }

  .count-badge {
    background: var(--color-accent);
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    min-width: 20px;
    text-align: center;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }

  /* Gallery View Container */
  .gallery-view-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    background: #000;
    border-radius: 8px;
  }

  .gallery-main-preview {
    flex: 1;
    position: relative;
    display: flex;
    flex-direction: column;
    background: #000;
    border-radius: 8px;
    overflow: hidden;
  }

  .gallery-main-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .gallery-main-info {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.8), transparent);
    padding: 1.5rem 1rem 1rem;
    color: white;
  }

  .frame-timestamp {
    font-size: 0.9rem;
    margin: 0 0 0.25rem 0;
    opacity: 0.9;
  }

  .frame-detections {
    font-size: 0.85rem;
    margin: 0;
    opacity: 0.7;
  }

  .gallery-thumbnails-strip {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.5rem 0;
    scrollbar-width: thin;
    scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar {
    height: 6px;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-track {
    background: transparent;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.3);
    border-radius: 3px;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.5);
  }

  .gallery-thumbnail {
    position: relative;
    flex-shrink: 0;
    width: 100px;
    height: 75px;
    border: 2px solid transparent;
    border-radius: 6px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: none;
    padding: 0;
  }

  .gallery-thumbnail:hover {
    border-color: rgba(255, 255, 255, 0.5);
    transform: scale(1.05);
  }

  .gallery-thumbnail.selected {
    border-color: var(--color-accent);
    box-shadow: 0 0 8px rgba(225, 96, 76, 0.5);
  }

  .gallery-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .thumbnail-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    background: var(--color-accent);
    color: white;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  }

  .empty-gallery {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: rgba(255, 255, 255, 0.6);
    gap: 0.5rem;
  }

  /* Main Preview for Gallery Images */
  .main-preview {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    position: relative;
  }

  .main-preview.zoomed {
    overflow: auto;
  }

  /* Gallery Controls */
  .gallery-controls {
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
    margin-top: var(--spacing-md);
  }

  .gallery-nav {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 40px;
    height: 40px;
    background-color: rgba(0, 0, 0, 0.7);
    color: var(--color-white);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    font-size: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all var(--transition-fast);
    z-index: 10;
  }

  .gallery-nav:hover:not(:disabled) {
    background-color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .gallery-nav:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .gallery-nav-prev {
    left: 10px;
  }

  .gallery-nav-next {
    right: 10px;
  }

  .gallery-thumbnails {
    display: flex;
    gap: var(--spacing-sm);
    overflow-x: auto;
    padding: var(--spacing-sm) 0;
    margin-bottom: var(--spacing-sm);
  }

  .gallery-thumbnail {
    flex-shrink: 0;
    width: 80px;
    height: 60px;
    border-radius: var(--radius-sm);
    overflow: hidden;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all var(--transition-fast);
    padding: 0;
    background: none;
    position: relative;
  }

  .gallery-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .thumbnail-timestamp {
    position: absolute;
    bottom: 2px;
    right: 2px;
    background-color: rgba(0, 0, 0, 0.8);
    color: var(--color-white);
    font-size: 10px;
    padding: 2px 4px;
    border-radius: 3px;
    font-weight: 600;
  }

  .gallery-thumbnail:hover {
    border-color: rgba(255, 255, 255, 0.5);
  }

  .gallery-thumbnail.active {
    border-color: var(--color-accent);
    box-shadow: 0 0 8px rgba(225, 96, 76, 0.5);
  }

  .gallery-indicators {
    display: flex;
    justify-content: center;
    gap: var(--spacing-sm);
  }

  .indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background-color: rgba(255, 255, 255, 0.3);
    border: none;
    cursor: pointer;
    transition: all var(--transition-fast);
    padding: 0;
  }

  .indicator:hover {
    background-color: rgba(255, 255, 255, 0.5);
  }

  .indicator.active {
    background-color: var(--color-accent);
    width: 30px;
    border-radius: 5px;
  }

  .gallery-thumbnails::-webkit-scrollbar {
    height: 6px;
  }

  .gallery-thumbnails::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: var(--radius-sm);
  }

  .gallery-thumbnails::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.3);
    border-radius: var(--radius-sm);
  }

  .gallery-thumbnails::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.5);
  }

  /* Results Area */
  .results-area {
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
    max-height: 250px;
    overflow-y: auto;
  }

  .results-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-md);
  }

  .result-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    background-color: var(--color-accent);
    color: var(--color-white);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    font-weight: 500;
  }

  .results-summary {
    padding-top: var(--spacing-sm);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  /* Control Sidebar */
  .control-sidebar {
    width: 320px;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    overflow-y: auto;
    padding-right: var(--spacing-sm);
  }

  .control-section {
    background-color: var(--color-bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
  }

  .control-section h3 {
    margin: 0 0 var(--spacing-md) 0;
    font-size: var(--font-size-lg);
    color: var(--color-accent);
    border-bottom: 2px solid rgba(225, 96, 76, 0.3);
    padding-bottom: var(--spacing-sm);
  }

  .form-group {
    margin-bottom: var(--spacing-md);
  }

  .form-group label {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .form-group span {
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .form-group input,
  .file-input-label {
    cursor: pointer;
  }

  .file-name {
    margin-top: var(--spacing-xs);
    font-size: 0.9rem;
    color: var(--color-text);
    font-weight: 500;
    line-height: 1.5;
    word-break: break-word;
    background: rgba(255, 255, 255, 0.05);
    padding: 0.75rem;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .btn-start {
    width: 100%;
    margin-bottom: var(--spacing-sm);
    font-weight: 600;
  }

  .btn-start-large {
    padding: var(--spacing-lg) var(--spacing-xl);
    font-size: var(--font-size-lg);
    font-weight: 700;
    letter-spacing: 0.5px;
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.3);
    transition: all var(--transition-base);
  }

  .btn-start-large:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(225, 96, 76, 0.4);
  }

  .btn-start-large:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(225, 96, 76, 0.3);
  }

  .btn-start-large:disabled {
    background-color: #666 !important;
    border-color: #666 !important;
    color: #999 !important;
    cursor: not-allowed !important;
    opacity: 0.5 !important;
    box-shadow: none !important;
  }

  /* Batch Progress Indicator */
  .batch-progress-indicator {
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-md);
    background: rgba(225, 96, 76, 0.1);
    border: 1px solid rgba(225, 96, 76, 0.3);
    border-radius: var(--radius-md);
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xs);
    color: var(--color-white);
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .progress-count {
    color: var(--color-accent);
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: var(--radius-full);
    overflow: hidden;
    margin-bottom: var(--spacing-xs);
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--color-accent), #f97316);
    border-radius: var(--radius-full);
    transition: width var(--transition-base);
  }

  .progress-file {
    color: var(--color-text-light);
    font-size: var(--font-size-xs);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Task-Specific Instructions Styles */
  .task-instructions {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-md);
  }

  .task-badge-header {
    margin-bottom: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
    transition: all 0.2s ease;
  }

  .task-badge-header:hover {
    opacity: 0.8;
  }

  .collapse-toggle {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    transition: all 0.2s ease;
  }

  .collapse-toggle:hover {
    color: rgba(255, 255, 255, 0.9);
    transform: scale(1.1);
  }

  .tips-content {
    margin-top: var(--spacing-sm);
    animation: slideDown 0.2s ease;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .task-badge {
    display: inline-block;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    color: white;
  }

  .task-badge.detect {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  }

  .task-badge.classify {
    background: linear-gradient(135deg, #e1604c 0%, #dc2626 100%);
  }

  .task-badge.segment {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  }

  .task-description {
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.9rem;
    line-height: 1.5;
    margin: var(--spacing-sm) 0;
  }

  .task-guidance {
    margin-top: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: rgba(59, 130, 246, 0.1);
    border-left: 3px solid #3b82f6;
    border-radius: 4px;
  }

  .warning-box {
    margin-top: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 6px;
    color: #fcd34d;
    font-size: 0.85rem;
    line-height: 1.5;
  }

  .btn-reset {
    width: 100%;
    margin-bottom: var(--spacing-md);
    font-size: var(--font-size-base);
  }

  .btn-outline {
    width: 100%;
    margin-bottom: var(--spacing-md);
  }

  .model-selector,
  .source-selector,
  .mode-selector {
    margin-bottom: var(--spacing-md);
  }

  /* Smart Settings */
  .class-filter-control {
    margin-bottom: 1rem;
  }

  .tags-input-container {
    width: 100%;
    min-height: 42px;
    padding: 0.5rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    transition: all 0.2s ease;
  }

  .tags-input-container:focus-within {
    border-color: #e1604c;
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    background: #4b5563;
    color: white;
    border-radius: 4px;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.2s ease;
  }

  .tag-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: 50%;
    color: white;
    font-size: 16px;
    font-weight: bold;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .tag-remove:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  .tag-remove:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .tag-input {
    flex: 1;
    min-width: 120px;
    padding: 0.25rem;
    border: none;
    outline: none;
    font-size: 0.875rem;
    background: transparent;
  }

  .tag-input::placeholder {
    color: #9ca3af;
  }

  .tag-input:disabled {
    cursor: not-allowed;
    background: #f3f4f6;
  }

  .segment-controls {
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-md);
    background: rgba(225, 96, 76, 0.1);
    border: 1px solid rgba(225, 96, 76, 0.3);
    border-radius: var(--radius-md);
  }

  .segment-controls div {
    display: block;
    margin-bottom: var(--spacing-sm);
    color: var(--color-white);
    font-weight: 600;
    font-size: var(--font-size-sm);
  }

  .prompt-mode-selector {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-sm);
  }

  .prompt-mode-btn {
    padding: var(--spacing-sm) var(--spacing-xs);
    background: rgba(255, 255, 255, 0.1);
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: var(--radius-sm);
    color: var(--color-white);
    font-size: var(--font-size-xs);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .prompt-mode-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.4);
    transform: translateY(-1px);
  }

  .prompt-mode-btn.active {
    background: var(--color-accent);
    border-color: var(--color-accent);
    box-shadow: 0 2px 8px rgba(225, 96, 76, 0.3);
  }

  .prompt-mode-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .prompt-hint {
    margin-bottom: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: rgba(255, 255, 255, 0.05);
    border-left: 3px solid var(--color-accent);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
  }

  .text-prompt-input {
    display: flex;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
  }

  .text-prompt-input input {
    flex: 1;
    padding: var(--spacing-sm);
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: var(--radius-sm);
    color: var(--color-white);
    font-size: var(--font-size-sm);
  }

  .text-prompt-input input::placeholder {
    color: rgba(255, 255, 255, 0.4);
  }

  .text-prompt-input input:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 2px rgba(225, 96, 76, 0.2);
  }

  .prompts-list {
    margin-top: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: rgba(0, 0, 0, 0.2);
    border-radius: var(--radius-sm);
  }

  .prompts-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-sm);
    padding-bottom: var(--spacing-xs);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .prompts-header span {
    color: var(--color-white);
    font-size: var(--font-size-xs);
    font-weight: 600;
  }

  .btn-clear {
    padding: var(--spacing-xs) var(--spacing-sm);
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: var(--radius-sm);
    color: #fca5a5;
    font-size: var(--font-size-xs);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .btn-clear:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.3);
    border-color: rgba(239, 68, 68, 0.6);
  }

  .btn-clear:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .prompts-items {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .prompt-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: rgba(255, 255, 255, 0.05);
    border-radius: var(--radius-sm);
    transition: all var(--transition-base);
  }

  .prompt-item:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .prompt-icon {
    font-size: var(--font-size-base);
  }

  .prompt-label {
    flex: 1;
    color: var(--color-white);
    font-size: var(--font-size-xs);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-remove {
    width: 20px;
    height: 20px;
    padding: 0;
    background: rgba(239, 68, 68, 0.2);
    border: none;
    border-radius: 50%;
    color: #fca5a5;
    font-size: 16px;
    font-weight: bold;
    line-height: 1;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .btn-remove:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.4);
  }

  .btn-remove:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .confidence-control {
    margin-bottom: var(--spacing-md);
  }

  /* Skip Frames Control */
  .skip-frames-control {
    margin-bottom: var(--spacing-md);
  }

  .help-text {
    margin-top: var(--spacing-xs);
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
  }

  .warning-badge {
    display: inline-block;
    padding: 4px 8px;
    background: var(--color-warning);
    color: white;
    border-radius: var(--radius-sm);
    font-weight: 600;
    font-size: 0.75rem;
  }

  .info-text {
    margin: 0;
    padding: 0;
  }

  .zoom-control {
    margin-bottom: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .zoom-control label {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .zoom-control span {
    color: var(--color-white);
    font-size: var(--font-size-sm);
    font-weight: 500;
  }

  .zoom-control input[type="range"] {
    width: 100%;
    height: 6px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: var(--radius-sm);
    outline: none;
    appearance: none;
    -webkit-appearance: none;
  }

  .zoom-control input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: var(--color-accent);
    border-radius: 50%;
    cursor: pointer;
  }

  .zoom-control input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: var(--color-accent);
    border-radius: 50%;
    cursor: pointer;
    border: none;
  }

  .zoom-control button {
    margin-top: var(--spacing-sm);
  }

  .class-filters {
    margin-top: var(--spacing-md);
  }

  .filter-label {
    display: block;
    margin-bottom: var(--spacing-sm);
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .filter-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .filter-btn {
    padding: var(--spacing-xs) var(--spacing-sm);
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--color-white);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .filter-btn:hover {
    background-color: rgba(255, 255, 255, 0.2);
  }

  .filter-btn.active {
    background-color: var(--color-accent);
    border-color: var(--color-accent);
  }

  /* Frame Stats */
  .frame-stats {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-xs) 0;
  }

  .stat-label {
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .stat-value {
    color: var(--color-white);
    font-weight: 600;
    font-size: var(--font-size-base);
  }

  /* Job Status */
  .job-status {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .status-badge {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    text-align: center;
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(
      90deg,
      var(--color-accent),
      var(--color-status-success)
    );
    transition: width var(--transition-base);
  }

  .progress-text {
    text-align: center;
    color: var(--color-white);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  /* Scrollbar Styling */
  .control-sidebar::-webkit-scrollbar,
  .results-area::-webkit-scrollbar {
    width: 8px;
  }

  .control-sidebar::-webkit-scrollbar-track,
  .results-area::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: var(--radius-sm);
  }

  .control-sidebar::-webkit-scrollbar-thumb,
  .results-area::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.3);
    border-radius: var(--radius-sm);
  }

  .control-sidebar::-webkit-scrollbar-thumb:hover,
  .results-area::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.5);
  }

  /* Camera Flash Overlay */
  .camera-flash-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: white;
    pointer-events: none;
    z-index: 1000;
    animation: flash 0.3s ease-out;
  }

  @keyframes flash {
    0% {
      opacity: 0.8;
    }
    100% {
      opacity: 0;
    }
  }

  /* Capture Button */
  .btn-capture {
    width: 100%;
    margin-bottom: 0.5rem;
    background: var(--color-accent);
    color: white;
    font-weight: 600;
    padding: 0.875rem 1.5rem;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .btn-capture:hover:not(:disabled) {
    background: #d55540;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.3);
  }

  .btn-capture:active:not(:disabled) {
    transform: translateY(0);
  }

  .btn-capture:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Capture Counter */
  .capture-counter {
    text-align: center;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin: 0.5rem 0 1rem 0;
  }

  /* Clear Gallery Button */
  .btn-clear-gallery {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 600;
    background: rgba(255, 59, 48, 0.9);
    color: white;
    border: 2px solid rgba(255, 59, 48, 1);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow:
      0 4px 12px rgba(255, 59, 48, 0.3),
      0 0 0 0 rgba(255, 59, 48, 0.4);
    backdrop-filter: blur(10px);
  }

  .btn-clear-gallery:hover {
    background: rgba(255, 59, 48, 1);
    transform: translateY(-2px);
    box-shadow:
      0 6px 16px rgba(255, 59, 48, 0.4),
      0 0 0 4px rgba(255, 59, 48, 0.2);
  }

  .btn-clear-gallery:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(255, 59, 48, 0.3);
  }

  .clear-icon {
    font-size: 1.1rem;
    line-height: 1;
  }

  .clear-text {
    font-weight: 600;
  }

  .clear-count {
    opacity: 0.9;
    font-size: 0.85rem;
    font-weight: 500;
  }

  /* Video Session Banner */
  .session-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.15),
      rgba(29, 47, 67, 0.3)
    );
    border: 2px solid rgba(225, 96, 76, 0.4);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(10px);
  }

  .session-info {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex: 1;
  }

  .session-icon {
    font-size: 1.5rem;
  }

  .session-details {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .session-filename {
    color: var(--color-accent);
    font-size: 0.95rem;
    font-weight: 500;
  }

  .session-stats {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-left: auto;
  }

  .capture-count {
    color: rgba(255, 255, 255, 0.7);
    font-size: 0.875rem;
  }

  /* Inactivity Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(5px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: fadeIn 0.2s ease-out;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal-content {
    background: var(--color-navy);
    border-radius: 16px;
    padding: 2rem;
    max-width: 500px;
    width: 90%;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  .inactivity-modal {
    text-align: center;
  }

  .modal-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
  }

  .modal-subtitle {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.6);
    margin-bottom: 1.5rem;
  }

  .modal-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin-top: 1.5rem;
  }

  /* Responsive adjustments */
  @media (max-width: 1200px) {
    .control-sidebar {
      width: 280px;
    }
  }

  /* Responsive adjustments */
  @media (max-height: 1080px) {
    .detection-page{
      height: 92vh;
    }
  }

  /* Responsive adjustments */
  @media (max-height: 720px) {
    .detection-page{
      height: 88vh;
    }
  }

  /* Responsive adjustments */
  @media (max-height: 768px) {
    .detection-page{
      height: 89vh;
    }
  }
</style>
