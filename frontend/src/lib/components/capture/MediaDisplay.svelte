<script lang="ts">
  import type { PredictionResponse, GalleryImage } from "@/lib/types";
  import type { InferencePrompt } from "@/lib/types";
  import RTSPViewer from "../visionmask/RTSPViewer.svelte";

  // Svelte 5: Props using $props() rune
  let {
    sourceType,
    galleryImages,
    currentGalleryIndex = 0,
    zoomLevel = 1,
    panOffset = $bindable(),
    isPanning = $bindable(),
    panStart = $bindable(),
    videoElement = $bindable(),
    canvasElement = $bindable(),
    canvasOverlay = $bindable(),
    isFlashing = $bindable(),
    rtspViewMode = "live",
    rtspCanvasElement = $bindable(),
    rtspCanvasOverlay = $bindable(),
    rtspFrameStatus = "loading",
    rtspCaptureMode = "manual",
    promptRequired = false,
    rtsp_viewer = $bindable(),
    rtspUrl = "",
    selectedModelId = null,
    inferPrompts = [],
    webcamViewMode = "live",
    videoCaptureMode = "manual",
    onUpdateOverlay = undefined,
    onPanStart = undefined,
    onPanMove = undefined,
    onPanEnd = undefined,
  }: {
    sourceType: "image" | "batch" | "video" | "webcam" | "rtsp";
    galleryImages: GalleryImage[];
    currentGalleryIndex?: number;
    zoomLevel?: number;
    panOffset?: { x: number; y: number };
    isPanning?: boolean;
    panStart?: { x: number; y: number };
    videoElement?: HTMLVideoElement | null;
    canvasElement?: HTMLCanvasElement | null;
    canvasOverlay?: HTMLCanvasElement | null;
    isFlashing?: boolean;
    rtspViewMode?: "live" | "gallery";
    rtspCanvasElement?: HTMLCanvasElement | null;
    rtspCanvasOverlay?: HTMLCanvasElement | null;
    rtspFrameStatus?: "loading" | "ready" | "error";
    rtspCaptureMode?: "manual" | "continuous";
    promptRequired?: boolean;
    rtsp_viewer?: any;
    rtspUrl?: string;
    selectedModelId?: number | null;
    inferPrompts?: InferencePrompt[];
    webcamViewMode?: "live" | "gallery";
    videoCaptureMode?: "manual" | "continuous";
    onUpdateOverlay?: (() => void) | undefined;
    onPanStart?: ((detail: { x: number; y: number }) => void) | undefined;
    onPanMove?: ((detail: { x: number; y: number }) => void) | undefined;
    onPanEnd?: (() => void) | undefined;
  } = $props();

  function handlePanStart(e: MouseEvent) {
    if (zoomLevel > 1) {
      isPanning = true;
      panStart = {
        x: e.clientX - panOffset.x,
        y: e.clientY - panOffset.y,
      };
      onPanStart?.(panStart);
    }
  }

  function handlePanMove(e: MouseEvent) {
    if (isPanning && zoomLevel > 1) {
      panOffset = {
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      };
      onPanMove?.(panOffset);
    }
  }

  function handlePanEnd() {
    isPanning = false;
    onPanEnd?.();
  }

  function handleVideoSeek() {
    if (videoCaptureMode === "continuous" && galleryImages.length > 0) {
      onUpdateOverlay?.();
    }
  }

  function handleVideoTimeUpdate() {
    if (
      videoCaptureMode === "continuous" &&
      galleryImages.length > 0 &&
      videoElement &&
      !videoElement.paused
    ) {
      onUpdateOverlay?.();
    }
  }

  function handleVideoKeydown(e: KeyboardEvent) {
    if (
      e.code === "Space" &&
      sourceType === "video" &&
      videoCaptureMode === "manual"
    ) {
      e.preventDefault();
      e.stopPropagation();
    }
  }
</script>

