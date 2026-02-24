<script lang="ts">
  import { onMount } from "svelte";
  import { InferenceAPI } from "../../../lib/api/inference";

  export let results: Array<{
    id: number;
    file_name: string;
    task_type: string;
    detection_count?: number;
    boxes?: number[][];
    scores?: number[];
    classes?: number[];
    class_names?: string[];
    top_class?: string;
    top_confidence?: number;
    masks?: Array<{
      instance_id: number;
      class_id: number;
      class_name: string;
      bbox: number[];
      score: number;
      mask: number[][];
      height: number;
      width: number;
    }>;
  }> = [];

  export let jobId: number;
  export let taskType: string = "detect";
  export let showStatistics: boolean = true;

  // Use jobId for API calls
  $: apiEndpoint = `/api/inference/jobs/${jobId}/results`;

  let selectedIndex = 0;
  let imageElements: Map<number, HTMLImageElement> = new Map();
  let canvasElement: HTMLCanvasElement;
  let currentImageData: string | null = null;
  let isLoading = false;
  let lastLoadedResultId: number | null = null;
  let pendingLoadId: number | null = null; // Track pending request

  $: currentResult = results[selectedIndex];
  $: if (
    currentResult &&
    canvasElement &&
    currentResult.id !== lastLoadedResultId &&
    currentResult.id !== pendingLoadId &&
    !isLoading
  ) {
    loadAndRenderImage(currentResult);
  }

  async function loadAndRenderImage(result: typeof currentResult) {
    if (!result || !canvasElement || isLoading) return;
    if (result.id === lastLoadedResultId || result.id === pendingLoadId) return; // Prevent reloading same image

    pendingLoadId = result.id;
    isLoading = true;
    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    try {
      // Fetch image using native fetch with manual Authorization header
      const response = await InferenceAPI.getResultImage(result.id || 0);

      if (!response.ok) {
        console.error(
          `Failed to load image for result ${result.id}: ${response.status}`
        );
        // Mark as loaded to prevent retry loop
        lastLoadedResultId = result.id;
        throw new Error(`Failed to load image: ${response.status}`);
      }

      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);

      // Load image
      const img = new Image();
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = imageUrl;
      });

      // Check canvas still exists before setting dimensions
      if (!canvasElement) {
        URL.revokeObjectURL(imageUrl);
        return;
      }

      // Set canvas size
      canvasElement.width = img.width;
      canvasElement.height = img.height;

      // Draw original image
      ctx.drawImage(img, 0, 0);

      // Draw annotations based on task type
      if (taskType === "detect" && result.boxes && result.boxes.length > 0) {
        drawBoundingBoxes(ctx, result);
      } else if (taskType === "classify" && result.top_class) {
        drawClassificationLabel(ctx, result);
      } else if (
        taskType === "segment" &&
        result.masks &&
        result.masks.length > 0
      ) {
        drawSegmentationMasks(ctx, result);
      }

      // Store canvas as data URL
      currentImageData = canvasElement.toDataURL("image/jpeg");

      // Mark as successfully loaded
      lastLoadedResultId = result.id;

      // Clean up
      URL.revokeObjectURL(imageUrl);
    } catch (error) {
      console.error("Error loading image:", error);
      // Keep lastLoadedResultId set to prevent infinite retry
      lastLoadedResultId = result.id;
    } finally {
      isLoading = false;
      // Clear pending flag after completion
      if (pendingLoadId === result.id) {
        pendingLoadId = null;
      }
    }
  }

  function drawBoundingBoxes(
    ctx: CanvasRenderingContext2D,
    result: typeof currentResult
  ) {
    if (!result.boxes || !result.scores || !result.class_names) return;

    result.boxes.forEach((box, idx) => {
      const [x1, y1, x2, y2] = box;
      const score = result.scores![idx];
      const className = result.class_names![idx];

      // Draw box
      ctx.strokeStyle = "#E1604C";
      ctx.lineWidth = 3;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw label background
      const label = `${className} ${(score * 100).toFixed(1)}%`;
      ctx.font = "16px Montserrat, sans-serif";
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = "#E1604C";
      ctx.fillRect(x1, y1 - 25, textWidth + 10, 25);

      // Draw label text
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(label, x1 + 5, y1 - 7);
    });
  }

  function drawClassificationLabel(
    ctx: CanvasRenderingContext2D,
    result: typeof currentResult
  ) {
    if (!result.top_class || !result.top_confidence) return;

    const label = `${result.top_class} ${(result.top_confidence * 100).toFixed(1)}%`;
    ctx.font = "bold 24px Montserrat, sans-serif";
    const textWidth = ctx.measureText(label).width;

    // Draw label at top center
    const x = (canvasElement.width - textWidth) / 2 - 10;
    const y = 20;

    // Background
    ctx.fillStyle = "rgba(225, 96, 76, 0.9)";
    ctx.fillRect(x, y, textWidth + 20, 40);

    // Text
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(label, x + 10, y + 28);
  }

  function drawSegmentationMasks(
    ctx: CanvasRenderingContext2D,
    result: typeof currentResult
  ) {
    if (!result.masks || result.masks.length === 0) return;

    const canvasWidth = ctx.canvas.width;
    const canvasHeight = ctx.canvas.height;

    // Create temporary canvas for mask overlay
    const maskCanvas = document.createElement("canvas");
    maskCanvas.width = canvasWidth;
    maskCanvas.height = canvasHeight;
    const maskCtx = maskCanvas.getContext("2d");
    if (!maskCtx) return;

    result.masks.forEach((maskData, idx) => {
      // Generate color from instance ID (golden angle hue)
      const hue = (idx * 137.5) % 360;
      const color = `hsla(${hue}, 70%, 50%, 0.4)`;

      // Draw mask pixels
      const imageData = maskCtx.createImageData(
        maskData.width,
        maskData.height
      );
      const rgba = hslToRgb(hue / 360, 0.7, 0.5);

      for (let y = 0; y < maskData.height; y++) {
        for (let x = 0; x < maskData.width; x++) {
          if (maskData.mask[y][x] === 1) {
            const pixelIndex = (y * maskData.width + x) * 4;
            imageData.data[pixelIndex] = rgba[0]; // R
            imageData.data[pixelIndex + 1] = rgba[1]; // G
            imageData.data[pixelIndex + 2] = rgba[2]; // B
            imageData.data[pixelIndex + 3] = 102; // A (0.4 opacity)
          }
        }
      }

      // Draw mask to mask canvas
      maskCtx.putImageData(imageData, 0, 0);

      // Draw bounding box
      const [x1, y1, x2, y2] = maskData.bbox;
      ctx.strokeStyle = `hsl(${hue}, 70%, 50%)`;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw label
      const label = `${maskData.class_name} ${(maskData.score * 100).toFixed(1)}%`;
      ctx.font = "14px Montserrat, sans-serif";
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = `hsl(${hue}, 70%, 50%)`;
      ctx.fillRect(x1, y1 - 22, textWidth + 8, 22);
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(label, x1 + 4, y1 - 6);
    });

    // Composite mask overlay onto main canvas
    ctx.globalAlpha = 1.0;
    ctx.drawImage(maskCanvas, 0, 0);
  }

  function hslToRgb(h: number, s: number, l: number): [number, number, number] {
    let r, g, b;

    if (s === 0) {
      r = g = b = l;
    } else {
      const hue2rgb = (p: number, q: number, t: number) => {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
      };

      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = hue2rgb(p, q, h + 1 / 3);
      g = hue2rgb(p, q, h);
      b = hue2rgb(p, q, h - 1 / 3);
    }

    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
  }

  function selectImage(index: number) {
    selectedIndex = index;
  }

  function handleThumbnailKeydown(event: KeyboardEvent, index: number) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectImage(index);
    }
  }

  function previousImage() {
    if (selectedIndex > 0) {
      selectedIndex--;
    }
  }

  function nextImage() {
    if (selectedIndex < results.length - 1) {
      selectedIndex++;
    }
  }

  onMount(() => {
    // Wait for canvas to be ready before loading first image
    setTimeout(() => {
      if (results.length > 0 && canvasElement) {
        loadAndRenderImage(results[0]);
      }
    }, 100);
  });
