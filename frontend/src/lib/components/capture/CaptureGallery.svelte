<script lang="ts">
  import type { PredictionResponse } from "@/lib/types";

  /**
   * CaptureGallery - Unified gallery component for capture page
   * Replaces 3x duplicated gallery implementations (image/webcam/RTSP)
   */

  // Svelte 5: Props using $props() rune
  let {
    images = [],
    selectedIndex = $bindable(0),
    disabled = false,
    emptyMessage = "No frames captured",
    emptySubtext = "Click 'Start Detection' to begin capturing frames",
    showMainPreview = true,
    onSelect = undefined,
    onClear = undefined,
  }: {
    images?: Array<{
      original: string;
      annotated: string;
      fileName: string;
      timestamp?: number;
      detectionData?: PredictionResponse;
    }>;
    selectedIndex?: number;
    disabled?: boolean;
    emptyMessage?: string;
    emptySubtext?: string;
    showMainPreview?: boolean;
    onSelect?: ((index: number) => void) | undefined;
    onClear?: (() => void) | undefined;
  } = $props();

  // Handle thumbnail selection
  function selectImage(index: number) {
    if (disabled) return;
    console.log("Selecting image at index:", index);
    selectedIndex = index; // Update bindable prop first
    onSelect?.(index); // Then call callback
  }

  // Handle clear gallery
  function clearGallery() {
    if (disabled) return;
    onClear?.();
  }

  // Svelte 5: Derived reactive values
  const currentImage = $derived(images[selectedIndex]);
  const detectionCount = $derived(
    currentImage?.detectionData?.boxes?.length || 0,
  );

  // Zoom and pan state
  let zoomLevel = $state(1);
  let isPanning = $state(false);
  let panOffset = $state({ x: 0, y: 0 });
  let panStart = $state({ x: 0, y: 0 });

  function handleZoomIn() {
    zoomLevel = Math.min(zoomLevel + 0.25, 3);
  }

  function handleZoomOut() {
    zoomLevel = Math.max(zoomLevel - 0.25, 1);
    if (zoomLevel === 1) {
      panOffset = { x: 0, y: 0 };
    }
  }

  function handlePanStart(e: MouseEvent) {
    if (zoomLevel > 1) {
      isPanning = true;
      panStart = {
        x: e.clientX - panOffset.x,
        y: e.clientY - panOffset.y,
      };
    }
  }

  function handlePanMove(e: MouseEvent) {
    if (isPanning && zoomLevel > 1) {
      panOffset = {
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      };
    }
  }

  function handlePanEnd() {
    isPanning = false;
  }

  function handleWheel(e: WheelEvent) {
    e.preventDefault();
    if (e.deltaY < 0) {
      handleZoomIn();
    } else {
      handleZoomOut();
    }
  }
</script>