<div class="media-container">
  {#if sourceType === "video"}
    <!-- Video Live View (always show video element when video source selected) -->
    <video
      bind:this={videoElement}
      class="video-display"
      controls={true}
      on:seeked={handleVideoSeek}
      on:timeupdate={handleVideoTimeUpdate}
      on:keydown={handleVideoKeydown}
    >
      <track kind="captions" />
    </video>
    <canvas
      bind:this={canvasElement}
      class="detection-canvas overlay"
      style="display: none;"
    ></canvas>
    <canvas bind:this={canvasOverlay} class="detection-canvas overlay"></canvas>
    {#if isFlashing}
      <div class="camera-flash-overlay"></div>
    {/if}
  {:else if sourceType === "webcam"}
    <!-- Webcam View -->
    {#if webcamViewMode === "live"}
      <!-- Webcam Live View -->
      <video
        bind:this={videoElement}
        class="video-display"
        controls={false}
        on:seeked={handleVideoSeek}
        on:timeupdate={handleVideoTimeUpdate}
        on:keydown={handleVideoKeydown}
      >
        <track kind="captions" />
      </video>
      <canvas
        bind:this={canvasElement}
        class="detection-canvas overlay"
        style="display: none;"
      ></canvas>
      <canvas bind:this={canvasOverlay} class="detection-canvas overlay"
      ></canvas>
      {#if isFlashing}
        <div class="camera-flash-overlay"></div>
      {/if}
    {:else if webcamViewMode === "gallery" && galleryImages.length > 0}
      <!-- Webcam Gallery View -->
      <div
        class="main-preview"
        class:zoomed={zoomLevel > 1}
        on:mousedown={handlePanStart}
        on:mousemove={handlePanMove}
        on:mouseup={handlePanEnd}
        on:mouseleave={handlePanEnd}
        role="presentation"
      >
        <img
          src={galleryImages[currentGalleryIndex].annotated}
          alt="Detection result"
          style="transform: scale({zoomLevel}) translate({panOffset.x /
            zoomLevel}px, {panOffset.y / zoomLevel}px); cursor: {zoomLevel > 1
            ? isPanning
              ? 'grabbing'
              : 'grab'
            : 'default'};"
        />
      </div>
    {:else}
      <!-- Webcam Empty State -->
      <div class="media-placeholder">
        <div class="placeholder-icon">📷</div>
        <p>Start webcam to begin capture</p>
      </div>
    {/if}
  {:else if sourceType === "image" || sourceType === "batch"}
    <!-- Image/Batch View -->
    {#if galleryImages.length > 0}
      <!-- Gallery Preview -->
      <div
        class="main-preview"
        class:zoomed={zoomLevel > 1}
        on:mousedown={handlePanStart}
        on:mousemove={handlePanMove}
        on:mouseup={handlePanEnd}
        on:mouseleave={handlePanEnd}
        role="presentation"
      >
        <img
          src={galleryImages[currentGalleryIndex].annotated}
          alt="Detection result"
          style="transform: scale({zoomLevel}) translate({(panOffset?.x || 0) /
            zoomLevel}px, {(panOffset?.y || 0) /
            zoomLevel}px); cursor: {zoomLevel > 1
            ? isPanning
              ? 'grabbing'
              : 'grab'
            : 'default'};"
        />
      </div>
    {:else}
      <!-- Canvas View (for live drawing during detection or prompt editing) -->
      <div
        class="canvas-preview-container"
        class:zoomed={zoomLevel > 1}
        on:mousedown={handlePanStart}
        on:mousemove={handlePanMove}
        on:mouseup={handlePanEnd}
        on:mouseleave={handlePanEnd}
        role="presentation"
      >
        <canvas
          bind:this={canvasElement}
          class="detection-canvas"
          style="transform: scale({zoomLevel}) translate({(panOffset?.x || 0) /
            zoomLevel}px, {(panOffset?.y || 0) /
            zoomLevel}px); cursor: {zoomLevel > 1
            ? isPanning
              ? 'grabbing'
              : 'grab'
            : 'default'}; transition: transform 0.1s ease-out;"
        ></canvas>
        <canvas
          bind:this={canvasOverlay}
          class="detection-canvas overlay"
          style="display: none;"
        ></canvas>
      </div>
    {/if}
  {:else if sourceType === "rtsp"}
    <!-- RTSP View -->
    {#if rtspViewMode === "live"}
      <!-- RTSP Live View -->
      {#if promptRequired && selectedModelId}
        <!-- SAM3 RTSP Viewer Component -->
        <RTSPViewer
          bind:this={rtsp_viewer}
          modelId={selectedModelId}
          {rtspUrl}
          prompts={inferPrompts}
          captureMode={rtspCaptureMode}
          skipFrames={5}
          campaignId={null}
          jobId={null}
        />
      {:else}
        <!-- Standard RTSP Canvas View -->
        <div class="rtsp-stream-container" style="position: relative;">
          <canvas bind:this={rtspCanvasElement} class="video-display"></canvas>
          <canvas bind:this={rtspCanvasOverlay} class="detection-canvas overlay"
          ></canvas>
          {#if isFlashing}
            <div class="camera-flash-overlay"></div>
          {/if}
          {#if rtspFrameStatus === "loading" && rtspCaptureMode === "manual"}
            <div class="rtsp-frame-status-overlay">
              <div class="status-message loading">
                <div class="spinner"></div>
                <p>Waiting for video stream...</p>
                <small>No frame available yet</small>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    {:else if rtspViewMode === "gallery" && galleryImages.length > 0}
      <!-- RTSP Gallery View -->
      <div
        class="main-preview"
        class:zoomed={zoomLevel > 1}
        on:mousedown={handlePanStart}
        on:mousemove={handlePanMove}
        on:mouseup={handlePanEnd}
        on:mouseleave={handlePanEnd}
        role="presentation"
      >
        <img
          src={galleryImages[currentGalleryIndex].annotated}
          alt="Detection result"
          style="transform: scale({zoomLevel}) translate({panOffset.x /
            zoomLevel}px, {panOffset.y / zoomLevel}px); cursor: {zoomLevel > 1
            ? isPanning
              ? 'grabbing'
              : 'grab'
            : 'default'};"
        />
      </div>
    {:else}
      <!-- RTSP Empty State -->
      <div class="media-placeholder">
        <div class="placeholder-icon">📡</div>
        <p>Enter RTSP URL to connect</p>
      </div>
    {/if}
  {:else}
    <!-- Empty State -->
    <div class="media-placeholder">
      <div class="placeholder-icon">📷</div>
      <p>Select a source to begin inference</p>
    </div>
  {/if}
</div>

<style>
  .media-container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #000;
    border-radius: 8px;
    overflow: hidden;
  }

  .main-preview {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    user-select: none;
  }

  .main-preview.zoomed {
    cursor: grab;
  }

  .canvas-preview-container {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    user-select: none;
  }

  .canvas-preview-container.zoomed {
    cursor: grab;
  }

  .canvas-preview-container canvas {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .main-preview img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transition: transform 0.1s ease-out;
  }

  .video-display {
    max-width: 100%;
    max-height: 100%;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .detection-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }

  .overlay {
    z-index: 2;
  }

  .camera-flash-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: white;
    opacity: 0;
    animation: flash 0.3s ease-out;
    pointer-events: none;
    z-index: 10;
  }

  @keyframes flash {
    0% {
      opacity: 0.8;
    }
    100% {
      opacity: 0;
    }
  }

  .rtsp-stream-container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .rtsp-stream-container canvas {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
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

  .status-message p {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: white;
  }

  .status-message small {
    font-size: 0.875rem;
    color: rgba(255, 255, 255, 0.7);
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

  .media-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    color: rgba(255, 255, 255, 0.5);
  }

  .placeholder-icon {
    font-size: 4rem;
    opacity: 0.3;
  }

  .media-placeholder p {
    margin: 0;
    font-size: 1.1rem;
  }
</style>
