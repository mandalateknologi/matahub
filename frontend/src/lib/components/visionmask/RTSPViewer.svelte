<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from "svelte";
  import type { InferencePrompt } from "@/lib/types";
  import type { MaskData } from "@/lib/types";
  import client from "../../api/client";
  import { drawPolygonMask } from "../../utils/drawingUtils";

  // Props
  export let modelId: number; // Model ID for inference
  export let rtspUrl: string;
  export let prompts: InferencePrompt[] = [];
  export let confidence: number = 0.5;
  export let classFilter: string[] = [];
  export let captureMode: "continuous" | "manual" = "manual";
  export let skipFrames: number = 10;
  export let campaignId: number | null = null;
  export let jobId: number | null = null;

  // Canvas elements
  let canvasElement: HTMLCanvasElement;
  let overlayCanvas: HTMLCanvasElement;
  let canvasCtx: CanvasRenderingContext2D | null = null;
  let overlayCtx: CanvasRenderingContext2D | null = null;

  // State
  let isStreaming = false;
  let pollingIntervalId: number | null = null;
  let latestFrame: string | null = null; // Base64 image
  let latestMasks: MaskData[] = [];
  let frameStatus: "loading" | "ready" | "error" = "loading";
  let errorMessage: string = "";

  const dispatch = createEventDispatcher<{
    jobStatusChange: { jobId: number; status: string };
    captureFrame: { frame: string; masks: MaskData[] };
    error: { message: string };
  }>();

  onMount(() => {
    // Initialize canvas contexts
    if (canvasElement) {
      canvasCtx = canvasElement.getContext("2d");
    }
    if (overlayCanvas) {
      overlayCtx = overlayCanvas.getContext("2d");
    }
  });

  onDestroy(() => {
    stopStream();
  });

  export function startStream() {
    if (isStreaming || !jobId) return;

    isStreaming = true;
    frameStatus = "loading";

    // Start polling for latest frames every 2.5s
    pollingIntervalId = window.setInterval(async () => {
      await pollLatestFrame();
    }, 2500);

    console.log(
      `🔴 Started RTSP stream polling (job ${jobId}, interval: 2.5s)`,
    );
  }

  export function stopStream() {
    if (pollingIntervalId !== null) {
      clearInterval(pollingIntervalId);
      pollingIntervalId = null;
    }
    isStreaming = false;
    console.log("⏹️ Stopped RTSP stream polling");
  }

  async function pollLatestFrame() {
    if (!jobId) return;

    try {
      frameStatus = "loading";

      // Use authenticated API client (client is already the axios instance)
      const response = await client.get(
        `/inference/rtsp/${jobId}/latest-frame`,
      );

      // Update state
      latestFrame = response.data.frame; // Base64 data URL
      latestMasks = response.data.masks || [];
      frameStatus = "ready";

      // Draw frame and masks
      drawFrame();
      drawMasks();
    } catch (error: any) {
      // 404 means no frames available yet (not an error, just waiting)
      if (error.response?.status === 404) {
        frameStatus = "loading";
        console.log("Waiting for first RTSP frame...");
      } else {
        // Actual error
        console.error("Error polling RTSP frame:", error);
        frameStatus = "error";
        errorMessage = error.response?.data?.detail || error.message;
        dispatch("error", { message: errorMessage });
      }
    }
  }

  function drawFrame() {
    if (!latestFrame || !canvasCtx || !canvasElement) return;

    const img = new Image();
    img.onload = () => {
      // Resize canvas to match image
      canvasElement.width = img.width;
      canvasElement.height = img.height;
      overlayCanvas.width = img.width;
      overlayCanvas.height = img.height;

      // Draw image
      canvasCtx!.drawImage(img, 0, 0);
    };
    img.src = latestFrame;
  }

  function drawMasks() {
    if (
      !overlayCtx ||
      !overlayCanvas ||
      !latestMasks ||
      latestMasks.length === 0
    ) {
      // Clear overlay if no masks
      if (overlayCtx && overlayCanvas) {
        overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      }
      return;
    }

    // Clear previous overlay
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    // Draw each mask using utility
    latestMasks.forEach((mask, i) => {
      if (!mask.polygon || mask.polygon.length === 0) return;

      // Use unified drawing utility for masks
      drawPolygonMask(overlayCtx!, mask.polygon, i, {
        fillOpacity: 0.3,
        strokeWidth: 2,
      });

      // Draw label at first point
      if (mask.polygon[0]) {
        const label = `${mask.class_name} ${(mask.score * 100).toFixed(1)}%`;
        overlayCtx!.font = "14px Montserrat, sans-serif";
        overlayCtx!.fillStyle = "white";
        overlayCtx!.strokeStyle = "black";
        overlayCtx!.lineWidth = 3;
        overlayCtx!.strokeText(
          label,
          mask.polygon[0][0],
          mask.polygon[0][1] - 5,
        );
        overlayCtx!.fillText(label, mask.polygon[0][0], mask.polygon[0][1] - 5);
      }
    });
  }

  export function captureCurrentFrame() {
    if (!latestFrame) {
      console.warn("No frame available to capture");
      return;
    }

    // Dispatch event to trigger backend capture
    dispatch("captureFrame", { frame: latestFrame, masks: latestMasks });
  }

  // Reactive: restart polling if jobId or prompts change
  $: if (jobId && isStreaming) {
    stopStream();
    startStream();
  }
</script>

<div class="rtsp-viewer">
  <div class="canvas-container">
    <canvas bind:this={canvasElement} class="stream-canvas"></canvas>
    <canvas bind:this={overlayCanvas} class="overlay-canvas"></canvas>

    {#if frameStatus === "loading"}
      <div class="status-overlay">
        <div class="spinner"></div>
        <p>Loading RTSP stream...</p>
      </div>
    {/if}

    {#if frameStatus === "error"}
      <div class="status-overlay error">
        <p>⚠️ {errorMessage}</p>
      </div>
    {/if}
  </div>

  <div class="stream-info">
    <div class="info-item">
      <span class="label">Status:</span>
      <span class="value" class:streaming={isStreaming}>
        {isStreaming ? "🔴 Live" : "⏸️ Paused"}
      </span>
    </div>
    <div class="info-item">
      <span class="label">Masks:</span>
      <span class="value">{latestMasks?.length || 0}</span>
    </div>
    <div class="info-item">
      <span class="label">Mode:</span>
      <span class="value">{captureMode}</span>
    </div>
  </div>
</div>

<style>
  .rtsp-viewer {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    height: 100%;
    width: 100%;
  }

  .canvas-container {
    position: relative;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: black;
    border-radius: var(--radius-sm);
    overflow: hidden;
    min-height: 400px;
    width: 100%;
  }

  .stream-canvas,
  .overlay-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-fit: contain;
  }

  .overlay-canvas {
    pointer-events: none;
  }

  .status-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.8);
    padding: var(--spacing-lg);
    border-radius: var(--radius-md);
    color: white;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .status-overlay.error {
    background: rgba(231, 76, 60, 0.9);
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 4px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .stream-info {
    display: flex;
    gap: var(--spacing-lg);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
  }

  .info-item {
    display: flex;
    gap: var(--spacing-xs);
    font-size: 0.875rem;
  }

  .label {
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .value {
    color: var(--color-navy);
    font-weight: 600;
  }

  .value.streaming {
    color: var(--color-error);
    animation: pulse 2s ease-in-out infinite;
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
</style>
