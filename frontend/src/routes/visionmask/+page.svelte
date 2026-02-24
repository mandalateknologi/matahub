<script lang="ts">
  import { onMount, onDestroy, tick } from "svelte";
  import InferenceAPI from "../../lib/api/inference";
  import type { InferencePrompt, InferenceConfig, ModelInfo } from "@/lib/types";

  import type {
    PredictionJob,
    PredictionResponse,
    PredictionResult,
  } from "@/lib/types";

  import { uiStore } from "../../lib/stores/uiStore";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import PromptEditor from "../../lib/components/visionmask/PromptEditor.svelte";
  import MaskOverlay from "../../lib/components/prediction/MaskOverlay.svelte";
  import RTSPSam3Viewer from "../../lib/components/visionmask/RTSPViewer.svelte";

  let models: ModelInfo[] = [];
  let selectedModelId: number | null = null;

  // Media mode: 'image' | 'video-detect-all' | 'video-manual' | 'rtsp' | 'rtsp-continuous'
  let mediaMode:
    | "image"
    | "video-detect-all"
    | "video-manual"
    | "rtsp"
    | "rtsp-continuous" = "image";

  // Image mode state
  let selectedFile: File | null = null;
  let imagePreviewUrl: string = "";
  let prompts: InferencePrompt[] = [];
  let loading = false;
  let segmenting = false;
  let result: PredictionResponse | null = null;
  let showResult = false;

  // Video mode state
  let selectedVideoFile: File | null = null;
  let videoPreviewUrl: string = "";
  let skipFrames: number = 5;
  let limitFrames: number = 0; // 0 means no limit, will be set to total frames
  let totalFrames: number = 0; // Total frames in video
  let stopRequested: boolean = false;
  let videoElement: HTMLVideoElement | null = null;
  let videoCanvas: HTMLCanvasElement | null = null;
  let videoCanvasCtx: CanvasRenderingContext2D | null = null;
  let isCapturing: boolean = false;

  // Video job state
  let currentVideoJob: PredictionJob | null = null;
  let videoResults: PredictionResult[] = [];
  let videoProcessing: boolean = false;
  let videoPolling: number | null = null;
  let selectedFrameResult: PredictionResult | null = null;

  // Video manual mode prompt state
  let promptMode: "point" | "box" | "text" = "point";
  let textPromptValue = "";

  // RTSP mode state
  let rtspUrl: string = "";
  let rtspSam3Viewer: RTSPSam3Viewer | null = null;
  let rtspJob: PredictionJob | null = null;

  // Reactive: Set capture mode based on mediaMode
  $: rtspCaptureMode =
    mediaMode === "rtsp-continuous" ? "continuous" : "manual";

  // Blob URLs for authenticated image loading
  let frameBlobUrls = new Map<number, string>();

  // Reactive properties for MaskOverlay (image mode)
  $: polygons = result?.masks?.map((m) => m.polygon) || [];
  $: classes = result?.masks?.map((m) => m.class_id) || [];
  $: classNames = result?.masks?.map((m) => m.class_name) || [];
  $: scores = result?.masks?.map((m) => m.score) || [];
  $: imageWidth = result?.masks?.[0]?.width || 0;
  $: imageHeight = result?.masks?.[0]?.height || 0;

  // Reactive properties for video frame overlay
  $: framePolygons = selectedFrameResult?.masks?.map((m) => m.polygon) || [];
  $: frameClasses = selectedFrameResult?.masks?.map((m) => m.class_id) || [];
  $: frameClassNames =
    selectedFrameResult?.masks?.map((m) => m.class_name) || [];
  $: frameScores = selectedFrameResult?.masks?.map((m) => m.score) || [];
  $: frameWidth = selectedFrameResult?.masks?.[0]?.width || 0;
  $: frameHeight = selectedFrameResult?.masks?.[0]?.height || 0;

  // Fetch authenticated images when videoResults change
  $: {
    if (videoResults.length > 0) {
      fetchFrameImages(videoResults);
    }
  }

  async function fetchFrameImages(frames: PredictionResult[]) {
    for (const frame of frames) {
      // Skip if already fetched
      if (frameBlobUrls.has(frame.result_id || 0)) continue;

      try {
        const response = await InferenceAPI.getResultImage(
          frame.result_id || 0,
        );
        const blobUrl = URL.createObjectURL(response.data);
        frameBlobUrls.set(frame.result_id || 0, blobUrl);
        // Trigger reactivity
        frameBlobUrls = frameBlobUrls;
      } catch (error) {
        console.error(`Failed to fetch image for frame ${frame.id}:`, error);
      }
    }
  }

  onMount(async () => {
    await loadModels();
  });

  onDestroy(() => {
    cleanup();
    // Revoke all blob URLs
    frameBlobUrls.forEach((url) => URL.revokeObjectURL(url));
    frameBlobUrls.clear();
  });

  async function loadModels() {
    try {
      loading = true;
      models = await InferenceAPI.listModels("sam3");

      if (models.length > 0) {
        selectedModelId = models[0].id;
      } else {
        uiStore.showToast(
          "No SAM3 models found. Please configure a SAM3 model in the Based project.",
          "warning",
        );
      }
    } catch (error: any) {
      uiStore.showToast(
        `Failed to load SAM3 models: ${error.message}`,
        "error",
      );
    } finally {
      loading = false;
    }
  }

  function handleMediaModeChange(mode: typeof mediaMode) {
    cleanup();
    mediaMode = mode;

    // Reset state
    selectedFile = null;
    selectedVideoFile = null;
    prompts = [];
    result = null;
    showResult = false;
    videoResults = [];
    currentVideoJob = null;
    selectedFrameResult = null;
  }

  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      selectedFile = input.files[0];

      // Create preview URL
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl);
      }
      imagePreviewUrl = URL.createObjectURL(selectedFile);

      // Reset result
      result = null;
      showResult = false;
    }
  }

  function handleVideoFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      selectedVideoFile = input.files[0];

      // Create preview URL
      if (videoPreviewUrl) {
        URL.revokeObjectURL(videoPreviewUrl);
      }
      videoPreviewUrl = URL.createObjectURL(selectedVideoFile);

      // Reset state
      videoResults = [];
      currentVideoJob = null;
      selectedFrameResult = null;
      totalFrames = 0;
      limitFrames = 0;

      // Setup video element when loaded
      if (videoElement) {
        videoElement.src = videoPreviewUrl;
      }
    }
  }

  function onVideoLoaded() {
    console.log(`Init Video loaded`);
    if (!videoElement) {
      console.error("videoElement is null");
      return;
    }

    // Setup canvas if available (for manual mode)
    if (videoCanvas) {
      videoCanvas.width = videoElement.videoWidth;
      videoCanvas.height = videoElement.videoHeight;
      videoCanvasCtx = videoCanvas.getContext("2d");
    }

    const duration = videoElement.duration;
    console.log("Video metadata:", {
      duration,
      isFinite: isFinite(duration),
      readyState: videoElement.readyState,
      videoWidth: videoElement.videoWidth,
      videoHeight: videoElement.videoHeight,
    });

    // Check if duration is valid
    if (isFinite(duration) && duration > 0) {
      const estimatedFps = 30;
      totalFrames = Math.floor(duration * estimatedFps);
      limitFrames = totalFrames;
      console.log(
        `Video loaded: duration=${duration}s, totalFrames=${totalFrames}, limitFrames=${limitFrames}`,
      );
    } else {
      // Duration not ready yet, retry after a short delay
      console.log("Duration not ready, retrying in 100ms...");
      setTimeout(() => {
        if (
          videoElement &&
          isFinite(videoElement.duration) &&
          videoElement.duration > 0
        ) {
          const estimatedFps = 30;
          totalFrames = Math.floor(videoElement.duration * estimatedFps);
          limitFrames = totalFrames;
          console.log(
            `Video loaded (retry): duration=${videoElement.duration}s, totalFrames=${totalFrames}, limitFrames=${limitFrames}`,
          );
        } else {
          console.warn("Could not get video duration, using fallback");
          totalFrames = 100; // Fallback
          limitFrames = 100;
        }
      }, 100);
    }
    console.log(`last Video loaded`);
  }

  function handlePromptsChange(event: CustomEvent<InferencePrompt[]>) {
    prompts = event.detail;
  }

  async function runSegmentation() {
    if (!selectedFile || !selectedModelId) {
      uiStore.showToast("Please select an image and model", "warning");
      return;
    }

    if (prompts.length === 0) {
      uiStore.showToast(
        "Please add at least one prompt (text, point, or box)",
        "warning",
      );
      return;
    }

    try {
      segmenting = true;
      
      const inferOptions: InferenceConfig = {
        modelId: selectedModelId,
        prompts: prompts,
      };

      result = await InferenceAPI.inferSingle(selectedFile, inferOptions);

      uiStore.showToast(
        `Segmentation complete: ${result.masks?.length || 0} masks in ${result.inference_time_ms?.toFixed(0)}ms`,
        "success",
      );

      showResult = true;
    } catch (error: any) {
      uiStore.showToast(`Segmentation failed: ${error.message}`, "error");
      console.error("Segmentation error:", error);
    } finally {
      segmenting = false;
    }
  }

  async function runVideoDetectAll() {
    if (!selectedVideoFile || !selectedModelId) {
      uiStore.showToast("Please select a video and model", "warning");
      return;
    }

    if (prompts.length === 0) {
      uiStore.showToast(
        "Please add at least one prompt (text, point, or box)",
        "warning",
      );
      return;
    }

    try {
      videoProcessing = true;
      videoResults = [];
      selectedFrameResult = null;
      stopRequested = false;
      currentVideoJob = null;

      const inferOptions: InferenceConfig = {
        modelId: selectedModelId,
        prompts: prompts,
    
      };
      const jobResponse = await InferenceAPI.inferVideo(
        selectedVideoFile,
        inferOptions,
        "continuous",
        skipFrames,
        limitFrames > 0 ? limitFrames : undefined,
      );

      console.log("Video job created:", jobResponse);
      currentVideoJob = jobResponse as any; // Store job response
      uiStore.showToast("Video processing started", "info");

      // Start polling for job status
      startVideoPolling(jobResponse.id);
    } catch (error: any) {
      uiStore.showToast(`Video processing failed: ${error.message}`, "error");
      console.error("Video processing error:", error);
      videoProcessing = false;
    }
  }

  function startVideoPolling(jobId: number) {
    console.log(`Starting video polling for job ${jobId}`);
    videoPolling = window.setInterval(async () => {
      try {
        const jobStatus = await InferenceAPI.getJob(jobId);
        currentVideoJob = jobStatus;
        console.log(
          `Job ${jobId} status:`,
          jobStatus.status,
          `Progress: ${jobStatus.progress}%`,
        );

        // Fetch partial results during processing for real-time updates
        if (
          jobStatus.status === "running" ||
          jobStatus.status === "completed"
        ) {
          try {
            const results = await InferenceAPI.getResults(jobId);
            console.log(`Fetched ${results.length} results for job ${jobId}`);
            if (results.length !== videoResults.length) {
              videoResults = results; // Direct assignment triggers reactivity
              console.log(
                `Updated videoResults, now ${videoResults.length} frames`,
              );
            }
            // Auto-select first frame if none selected
            if (results.length > 0 && !selectedFrameResult) {
              selectedFrameResult = results[0];
            }
          } catch (error) {
            console.log("Results not ready yet");
          }
        }

        if (jobStatus.status === "completed") {
          stopVideoPolling();
          videoProcessing = false;
          stopRequested = false;

          // Fetch final results
          const results = await InferenceAPI.getResults(jobId);
          videoResults = [...results];

          uiStore.showModal({
            type: "success",
            title: "Video Processing Complete",
            message: `Successfully processed ${jobStatus.summary_json.frames_processed} frames with ${jobStatus.summary_json.total_masks} total masks detected.`,
            confirmText: "OK",
            showCancel: false,
            dismissible: true,
          });
        } else if (
          jobStatus.status === "failed" ||
          jobStatus.status === "cancelled"
        ) {
          stopVideoPolling();
          videoProcessing = false;
          stopRequested = false;
          uiStore.showToast(
            jobStatus.status === "cancelled"
              ? "Video processing stopped"
              : `Video processing failed: ${jobStatus.error_message || "Unknown error"}`,
            jobStatus.status === "cancelled" ? "info" : "error",
          );

          uiStore.showModal({
            type: "error",
            title: "Video Processing Failed",
            message: `Failed to process video: ${jobStatus.error_message || "Unknown error"}`,
            confirmText: "OK",
            showCancel: false,
            dismissible: true,
          });
        }
      } catch (error: any) {
        console.error("Polling error:", error);
        stopVideoPolling();
        videoProcessing = false;
      }
    }, 1000);
  }

  function stopVideoPolling() {
    if (videoPolling !== null) {
      clearInterval(videoPolling);
      videoPolling = null;
    }
  }

  async function stopVideoProcessing() {
    if (!currentVideoJob || !currentVideoJob.id) {
      console.error("No video job to stop");
      return;
    }

    try {
      stopRequested = true;
      await InferenceAPI.cancelJob(currentVideoJob.id);
      uiStore.showToast("Stopping video processing...", "info");
    } catch (error: any) {
      uiStore.showToast(`Failed to stop processing: ${error.message}`, "error");
      console.error("Stop error:", error);
      stopRequested = false;
    }
  }

  async function captureCurrentFrame() {
    if (!videoElement || !videoCanvas || !videoCanvasCtx || !selectedModelId)
      return;

    if (prompts.length === 0) {
      uiStore.showToast("Please add at least one prompt first", "warning");
      return;
    }

    try {
      isCapturing = true;

      // Start video session if not exists
      if (!currentVideoJob && selectedVideoFile) {
        const config: InferenceConfig = {
          modelId: selectedModelId,
          prompts: prompts,
        };
        const sessionResponse = await InferenceAPI.inferVideo(
          selectedVideoFile,
          config,
          "manual",
          skipFrames,
        );
        currentVideoJob = sessionResponse;
      }

      // Draw current video frame to canvas
      videoCanvasCtx.drawImage(
        videoElement,
        0,
        0,
        videoCanvas.width,
        videoCanvas.height,
      );

      // Convert canvas to blob
      const blob = await new Promise<Blob | null>((resolve) => {
        videoCanvas!.toBlob(resolve, "image/jpeg", 0.9);
      });

      if (!blob) {
        throw new Error("Failed to capture frame");
      }

      // Create file from blob
      const file = new File([blob], `frame_${Date.now()}.jpg`, {
        type: "image/jpeg",
      });

      // Run segmentation with video session ID
      const captureResult = await InferenceAPI.video_capture_frame(
        currentVideoJob?.id || 0,
        file,
        {
          modelId: selectedModelId,
          prompts: prompts,
        },
      );

      videoResults = [...videoResults, captureResult];
      selectedFrameResult = captureResult;

      // Update session summary
      if (currentVideoJob) {
        currentVideoJob.summary_json.frames_processed = videoResults.length;
        currentVideoJob.summary_json.total_masks = videoResults.reduce(
          (sum, frame) => sum + (frame.masks?.length || 0),
          0,
        );
      }

      uiStore.showToast(
        `Frame captured: ${captureResult.masks?.length || 0} masks detected`,
        "success",
      );
    } catch (error: any) {
      uiStore.showToast(`Capture failed: ${error.message}`, "error");
      console.error("Capture error:", error);
    } finally {
      isCapturing = false;
    }
  }

  function formatTimestamp(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, "0")}:${secs.toFixed(2).padStart(5, "0")}`;
  }

  function selectFrame(frame: PredictionResponse) {
    selectedFrameResult = frame;

    // Seek video to frame timestamp if in manual mode
    if (videoElement && mediaMode === "video-manual") {
      const [mins, secs] = frame.frame_timestamp?.split(":") || ["0", "0"];
      const totalSeconds = parseInt(mins) * 60 + parseFloat(secs);
      videoElement.currentTime = totalSeconds;
    }
  }

  function clearPrompts() {
    prompts = [];
    result = null;
    showResult = false;
    selectedFrameResult = null;
  }

  function removePrompt(index: number) {
    prompts = prompts.filter((_, i) => i !== index);
  }

  function addTextPrompt() {
    if (!textPromptValue.trim()) return;
    prompts = [
      ...prompts,
      {
        type: "text",
        value: textPromptValue.trim(),
      },
    ];
    textPromptValue = "";
  }

  function reset() {
    cleanup();

    selectedFile = null;
    selectedVideoFile = null;
    prompts = [];
    result = null;
    showResult = false;
    videoResults = [];
    currentVideoJob = null; // Clears video manual session
    selectedFrameResult = null;
    limitFrames = 0;
    totalFrames = 0;
    stopRequested = false;
  }

  // RTSP functions
  async function startRTSPStream() {
    if (!rtspUrl || !selectedModelId) {
      uiStore.showToast("Please enter RTSP URL and select model", "warning");
      return;
    }

    if (prompts.length === 0) {
      uiStore.showToast("Please add at least one text prompt", "warning");
      return;
    }

    try {
      videoProcessing = true;
      const inferOptions: InferenceConfig = {
        modelId: selectedModelId,
        prompts: prompts,
      };
      const jobResponse = await InferenceAPI.inferRTSP(
        rtspUrl,
        inferOptions,
        rtspCaptureMode as "continuous" | "manual",
        skipFrames,
      );

      rtspJob = jobResponse;
      console.log("🔴 RTSP job created:", jobResponse);

      // Wait for component to receive new jobId prop
      await tick();

      // Start viewer streaming
      if (rtspSam3Viewer) {
        rtspSam3Viewer.startStream();
      }

      // Start polling for results if in continuous mode
      if (mediaMode === "rtsp-continuous" && rtspJob) {
        startVideoPolling(rtspJob.id);
      }

      uiStore.showToast("RTSP stream started", "success");
    } catch (error: any) {
      uiStore.showToast(`RTSP stream failed: ${error.message}`, "error");
      console.error("RTSP error:", error);
      videoProcessing = false;
    }
  }

  async function handleRTSPCapture(
    event: CustomEvent<{ frame: string; masks: any[] }>,
  ) {
    if (!rtspJob) return;

    try {
      // Call backend to capture and save frame
      const capturedData = await InferenceAPI.rtsp_capture_frame(rtspJob.id, {
        modelId: selectedModelId!,
        prompts: prompts,
      });

      videoResults = [capturedData, ...videoResults];
      selectedFrameResult = capturedData;

      // Fetch frame image for gallery thumbnail
      fetchFrameImages([capturedData]);

      console.log(
        `📸 RTSP frame captured: ${capturedData.masks?.length || 0} masks`,
      );
      uiStore.showToast(
        `Frame captured: ${capturedData.masks?.length || 0} masks`,
        "success",
      );
    } catch (error: any) {
      console.error("Capture error:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to capture frame",
        "error",
      );
    }
  }

  function stopRTSPStream() {
    if (rtspSam3Viewer) {
      rtspSam3Viewer.stopStream();
    }
    if (rtspJob) {
      InferenceAPI.stopJob(rtspJob.id);
    }
    stopVideoPolling();
    videoProcessing = false;
    uiStore.showToast("RTSP stream stopped", "info");
  }

  function cleanup() {
    if (currentVideoJob) {
      // Cancel any ongoing video job
      InferenceAPI.stopJob(currentVideoJob.id).catch((error) => {
        console.error("Failed to cancel video job during cleanup:", error);
      });
    }

    // Stop polling
    stopVideoPolling();

    // Revoke object URLs
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
      imagePreviewUrl = "";
    }

    if (videoPreviewUrl) {
      URL.revokeObjectURL(videoPreviewUrl);
      videoPreviewUrl = "";
    }
  }
</script>

<div class="visionmask-page">
  <div class="page-header">
    <div class="header-content">
      <h1 class="page-title">🎭 VisionMask</h1>
      <p class="page-subtitle">Facebook SAM3 - Segment Anything with Prompts</p>
    </div>
  </div>

  {#if loading}
    <div class="loading-container">
      <LoadingSpinner size="lg" />
      <p>Loading SAM3 models...</p>
    </div>
  {:else}
    <div class="visionmask-container">
      <!-- Configuration Panel -->
      <div class="config-panel">
        <!-- Model Selection -->
        <div class="section">
          <h3>1. Select SAM3 Model</h3>
          <select
            bind:value={selectedModelId}
            class="model-select"
            disabled={models.length === 0}
          >
            {#each models as model}
              <option value={model.id}>{model.name}</option>
            {/each}
          </select>

          {#if models.length === 0}
            <p class="warning-text">
              No SAM3 models available. Configure a SAM3 model in the Based
              project.
            </p>
          {/if}
        </div>

        <!-- Media Mode Selection -->
        <div class="section">
          <h3>2. Select Mode</h3>
          <div class="mode-selector">
            <label class="mode-option">
              <input
                type="radio"
                name="mediaMode"
                value="image"
                checked={mediaMode === "image"}
                on:change={() => handleMediaModeChange("image")}
              />
              <span>🖼️ Image</span>
            </label>
            <label class="mode-option">
              <input
                type="radio"
                name="mediaMode"
                value="video-detect-all"
                checked={mediaMode === "video-detect-all"}
                on:change={() => handleMediaModeChange("video-detect-all")}
              />
              <span>🎬 Video: Detect All</span>
            </label>
            <label class="mode-option">
              <input
                type="radio"
                name="mediaMode"
                value="video-manual"
                checked={mediaMode === "video-manual"}
                on:change={() => handleMediaModeChange("video-manual")}
              />
              <span>📹 Video: Manual</span>
            </label>
            <label class="mode-option">
              <input
                type="radio"
                name="mediaMode"
                value="rtsp"
                checked={mediaMode === "rtsp"}
                on:change={() => handleMediaModeChange("rtsp")}
              />
              <span>🔴 RTSP: Manual</span>
            </label>
            <label class="mode-option">
              <input
                type="radio"
                name="mediaMode"
                value="rtsp-continuous"
                checked={mediaMode === "rtsp-continuous"}
                on:change={() => handleMediaModeChange("rtsp-continuous")}
              />
              <span>🔴 RTSP: Continuous</span>
            </label>
          </div>
        </div>

        <!-- File/Stream Upload -->
        <div class="section">
          <h3>
            3. {mediaMode === "rtsp" || mediaMode === "rtsp-continuous"
              ? "Enter RTSP URL"
              : `Upload ${mediaMode === "image" ? "Image" : "Video"}`}
          </h3>

          {#if mediaMode === "rtsp" || mediaMode === "rtsp-continuous"}
            <input
              type="text"
              bind:value={rtspUrl}
              placeholder="rtsp://camera.local:554/stream"
              class="file-input"
            />
            {#if rtspUrl}
              <p class="file-name">✓ {rtspUrl}</p>
            {/if}
            <p class="help-text">
              Enter your RTSP camera stream URL. Text prompts only for RTSP.
            </p>
          {:else if mediaMode === "image"}
            <input
              type="file"
              accept="image/*"
              on:change={handleFileSelect}
              class="file-input"
            />
            {#if selectedFile}
              <p class="file-name">✓ {selectedFile.name}</p>
            {/if}
          {:else}
            <input
              type="file"
              accept="video/*"
              on:change={handleVideoFileSelect}
              class="file-input"
            />
            {#if selectedVideoFile}
              <p class="file-name">✓ {selectedVideoFile.name}</p>
            {/if}
          {/if}
        </div>

        <!-- Video Settings (Detect All mode only) -->
        {#if mediaMode === "video-detect-all"}
          <div class="section">
            <h3>4. Frame Skip Settings</h3>
            <p class="help-text">Process every Nth frame (Recommended: 5)</p>
            <div class="slider-container">
              <input
                type="range"
                min="1"
                max="30"
                bind:value={skipFrames}
                class="slider"
              />
              <span class="slider-value">{skipFrames}</span>
            </div>
          </div>

          <div class="section">
            <h3>5. Frame Limit</h3>
            <p class="help-text">
              {totalFrames > 0
                ? `Limit processing to first N frames (Total: ${totalFrames} frames)`
                : "Upload a video to see total frames"}
            </p>
            <div class="slider-container">
              <input
                type="range"
                min="1"
                max={totalFrames || 100}
                bind:value={limitFrames}
                disabled={totalFrames === 0}
                class="slider"
              />
              <span class="slider-value"
                >{totalFrames > 0 ? limitFrames : "N/A"}</span
              >
            </div>
          </div>
        {/if}

        <!-- Prompts -->
        <div class="section">
          <h3>
            {mediaMode === "video-detect-all"
              ? "6"
              : mediaMode === "video-manual" ||
                  mediaMode === "rtsp" ||
                  mediaMode === "rtsp-continuous"
                ? "4"
                : "4"}. Add Prompts
          </h3>
          <p class="help-text">
            {mediaMode.startsWith("video") || mediaMode.startsWith("rtsp")
              ? "Prompts will be applied to all frames"
              : "Click on the image to add points, draw boxes, or enter text descriptions"}
          </p>

          {#if prompts.length > 0}
            <div class="prompts-list">
              {#each prompts as prompt, idx}
                <div class="prompt-item">
                  <span>
                    {#if prompt.type === "text"}
                      📝 {prompt.value}
                    {:else if prompt.type === "point"}
                      📍 Point ({prompt.coords?.[0]}, {prompt.coords?.[1]})
                    {:else}
                      ▢ Box
                    {/if}
                  </span>
                  <button
                    class="remove-btn"
                    on:click={() => removePrompt(idx)}
                    title="Remove prompt"
                  >
                    ×
                  </button>
                </div>
              {/each}
            </div>
          {/if}

          {#if mediaMode === "video-detect-all" || mediaMode === "video-manual" || mediaMode === "rtsp" || mediaMode === "rtsp-continuous"}
            <!-- Text prompt input for video and RTSP modes -->
            <div class="text-prompt-input">
              <input
                type="text"
                bind:value={textPromptValue}
                placeholder="Enter object description (e.g., 'person', 'car')"
                on:keydown={(e) => e.key === "Enter" && addTextPrompt()}
              />
              <button
                on:click={addTextPrompt}
                disabled={!textPromptValue.trim()}
                class="btn-add-prompt"
              >
                ➕ Add
              </button>
            </div>
          {/if}
        </div>

        <!-- Actions -->
        <div class="actions">
          {#if mediaMode === "image"}
            <button
              on:click={runSegmentation}
              disabled={!selectedFile ||
                !selectedModelId ||
                prompts.length === 0 ||
                segmenting}
              class="btn btn-primary"
            >
              {#if segmenting}
                <span class="spinner-container">
                  <LoadingSpinner size="sm" />
                </span>
                Segmenting...
              {:else}
                🎯 Run Segmentation
              {/if}
            </button>
          {:else if mediaMode === "video-detect-all"}
            {#if videoProcessing}
              <button
                on:click={stopVideoProcessing}
                disabled={stopRequested}
                class="btn btn-stop"
              >
                {#if stopRequested}
                  <span class="spinner-container">
                    <LoadingSpinner size="sm" />
                  </span>
                  Stopping...
                {:else}
                  ⏹️ Stop Processing
                {/if}
              </button>
            {:else}
              <button
                on:click={runVideoDetectAll}
                disabled={!selectedVideoFile ||
                  !selectedModelId ||
                  prompts.length === 0}
                class="btn btn-primary"
              >
                🎬 Detect All Frames
              </button>
            {/if}
          {:else if mediaMode === "video-manual"}
            <button
              on:click={captureCurrentFrame}
              disabled={!selectedVideoFile ||
                !selectedModelId ||
                prompts.length === 0 ||
                isCapturing}
              class="btn btn-primary"
            >
              {#if isCapturing}
                <span class="spinner-container">
                  <LoadingSpinner size="sm" />
                </span>
                Capturing...
              {:else}
                📸 Capture Frame
              {/if}
            </button>
          {:else if mediaMode === "rtsp" || mediaMode === "rtsp-continuous"}
            {#if videoProcessing}
              <button on:click={stopRTSPStream} class="btn btn-stop">
                ⏹️ Stop Stream
              </button>
              {#if mediaMode === "rtsp"}
                <!-- Manual mode: Show Capture button -->
                <button
                  on:click={() => rtspSam3Viewer?.captureCurrentFrame()}
                  disabled={!rtspJob}
                  class="btn btn-primary"
                >
                  📸 Capture Frame
                </button>
              {/if}
            {:else}
              <button
                on:click={startRTSPStream}
                disabled={!rtspUrl || !selectedModelId || prompts.length === 0}
                class="btn btn-primary"
              >
                🔴 Start Stream
              </button>
            {/if}
          {/if}

          <button
            on:click={clearPrompts}
            disabled={prompts.length === 0 &&
              !result &&
              videoResults.length === 0}
            class="btn btn-secondary"
          >
            🗑️ Clear Prompts
          </button>

          <button on:click={reset} class="btn btn-secondary"> 🔄 Reset </button>
        </div>

        <!-- Progress (Detect All mode) -->
        {#if currentVideoJob && videoProcessing}
          <div class="progress-summary">
            <h4>Processing Video</h4>
            <p class="progress-text">
              Frame {currentVideoJob.summary_json?.frames_processed || 0} of {currentVideoJob
                .summary_json?.total_frames || 0} frames
            </p>
            <div class="progress-bar">
              <div
                class="progress-fill"
                style="width: {currentVideoJob.progress || 0}%"
              ></div>
            </div>
            <div class="progress-stats">
              <span>{(currentVideoJob.progress || 0).toFixed(1)}%</span>
              <span class="stat-label"
                >Masks: {currentVideoJob.summary_json?.total_masks || 0}</span
              >
            </div>
          </div>
        {/if}

        <!-- Results Summary -->
        {#if result && mediaMode === "image"}
          <div class="result-summary">
            <h4>Results</h4>
            <div class="result-stats">
              <div class="stat">
                <span class="stat-label">Masks:</span>
                <span class="stat-value">{result.masks?.length || 0}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Inference Time:</span>
                <span class="stat-value"
                  >{result.inference_time_ms?.toFixed(0)}ms</span
                >
              </div>
              <div class="stat">
                <span class="stat-label">Prompts Used:</span>
                <span class="stat-value">{prompts.length}</span>
              </div>
            </div>
          </div>
        {/if}

        {#if videoResults.length > 0 && !videoProcessing}
          <div class="result-summary">
            <h4>Results</h4>
            <div class="result-stats">
              <div class="stat">
                <span class="stat-label">Frames Captured:</span>
                <span class="stat-value">{videoResults.length}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Total Masks:</span>
                <span class="stat-value">
                  {videoResults.reduce(
                    (sum, r) => sum + (r.masks?.length || 0),
                    0,
                  )}
                </span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Media Panel -->
      <div class="media-panel">
        {#if mediaMode === "image"}
          <!-- Image Mode -->
          {#if imagePreviewUrl}
            {#if showResult && result}
              <div class="result-view">
                <MaskOverlay
                  imageUrl={imagePreviewUrl}
                  {polygons}
                  {classes}
                  {classNames}
                  {scores}
                  {imageWidth}
                  {imageHeight}
                />
              </div>
            {:else}
              <PromptEditor
                imageUrl={imagePreviewUrl}
                {prompts}
                on:promptsChange={handlePromptsChange}
              />
            {/if}
          {:else}
            <div class="empty-state">
              <div class="empty-icon">🖼️</div>
              <p>Upload an image to start</p>
            </div>
          {/if}
        {:else if mediaMode === "video-detect-all"}
          <!-- Video Detect All Mode -->
          <!-- Hidden video element for metadata loading -->
          {#if videoPreviewUrl}
            <video
              bind:this={videoElement}
              src={videoPreviewUrl}
              on:loadedmetadata={onVideoLoaded}
              style="display: none;"
              preload="metadata"
            >
              <track kind="captions" />
            </video>
          {/if}

          {#if videoResults.length > 0 || videoProcessing}
            <div class="video-detect-all-container">
              <!-- Selected Frame Detail -->
              <div class="frame-preview-section">
                {#if selectedFrameResult}
                  <div class="frame-detail-view">
                    <h4>
                      Frame {selectedFrameResult.frame_number} - {selectedFrameResult.frame_timestamp}
                    </h4>
                    {#if frameBlobUrls.has(selectedFrameResult.id || 0)}
                      <div class="frame-image-container">
                        {#key selectedFrameResult.id}
                          <MaskOverlay
                            imageUrl={frameBlobUrls.get(
                              selectedFrameResult.id || 0,
                            ) || ""}
                            polygons={selectedFrameResult.masks?.map(
                              (m) => m.polygon,
                            ) || []}
                            classes={selectedFrameResult.masks?.map(
                              (m) => m.class_id,
                            ) || []}
                            classNames={selectedFrameResult.masks?.map(
                              (m) => m.class_name,
                            ) || []}
                            scores={selectedFrameResult.masks?.map(
                              (m) => m.score,
                            ) || []}
                            imageWidth={selectedFrameResult.masks?.[0]?.width ||
                              0}
                            imageHeight={selectedFrameResult.masks?.[0]
                              ?.height || 0}
                          />
                        {/key}
                      </div>
                    {:else}
                      <div class="loading-frame">
                        <LoadingSpinner size="lg" />
                        <p>Loading frame...</p>
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="empty-state">
                    <div class="empty-icon">🎬</div>
                    <p>
                      {videoProcessing
                        ? "Processing frames..."
                        : "Select a frame to view details"}
                    </p>
                  </div>
                {/if}
              </div>

              <!-- Captured Frames Sidebar -->
              <div class="captured-frames-sidebar">
                <h4>
                  {#if videoProcessing}
                    Processing... ({videoResults.length})
                  {:else}
                    Captured Frames ({videoResults.length})
                  {/if}
                </h4>
                <div class="frames-list">
                  {#each videoResults as frame}
                    <button
                      class="frame-thumb {selectedFrameResult?.id === frame.id
                        ? 'selected'
                        : ''}"
                      on:click={() => selectFrame(frame)}
                    >
                      <div class="thumb-preview">
                        {#if frameBlobUrls.has(frame.id || 0)}
                          <img
                            src={frameBlobUrls.get(frame.id || 0)}
                            alt="Frame {frame.frame_number}"
                            class="thumb-image"
                          />
                          {#if (frame.masks?.length || 0) > 0}
                            <div class="thumb-overlay">
                              <MaskOverlay
                                imageUrl={frameBlobUrls.get(frame.id || 0) ||
                                  ""}
                                polygons={frame.masks?.map((m) => m.polygon) ||
                                  []}
                                classes={frame.masks?.map((m) => m.class_id) ||
                                  []}
                                classNames={frame.masks?.map(
                                  (m) => m.class_name,
                                ) || []}
                                scores={frame.masks?.map((m) => m.score) || []}
                                imageWidth={frame.masks?.[0]?.width || 0}
                                imageHeight={frame.masks?.[0]?.height || 0}
                              />
                            </div>
                          {/if}
                        {:else}
                          <div class="thumb-loading">Loading...</div>
                        {/if}
                      </div>
                      <div class="thumb-info">
                        <span class="thumb-time">{frame.frame_timestamp}</span>
                        <span class="thumb-masks"
                          >{frame.masks?.length || 0} masks</span
                        >
                      </div>
                    </button>
                  {/each}
                </div>
              </div>
            </div>
          {:else if videoPreviewUrl}
            <div class="empty-state">
              <div class="empty-icon">🎬</div>
              <p>Click "Detect All Frames" to start processing</p>
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-icon">🎬</div>
              <p>Upload a video to start</p>
            </div>
          {/if}
        {:else if mediaMode === "video-manual"}
          <!-- Video Manual Mode -->
          {#if videoPreviewUrl}
            <div class="video-manual-container">
              <!-- Main Prompt/Video Section -->
              <div class="video-prompt-section">
                <div class="toolbar">
                  <div class="mode-selector">
                    <button
                      class="mode-btn"
                      class:active={promptMode === "point"}
                      on:click={() => (promptMode = "point")}
                    >
                      📍 Point
                    </button>
                    <button
                      class="mode-btn"
                      class:active={promptMode === "box"}
                      on:click={() => (promptMode = "box")}
                    >
                      ▢ Box
                    </button>
                    <button
                      class="mode-btn"
                      class:active={promptMode === "text"}
                      on:click={() => (promptMode = "text")}
                    >
                      📝 Text
                    </button>
                  </div>
                </div>

                {#if promptMode === "point"}
                  <div class="help-bar">
                    Click to add foreground point • Shift+Click for background
                    point
                  </div>
                {:else if promptMode === "box"}
                  <div class="help-bar">
                    Click and drag to draw a bounding box
                  </div>
                {:else if promptMode === "text"}
                  <div class="text-prompt-input">
                    <input
                      type="text"
                      bind:value={textPromptValue}
                      placeholder="Describe object (e.g., 'white car', 'person')"
                      on:keypress={(e) => e.key === "Enter" && addTextPrompt()}
                    />
                    <button
                      on:click={addTextPrompt}
                      disabled={!textPromptValue.trim()}
                    >
                      Add
                    </button>
                  </div>
                {/if}

                <div
                  class="video-canvas-container"
                  title="Tip: Use fullscreen mode for better view of low-resolution videos"
                >
                  <video
                    bind:this={videoElement}
                    src={videoPreviewUrl}
                    controls
                    on:loadedmetadata={onVideoLoaded}
                    class="video-element"
                  >
                    <track kind="captions" />
                  </video>
                  <canvas
                    bind:this={videoCanvas}
                    class="video-canvas"
                    style="display: none;"
                  ></canvas>
                </div>

                {#if prompts.length > 0}
                  <div class="prompts-list-compact">
                    <h4>Prompts ({prompts.length})</h4>
                    <div class="prompts">
                      {#each prompts as prompt, index}
                        <div class="prompt-item">
                          <span class="prompt-icon">
                            {#if prompt.type === "point"}
                              {prompt.label === 1 ? "🟢" : "🔴"}
                            {:else if prompt.type === "box"}
                              🔷
                            {:else}
                              📝
                            {/if}
                          </span>
                          <span class="prompt-text">
                            {#if prompt.type === "point"}
                              Point {index + 1} ({prompt.label === 1
                                ? "foreground"
                                : "background"})
                            {:else if prompt.type === "box"}
                              Box {index + 1}
                            {:else}
                              "{prompt.value}"
                            {/if}
                          </span>
                          <button
                            class="remove-btn"
                            on:click={() => removePrompt(index)}
                          >
                            ×
                          </button>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>

              <!-- Captured Frames Sidebar -->
              {#if videoResults.length > 0}
                <div class="captured-frames-sidebar">
                  <h4>
                    {#if isCapturing}
                      Capturing... ({videoResults.length})
                    {:else}
                      Captured Frames ({videoResults.length})
                    {/if}
                  </h4>
                  <div class="frames-list">
                    {#each videoResults as frame}
                      <button
                        class="frame-thumb {selectedFrameResult?.id === frame.id
                          ? 'selected'
                          : ''}"
                        on:click={() => selectFrame(frame)}
                      >
                        <!-- Thumbnail with detection overlay -->
                        <div class="thumb-preview">
                          {#if frameBlobUrls.has(frame.id || 0)}
                            <img
                              src={frameBlobUrls.get(frame.id || 0)}
                              alt="Frame {frame.frame_number}"
                              class="thumb-image"
                            />
                            {#if frame.masks && frame.masks.length > 0}
                              <div class="thumb-overlay">
                                <MaskOverlay
                                  imageUrl={frameBlobUrls.get(frame.id || 0) ||
                                    ""}
                                  polygons={frame.masks?.map((m) => m.polygon)}
                                  classes={frame.masks?.map((m) => m.class_id)}
                                  classNames={frame.masks?.map(
                                    (m) => m.class_name,
                                  )}
                                  scores={frame.masks?.map((m) => m.score)}
                                  imageWidth={frame.masks[0]?.width || 0}
                                  imageHeight={frame.masks[0]?.height || 0}
                                />
                              </div>
                            {/if}
                          {:else}
                            <div class="thumb-loading">Loading...</div>
                          {/if}
                        </div>
                        <div class="thumb-info">
                          <span class="thumb-time">{frame.frame_timestamp}</span
                          >
                          <span class="thumb-masks"
                            >{frame.masks?.length} masks</span
                          >
                        </div>
                      </button>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-icon">📹</div>
              <p>Upload a video to start</p>
            </div>
          {/if}
        {:else if mediaMode === "rtsp" || mediaMode === "rtsp-continuous"}
          <!-- RTSP Stream Mode -->
          {#if rtspUrl && rtspJob}
            <div class="video-manual-container">
              <!-- RTSP Viewer -->
              <div class="video-prompt-section">
                {#if mediaMode === "rtsp-continuous"}
                  <div class="mode-indicator">
                    <span class="mode-label">Mode:</span>
                    <span class="mode-value">Continuous</span>
                  </div>
                {/if}
                <RTSPSam3Viewer
                  bind:this={rtspSam3Viewer}
                  modelId={selectedModelId!}
                  {rtspUrl}
                  {prompts}
                  captureMode={rtspCaptureMode as "continuous" | "manual"}
                  {skipFrames}
                  jobId={rtspJob?.id}
                  on:captureFrame={handleRTSPCapture}
                  on:error={(e) => uiStore.showToast(e.detail.message, "error")}
                />
              </div>

              <!-- Captured Frames Sidebar -->
              <div class="captured-frames-sidebar">
                <h4>Captured Frames ({videoResults.length})</h4>

                <div class="frames-list">
                  {#each videoResults as frame (frame.id)}
                    <button
                      class="frame-thumb"
                      class:selected={selectedFrameResult?.id === frame.id}
                      on:click={() => selectFrame(frame)}
                    >
                      <div class="thumb-preview">
                        {#if frameBlobUrls.has(frame.id || 0)}
                          <img
                            src={frameBlobUrls.get(frame.id || 0)}
                            alt="Frame {frame.frame_number}"
                            class="thumb-image"
                          />
                          {#if frame.masks && frame.masks.length > 0}
                            <div class="thumb-overlay">
                              <MaskOverlay
                                imageUrl={frameBlobUrls.get(frame.id || 0) ||
                                  ""}
                                polygons={frame.masks.map((m) => m.polygon)}
                                classes={frame.masks.map(
                                  (m) => m.class_id || 0,
                                )}
                                classNames={frame.masks.map(
                                  (m) => m.class_name || "",
                                )}
                                scores={frame.masks.map((m) => m.score || 0)}
                                imageWidth={frame.masks[0]?.width || 0}
                                imageHeight={frame.masks[0]?.height || 0}
                              />
                            </div>
                          {/if}
                        {:else}
                          <div class="thumb-loading">Loading...</div>
                        {/if}
                      </div>
                      <div class="thumb-info">
                        <span class="thumb-time">{frame.frame_timestamp}</span>
                        <span class="thumb-masks"
                          >{frame.masks?.length || 0} masks</span
                        >
                      </div>
                    </button>
                  {/each}
                </div>
              </div>
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-icon">🔴</div>
              <p>Enter RTSP URL and start streaming</p>
            </div>
          {/if}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .visionmask-page {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .page-header {
    margin-bottom: var(--spacing-lg);
  }

  .header-content {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .page-title {
    font-size: 2rem;
    font-weight: 700;
    color: var(--color-navy);
    margin: 0;
  }

  .page-subtitle {
    font-size: 1rem;
    color: var(--color-text-secondary);
    margin: 0;
  }

  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-md);
    padding: var(--spacing-xl);
  }

  .visionmask-container {
    display: grid;
    grid-template-columns: 400px 1fr;
    gap: var(--spacing-lg);
    flex: 1;
    overflow: hidden;
  }

  .config-panel {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
    padding: var(--spacing-lg);
    background: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    overflow-y: auto;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .section h3 {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-navy);
    margin: 0;
  }

  .model-select {
    padding: var(--spacing-sm);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }

  .file-input {
    padding: var(--spacing-sm);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }

  .file-name {
    font-size: 0.875rem;
    color: var(--color-success);
    margin: 0;
  }

  .help-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin: 0;
  }

  .warning-text {
    font-size: 0.875rem;
    color: var(--color-warning);
    margin: 0;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-sm);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-border);
  }

  .btn {
    padding: var(--spacing-sm) var(--spacing-md);
    border: none;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-base);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-xs);
    min-height: 36px;
    white-space: nowrap;
    flex: 1;
    min-width: fit-content;
  }

  .spinner-container {
    display: inline-flex;
    align-items: center;
    width: 16px;
    height: 16px;
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .btn-primary:disabled {
    background: var(--color-border);
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--color-bg-light1);
    color: var(--color-navy);
    border: 1px solid var(--color-border);
  }

  .btn-secondary:hover {
    background: var(--color-bg-light2);
  }

  .btn-stop {
    background: var(--color-error);
    color: white;
  }

  .btn-stop:hover:not(:disabled) {
    background: #c0392b;
  }

  .btn-stop:disabled {
    background: var(--color-border);
    cursor: not-allowed;
  }

  .result-summary {
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--color-success);
  }

  .result-summary h4 {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-navy);
    margin: 0 0 var(--spacing-sm) 0;
  }

  .result-stats {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .stat {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
  }

  .stat-label {
    color: var(--color-text-secondary);
  }

  .stat-value {
    font-weight: 600;
    color: var(--color-navy);
  }

  .media-panel {
    background: white;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .result-view {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-md);
    color: var(--color-text-secondary);
  }

  .empty-icon {
    font-size: 4rem;
  }

  /* Mode Selector */
  .mode-selector {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .mode-option {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .mode-option:hover {
    background: var(--color-bg-light1);
    border-color: var(--color-accent);
  }

  .mode-option input[type="radio"] {
    cursor: pointer;
  }

  .mode-option span {
    font-size: 0.875rem;
  }

  /* Slider */
  .slider-container {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }

  .slider {
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: var(--color-bg-light2);
    outline: none;
    -webkit-appearance: none;
  }

  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--color-accent);
    cursor: pointer;
  }

  .slider::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--color-accent);
    cursor: pointer;
    border: none;
  }

  .slider-value {
    font-weight: 600;
    color: var(--color-accent);
    min-width: 30px;
    text-align: center;
  }

  /* Prompts List */
  .prompts-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
    max-height: 150px;
    overflow-y: auto;
  }

  .prompt-item {
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }

  /* Progress */
  .progress-summary {
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--color-accent);
  }

  .progress-summary h4 {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-navy);
    margin: 0 0 var(--spacing-xs) 0;
  }

  .progress-text {
    font-size: 0.875rem;
    color: var(--color-navy);
    font-weight: 500;
    margin: 0 0 var(--spacing-sm) 0;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: var(--color-bg-light2);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: var(--spacing-sm);
  }

  .progress-fill {
    height: 100%;
    background: var(--color-accent);
    transition: width 0.3s ease;
  }

  .progress-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
    margin-bottom: var(--spacing-xs);
  }

  .progress-details {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
  }

  .btn-accent {
    background: var(--color-accent);
    color: white;
  }

  .btn-accent:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  /* Video Results */
  .video-detect-all-container {
    width: 100%;
    height: 100%;
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: var(--spacing-md);
    overflow: hidden;
  }

  .frame-preview-section {
    display: flex;
    flex-direction: column;
    background: white;
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .frame-detail-view {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: var(--spacing-md);
  }

  .frame-detail-view h4 {
    margin: 0 0 var(--spacing-md) 0;
    font-size: 1rem;
    color: var(--color-navy);
  }

  .frame-image-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .loading-frame {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-md);
    flex: 1;
  }

  /* Video Manual */
  .video-manual-container {
    width: 100%;
    height: 100%;
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: var(--spacing-md);
    overflow: hidden;
  }

  .video-prompt-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    background: white;
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  .mode-indicator {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-accent);
    border-radius: var(--radius-sm);
    color: white;
    font-size: 0.875rem;
  }

  .mode-label {
    font-weight: 600;
  }

  .mode-value {
    font-weight: 400;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
  }

  .toolbar .mode-selector {
    display: flex;
    flex-direction: row;
    gap: var(--spacing-xs);
  }

  .mode-btn {
    padding: var(--spacing-sm) var(--spacing-md);
    border: 1px solid var(--color-border);
    background: white;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .mode-btn:hover {
    background: var(--color-bg-light2);
  }

  .mode-btn.active {
    background: var(--color-navy);
    color: white;
    border-color: var(--color-navy);
  }

  .text-prompt-input {
    display: flex;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm);
  }

  .text-prompt-input input {
    flex: 1;
    padding: var(--spacing-sm);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }

  .text-prompt-input button {
    padding: var(--spacing-sm) var(--spacing-md);
    border: none;
    background: var(--color-accent);
    color: white;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    cursor: pointer;
    transition: background var(--transition-base);
  }

  .text-prompt-input button:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .text-prompt-input button:disabled {
    background: var(--color-border);
    cursor: not-allowed;
  }

  .video-canvas-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: black;
    border-radius: var(--radius-sm);
    overflow: hidden;
    position: relative;
    min-height: 500px;
  }

  .video-element {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .prompts-list-compact {
    padding: var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
    max-height: 120px;
    overflow-y: auto;
  }

  .prompts-list-compact h4 {
    font-size: 0.875rem;
    font-weight: 600;
    margin: 0 0 var(--spacing-sm) 0;
    color: var(--color-navy);
  }

  .prompts {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .prompt-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: white;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
  }

  .prompt-icon {
    font-size: 1rem;
  }

  .prompt-text {
    flex: 1;
    color: var(--color-navy);
  }

  .remove-btn {
    width: 24px;
    height: 24px;
    border: none;
    background: transparent;
    color: var(--color-text-secondary);
    font-size: 1.25rem;
    cursor: pointer;
    transition: color var(--transition-base);
    padding: 0;
    line-height: 1;
  }

  .remove-btn:hover {
    color: var(--color-error);
  }

  .captured-frames-sidebar {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    background: white;
    border-radius: var(--radius-sm);
    overflow: hidden;
    min-height: 0;
  }

  .captured-frames-sidebar h4 {
    margin: 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-navy);
    flex-shrink: 0;
  }

  .video-frame-canvas {
    flex: 1;
    overflow: hidden;
  }

  .video-player-section {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    gap: var(--spacing-sm);
  }

  .video-player {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: black;
    position: relative;
    border-radius: var(--radius-sm);
    overflow: hidden;
    min-height: 400px;
  }

  .video-element {
    max-width: 100%;
    max-height: 100%;
  }

  .video-canvas {
    position: absolute;
    top: 0;
    left: 0;
  }

  .captured-frames {
    padding: var(--spacing-lg);
    border-top: 1px solid var(--color-border);
    background: white;
    max-height: 200px;
    overflow-y: auto;
  }

  .captured-frames h4 {
    margin: 0 0 var(--spacing-md) 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-navy);
  }

  .frames-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .frame-thumb {
    width: 100%;
    min-height: 200px;
    padding: 0;
    background: var(--color-bg-light1);
    border: 2px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-base);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .frame-thumb:hover {
    border-color: var(--color-accent);
    transform: translateY(-2px);
    box-shadow: var(--shadow-sm);
  }

  .frame-thumb.selected {
    border-color: var(--color-accent);
    border-width: 3px;
  }

  .thumb-preview {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: black;
  }

  .thumb-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .thumb-loading {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .thumb-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    /* height: 100%; */
    pointer-events: none;
  }

  .thumb-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm);
    background: white;
  }

  .thumb-time {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-navy);
  }

  .thumb-masks {
    font-size: 0.7rem;
    color: var(--color-text-secondary);
  }

  .frame-thumb.selected .thumb-info {
    background: var(--color-accent);
  }

  .frame-thumb.selected .thumb-time,
  .frame-thumb.selected .thumb-masks {
    color: white;
  }
</style>