<div class="gallery-container">
  {#if images.length > 0}
    <!-- Main Preview (optional, hidden when used with MediaDisplay) -->
    {#if showMainPreview}
      <div class="gallery-main-preview">
        <div
          class="preview-image-container"
          class:zoomed={zoomLevel > 1}
          on:mousedown={handlePanStart}
          on:mousemove={handlePanMove}
          on:mouseup={handlePanEnd}
          on:mouseleave={handlePanEnd}
          on:wheel={handleWheel}
          role="presentation"
        >
          <img
            src={currentImage?.annotated || currentImage?.original}
            alt="Selected frame"
            class="gallery-main-image"
            style="transform: scale({zoomLevel}) translate({panOffset.x /
              zoomLevel}px, {panOffset.y / zoomLevel}px); cursor: {zoomLevel > 1
              ? isPanning
                ? 'grabbing'
                : 'grab'
              : 'default'};"
          />
        </div>
        <div class="gallery-main-info">
          <div class="frame-info-left">
            <p class="frame-timestamp">
              {currentImage?.fileName || `Frame ${selectedIndex + 1}`}
            </p>
            {#if currentImage?.detectionData}
              <p class="frame-detections">
                {detectionCount}
                {detectionCount === 1 ? "object" : "objects"} detected
              </p>
            {/if}
          </div>
          <div class="zoom-controls">
            <h1>ZOOM {zoomLevel}</h1>
            <button
              class="zoom-btn"
              on:click={handleZoomOut}
              disabled={zoomLevel <= 1}
              title="Zoom out"
            >
              −
            </button>
            <span class="zoom-level">{Math.round(zoomLevel * 100)}%</span>
            <button
              class="zoom-btn"
              on:click={handleZoomIn}
              disabled={zoomLevel >= 3}
              title="Zoom in"
            >
              +
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- Thumbnail Strip with Clear Button -->
    <div class="gallery-controls-row">
      <div class="gallery-thumbnails-strip">
        {#each images as image, index}
          <button
            class="gallery-thumbnail"
            class:selected={index === selectedIndex}
            on:click={() => selectImage(index)}
            {disabled}
          >
            <img
              src={image.annotated || image.original}
              alt="Frame {index + 1}"
            />
            {#if image.detectionData}
              <span class="thumbnail-badge">
                {image.detectionData.boxes?.length || 0}
              </span>
            {/if}
          </button>
        {/each}
      </div>

      <!-- Clear Gallery Button -->
      <button class="btn btn-clear-gallery" on:click={clearGallery} {disabled}>
        🗑️ Clear ({images.length})
      </button>
    </div>
  {:else}
    <!-- Empty State -->
    <div class="empty-gallery">
      <p>{emptyMessage}</p>
      <p class="text-muted">{emptySubtext}</p>
    </div>
  {/if}
</div>

<style>
  .gallery-container {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 100%;
  }

  /* Gallery Controls Row - Horizontal layout for thumbnails + clear button */
  .gallery-controls-row {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    background: #f5f5f5;
    padding: 0.5rem;
    border-radius: 8px;
  }

  /* Main Preview */
  .gallery-main-preview {
    flex: 1;
    background: var(--color-navy, #1d2f43);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
    min-height: 400px;
  }

  .preview-image-container {
    flex: 1;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: #000;
    user-select: none;
  }

  .preview-image-container.zoomed {
    cursor: grab;
  }

  .gallery-main-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transition: transform 0.1s ease-out;
  }

  .gallery-main-info {
    background: rgba(29, 47, 67, 0.95);
    padding: 0.75rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: white;
  }

  .frame-info-left {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .frame-timestamp {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .frame-detections {
    margin: 0;
    font-size: 0.85rem;
    color: var(--color-accent, #e1604c);
    font-weight: 600;
  }

  /* Zoom Controls */
  .zoom-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .zoom-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    color: white;
    font-size: 1.2rem;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .zoom-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
    border-color: var(--color-accent, #e1604c);
  }

  .zoom-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .zoom-level {
    min-width: 50px;
    text-align: center;
    font-size: 0.85rem;
    font-weight: 600;
  }

  /* Thumbnail Strip */
  .gallery-thumbnails-strip {
    flex: 1;
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0;
  }

  .gallery-thumbnail {
    position: relative;
    flex-shrink: 0;
    width: 100px;
    height: 75px;
    border: 3px solid transparent;
    border-radius: 6px;
    overflow: hidden;
    cursor: pointer;
    background: #000;
    transition: all 0.2s ease;
    margin-bottom: 5px;
  }

  .gallery-thumbnail:hover:not(:disabled) {
    border-color: rgba(225, 96, 76, 0.5);
    transform: translateY(-2px);
  }

  .gallery-thumbnail.selected {
    border-color: var(--color-accent, #e1604c);
    box-shadow: 0 4px 8px rgba(225, 96, 76, 0.3);
  }

  .gallery-thumbnail:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
    background: var(--color-accent, #e1604c);
    color: white;
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 700;
  }

  /* Empty State */
  .empty-gallery {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: #f5f5f5;
    border-radius: 8px;
    padding: 3rem 1.5rem;
    text-align: center;
    min-height: 300px;
  }

  .empty-gallery p {
    margin: 0.25rem 0;
    color: var(--color-navy, #1d2f43);
    font-size: 1.1rem;
    font-weight: 500;
  }

  .empty-gallery .text-muted {
    color: #666;
    font-size: 0.95rem;
    font-weight: 400;
  }

  /* Clear Gallery Button */
  .btn-clear-gallery {
    flex-shrink: 0;
    padding: 0.6rem 1rem;
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.2s ease;
    white-space: nowrap;
    height: 75px;
  }

  .btn-clear-gallery:hover:not(:disabled) {
    background: #c82333;
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(220, 53, 69, 0.3);
  }

  .btn-clear-gallery:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Scrollbar Styling */
  .gallery-thumbnails-strip::-webkit-scrollbar {
    height: 8px;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-track {
    background: #e0e0e0;
    border-radius: 4px;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-thumb {
    background: var(--color-navy, #1d2f43);
    border-radius: 4px;
  }

  .gallery-thumbnails-strip::-webkit-scrollbar-thumb:hover {
    background: var(--color-accent, #e1604c);
  }
</style>