</script>

<div class="image-gallery">
  {#if results.length === 0}
    <div class="empty-state">
      <p>No images to display</p>
    </div>
  {:else}
    <div class="gallery-main">
      <!-- Main Image Viewer -->
      <div class="image-viewer">
        <canvas bind:this={canvasElement} class="main-canvas"></canvas>
        {#if isLoading}
          <div class="loading-overlay">
            <div class="loading">Loading image...</div>
          </div>
        {/if}

        <!-- Navigation Controls -->
        <div class="navigation">
          <button
            on:click={previousImage}
            disabled={selectedIndex === 0}
            class="nav-btn"
          >
            ◀ Previous
          </button>
          <span class="image-counter">
            {selectedIndex + 1} / {results.length}
          </span>
          <button
            on:click={nextImage}
            disabled={selectedIndex === results.length - 1}
            class="nav-btn"
          >
            Next ▶
          </button>
        </div>
      </div>

      <!-- Thumbnail Grid -->
      <div class="thumbnail-grid">
        {#each results as result, index}
          <div
            class="thumbnail-item"
            class:selected={index === selectedIndex}
            on:click={() => selectImage(index)}
            on:keydown={(e) => handleThumbnailKeydown(e, index)}
            role="button"
            tabindex="0"
          >
            <div class="thumbnail-placeholder">
              <span class="thumbnail-label">{result.file_name}</span>
              {#if taskType === "detect"}
                <span class="detection-badge"
                  >{result.detection_count || 0}</span
                >
              {:else if taskType === "classify" && result.top_class}
                <span class="class-badge">{result.top_class}</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>

      <!-- Statistics Panel -->
      {#if showStatistics && currentResult}
        <div class="statistics-panel">
          <h4>Detection Details</h4>
          <div class="stat-item">
            <span class="stat-label">File:</span>
            <span class="stat-value">{currentResult.file_name}</span>
          </div>

          {#if taskType === "detect"}
            <div class="stat-item">
              <span class="stat-label">Detections:</span>
              <span class="stat-value"
                >{currentResult.detection_count || 0}</span
              >
            </div>
            {#if currentResult.class_names && currentResult.class_names.length > 0}
              <div class="detections-list">
                {#each currentResult.class_names as className, idx}
                  <div class="detection-item">
                    <span>{className}</span>
                    <span class="confidence">
                      {((currentResult.scores?.[idx] || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
          {:else if taskType === "classify"}
            <div class="stat-item">
              <span class="stat-label">Class:</span>
              <span class="stat-value">{currentResult.top_class}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Confidence:</span>
              <span class="stat-value">
                {((currentResult.top_confidence || 0) * 100).toFixed(1)}%
              </span>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .image-gallery {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: #666;
  }

  .gallery-main {
    display: grid;
    grid-template-columns: 1fr 250px;
    gap: 1rem;
    height: 100%;
  }

  .image-viewer {
    position: relative;
    background: #f5f5f5;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
  }

  .main-canvas {
    max-width: 100%;
    max-height: calc(100% - 60px);
    object-fit: contain;
    display: block;
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(245, 245, 245, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
  }

  .loading {
    color: #666;
    font-size: 1.1rem;
  }

  .navigation {
    position: absolute;
    bottom: 1rem;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 1rem;
    align-items: center;
    background: rgba(255, 255, 255, 0.95);
    padding: 0.5rem 1rem;
    border-radius: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .nav-btn {
    padding: 0.5rem 1rem;
    background: var(--color-navy, #1d2f43);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-family: "Montserrat", sans-serif;
    font-size: 0.9rem;
    transition: var(--transition-base, 0.2s);
  }

  .nav-btn:hover:not(:disabled) {
    background: var(--color-accent, #e1604c);
  }

  .nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .image-counter {
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
    min-width: 80px;
    text-align: center;
  }

  .thumbnail-grid {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    overflow-y: auto;
    max-height: 600px;
    padding: 0.5rem;
    background: #f9f9f9;
    border-radius: 8px;
  }

  .thumbnail-item {
    cursor: pointer;
    border: 2px solid transparent;
    border-radius: 6px;
    transition: var(--transition-base, 0.2s);
    overflow: hidden;
  }

  .thumbnail-item:hover {
    border-color: var(--color-accent, #e1604c);
  }

  .thumbnail-item.selected {
    border-color: var(--color-navy, #1d2f43);
    box-shadow: 0 2px 8px rgba(29, 47, 67, 0.2);
  }

  .thumbnail-placeholder {
    background: white;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-height: 80px;
    position: relative;
  }

  .thumbnail-label {
    font-size: 0.85rem;
    color: #333;
    font-weight: 500;
    word-break: break-all;
  }

  .detection-badge,
  .class-badge {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: var(--color-accent, #e1604c);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .class-badge {
    background: var(--color-navy, #1d2f43);
  }

  .statistics-panel {
    grid-column: 1 / -1;
    background: white;
    border-radius: 8px;
    padding: 1rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .statistics-panel h4 {
    margin: 0 0 1rem;
    color: var(--color-navy, #1d2f43);
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid #eee;
  }

  .stat-label {
    font-weight: 600;
    color: #666;
  }

  .stat-value {
    color: var(--color-navy, #1d2f43);
    font-weight: 500;
  }

  .detections-list {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .detection-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    background: #f5f5f5;
    border-radius: 4px;
  }

  .confidence {
    font-weight: 600;
    color: var(--color-accent, #e1604c);
  }
</style>
