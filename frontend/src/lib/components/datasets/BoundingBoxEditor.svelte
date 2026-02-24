<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from "svelte";
  import { datasetsAPI } from "../../api/datasets";
  import { uiStore } from "../../stores/uiStore";
  import type {
    DatasetFile,
    BoundingBox,
    ImageLabelData,
  } from "@/lib/types";

  const dispatch = createEventDispatcher();

  export let datasetId: number;
  export let file: DatasetFile;
  export let classes: { [key: string]: string };
  export let onClose: () => void;
  export let onNext: (() => void) | null = null;
  export let onPrevious: (() => void) | null = null;

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null;
  let imageElement: HTMLImageElement;
  let imageLoaded = false;
  let loading = true;
  let saving = false;

  let boxes: BoundingBox[] = [];
  let imageWidth = 0;
  let imageHeight = 0;
  let canvasWidth = 0;
  let canvasHeight = 0;
  let scale = 1;
  let offsetX = 0;
  let offsetY = 0;

  let selectedClassId: number = 0;
  let selectedBoxIndex: number = -1;
  let isDrawing = false;
  let drawStartX = 0;
  let drawStartY = 0;
  let currentBox: BoundingBox | null = null;

  // Undo stack
  let undoStack: BoundingBox[][] = [];
  const MAX_UNDO = 10;

  // Zoom
  let zoomLevel = 1;
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 3;

  // Reactive statement to initialize canvas when both canvas and image are ready
  $: if (imageLoaded && canvas && imageElement) {
    console.log("Reactive: Image and canvas ready, initializing...");
    initializeCanvas();
  }

  // Reactive statement to reload when file changes (Next/Previous navigation)
  $: if (file) {
    console.log("File changed, reloading image and labels:", file.path);
    loadImageAndLabels();
  }

  onMount(async () => {
    if (Object.keys(classes).length > 0) {
      selectedClassId = parseInt(Object.keys(classes)[0]);
    }
    window.addEventListener("keydown", handleKeyDown);
  });

  onDestroy(() => {
    window.removeEventListener("keydown", handleKeyDown);
  });

  async function loadImageAndLabels() {
    loading = true;
    imageLoaded = false;

    // Reset editor state
    selectedBoxIndex = -1;
    isDrawing = false;
    currentBox = null;
    zoomLevel = 1;
    offsetX = 0;
    offsetY = 0;
    undoStack = [];

    try {
      // Load existing labels
      const labelData: ImageLabelData = await datasetsAPI.getImageLabels(
        datasetId,
        file.path
      );
      boxes = labelData.boxes;
      imageWidth = labelData.image_width;
      imageHeight = labelData.image_height;

      // Load image
      const token = localStorage.getItem("access_token");
      // Encode the file path to handle special characters and spaces
      const encodedPath = file.path
        .split("/")
        .map((segment) => encodeURIComponent(segment))
        .join("/");
      const imageUrl = `/api/datasets/${datasetId}/image/${encodedPath}`;
      const urlWithToken = token
        ? `${imageUrl}?token=${encodeURIComponent(token)}`
        : imageUrl;

      imageElement = new Image();
      imageElement.crossOrigin = "anonymous";
      imageElement.onload = () => {
        console.log("Image loaded successfully:", urlWithToken);
        imageLoaded = true;
        loading = false;
        // Don't call initializeCanvas here - let the reactive statement handle it
      };
      imageElement.onerror = (error) => {
        console.error("Failed to load image:", urlWithToken, error);
        uiStore.showToast("Failed to load image", "error");
        loading = false;
      };
      console.log("Loading image from:", urlWithToken);
      imageElement.src = urlWithToken;
    } catch (error) {
      uiStore.showToast("Failed to load labels", "error");
      console.error(error);
      loading = false;
    }
  }

  function initializeCanvas() {
    if (!canvas || !imageElement) {
      console.error("Canvas or image element not available");
      return;
    }

    ctx = canvas.getContext("2d");
    if (!ctx) {
      console.error("Could not get canvas context");
      return;
    }

    // Calculate canvas size to fit container while maintaining aspect ratio
    const containerWidth = canvas.parentElement?.clientWidth || 800;
    const containerHeight = window.innerHeight - 300;

    const imageAspect = imageWidth / imageHeight;
    const containerAspect = containerWidth / containerHeight;

    if (imageAspect > containerAspect) {
      canvasWidth = containerWidth;
      canvasHeight = containerWidth / imageAspect;
    } else {
      canvasHeight = containerHeight;
      canvasWidth = containerHeight * imageAspect;
    }

    canvas.width = canvasWidth;
    canvas.height = canvasHeight;

    scale = canvasWidth / imageWidth;

    console.log("Canvas initialized:", {
      canvasWidth,
      canvasHeight,
      imageWidth,
      imageHeight,
      imageLoaded,
    });

    render();
  }

  function render() {
    if (!ctx || !imageElement || !imageLoaded) {
      console.warn("Cannot render - missing:", {
        hasCtx: !!ctx,
        hasImage: !!imageElement,
        imageLoaded,
      });
      return;
    }

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Apply zoom and pan
    ctx.save();
    ctx.scale(zoomLevel, zoomLevel);
    ctx.translate(offsetX, offsetY);

    // Draw image
    try {
      ctx.drawImage(imageElement, 0, 0, canvasWidth, canvasHeight);
      console.log("Image drawn on canvas");
    } catch (error) {
      console.error("Error drawing image:", error);
    }

    // Draw all boxes
    boxes.forEach((box, index) => {
      drawBox(box, index === selectedBoxIndex);
    });

    // Draw current drawing box
    if (currentBox) {
      drawBox(currentBox, false, true);
    }

    ctx.restore();
  }

  function drawBox(box: BoundingBox, isSelected: boolean, isDraft = false) {
    if (!ctx) return;

    // Convert normalized coordinates to canvas coordinates
    const x = box.x_center * canvasWidth;
    const y = box.y_center * canvasHeight;
    const w = box.width * canvasWidth;
    const h = box.height * canvasHeight;

    const x1 = x - w / 2;
    const y1 = y - h / 2;

    // Draw rectangle
    ctx.strokeStyle = isSelected ? "#E1604C" : isDraft ? "#FFA500" : "#00FF00";
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.strokeRect(x1, y1, w, h);

    // Draw class label
    const className =
      classes[box.class_id.toString()] || `Class ${box.class_id}`;
    const labelBg = isSelected ? "#E1604C" : isDraft ? "#FFA500" : "#00FF00";

    ctx.font = "14px Montserrat, sans-serif";
    const textWidth = ctx.measureText(className).width;
    const padding = 4;

    ctx.fillStyle = labelBg;
    ctx.fillRect(x1, y1 - 20, textWidth + padding * 2, 20);

    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(className, x1 + padding, y1 - 6);
  }

  function getCanvasCoordinates(
    event: MouseEvent
  ): { x: number; y: number } | null {
    if (!canvas) return null;

    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / zoomLevel - offsetX;
    const y = (event.clientY - rect.top) / zoomLevel - offsetY;

    return { x, y };
  }

  function handleMouseDown(event: MouseEvent) {
    const coords = getCanvasCoordinates(event);
    if (!coords) return;

    // Check if clicking on existing box
    const clickedIndex = findBoxAtPoint(coords.x, coords.y);
    if (clickedIndex !== -1) {
      selectedBoxIndex = clickedIndex;
      render();
      return;
    }

    // Start drawing new box
    selectedBoxIndex = -1;
    isDrawing = true;
    drawStartX = coords.x;
    drawStartY = coords.y;
  }

  function handleMouseMove(event: MouseEvent) {
    if (!isDrawing) return;

    const coords = getCanvasCoordinates(event);
    if (!coords) return;

    const x1 = Math.min(drawStartX, coords.x);
    const y1 = Math.min(drawStartY, coords.y);
    const x2 = Math.max(drawStartX, coords.x);
    const y2 = Math.max(drawStartY, coords.y);

    const width = x2 - x1;
    const height = y2 - y1;

    // Convert to normalized coordinates
    currentBox = {
      class_id: selectedClassId,
      x_center: (x1 + width / 2) / canvasWidth,
      y_center: (y1 + height / 2) / canvasHeight,
      width: width / canvasWidth,
      height: height / canvasHeight,
    };

    render();
  }

  function handleMouseUp(event: MouseEvent) {
    if (!isDrawing || !currentBox) return;

    isDrawing = false;

    // Validate box has minimum size
    if (currentBox.width < 0.01 || currentBox.height < 0.01) {
      currentBox = null;
      render();
      return;
    }

    // Clamp box to image bounds
    currentBox = clampBox(currentBox);

    // Save to undo stack
    pushUndo();

    // Add box
    boxes = [...boxes, currentBox];
    currentBox = null;
    render();
  }

  function findBoxAtPoint(x: number, y: number): number {
    for (let i = boxes.length - 1; i >= 0; i--) {
      const box = boxes[i];
      const boxX = box.x_center * canvasWidth;
      const boxY = box.y_center * canvasHeight;
      const boxW = box.width * canvasWidth;
      const boxH = box.height * canvasHeight;

      const x1 = boxX - boxW / 2;
      const y1 = boxY - boxH / 2;
      const x2 = boxX + boxW / 2;
      const y2 = boxY + boxH / 2;

      if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
        return i;
      }
    }
    return -1;
  }

  function clampBox(box: BoundingBox): BoundingBox {
    const halfW = box.width / 2;
    const halfH = box.height / 2;

    let x = box.x_center;
    let y = box.y_center;

    // Clamp center to keep box within bounds
    x = Math.max(halfW, Math.min(1 - halfW, x));
    y = Math.max(halfH, Math.min(1 - halfH, y));

    return { ...box, x_center: x, y_center: y };
  }

  function deleteSelectedBox() {
    if (selectedBoxIndex === -1) return;

    pushUndo();
    boxes = boxes.filter((_, index) => index !== selectedBoxIndex);
    selectedBoxIndex = -1;
    render();
  }

  function handleKeyDown(event: KeyboardEvent) {
    // Ignore if typing in input
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLSelectElement
    ) {
      return;
    }

    switch (event.key) {
      case "Delete":
      case "Backspace":
        event.preventDefault();
        deleteSelectedBox();
        break;
      case "Escape":
        event.preventDefault();
        if (isDrawing) {
          isDrawing = false;
          currentBox = null;
          render();
        } else {
          onClose();
        }
        break;
      case "n":
      case "N":
        event.preventDefault();
        if (onNext) handleSaveAndNext();
        break;
      case "p":
      case "P":
        event.preventDefault();
        if (onPrevious) handleSaveAndPrevious();
        break;
      case "z":
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault();
          undo();
        }
        break;
      case "y":
        if (event.ctrlKey || event.metaKey) {
          event.preventDefault();
          redo();
        }
        break;
    }
  }

  function pushUndo() {
    undoStack = [...undoStack, JSON.parse(JSON.stringify(boxes))];
    if (undoStack.length > MAX_UNDO) {
      undoStack = undoStack.slice(-MAX_UNDO);
    }
  }

  function undo() {
    if (undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    undoStack = undoStack.slice(0, -1);
    boxes = JSON.parse(JSON.stringify(previous));
    selectedBoxIndex = -1;
    render();
  }

  function redo() {
    // Simple implementation - can be enhanced
    uiStore.showToast("Redo not yet implemented", "info");
  }

  function handleZoomIn() {
    zoomLevel = Math.min(MAX_ZOOM, zoomLevel + 0.2);
    render();
  }

  function handleZoomOut() {
    zoomLevel = Math.max(MIN_ZOOM, zoomLevel - 0.2);
    render();
  }

  function handleZoomReset() {
    zoomLevel = 1;
    offsetX = 0;
    offsetY = 0;
    render();
  }

  async function handleSave() {
    saving = true;
    try {
      await datasetsAPI.saveImageLabels(datasetId, file.path, boxes, true);
      uiStore.showToast("Labels saved successfully", "success");

      // Dispatch event to notify parent component of label updates
      dispatch("labelsUpdated", {
        filePath: file.path,
        boxes: boxes,
      });
    } catch (error) {
      uiStore.showToast("Failed to save labels", "error");
      console.error(error);
    } finally {
      saving = false;
    }
  }

  async function handleSaveAndNext() {
    await handleSave();
    if (onNext) onNext();
  }

  async function handleSaveAndPrevious() {
    await handleSave();
    if (onPrevious) onPrevious();
  }

  function handleClassChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    selectedClassId = parseInt(target.value);
  }
</script>

<div class="editor-overlay" on:click={onClose}>
  <div class="editor-container" on:click|stopPropagation>
    <div class="editor-header">
      <div class="header-left">
        <h2>Label Image</h2>
        <span class="filename">{file.name}</span>
      </div>
      <div class="header-actions">
        <button class="btn-icon" on:click={onClose} title="Close (Esc)">
          ✕
        </button>
      </div>
    </div>

    {#if loading}
      <div class="editor-loading">
        <div class="spinner"></div>
        <p>Loading image...</p>
      </div>
    {:else}
      <div class="editor-body">
        <div class="editor-sidebar">
          <div class="section">
            <h3>Class Selection</h3>
            <select
              class="class-select"
              bind:value={selectedClassId}
              on:change={handleClassChange}
            >
              {#each Object.entries(classes) as [classId, className]}
                <option value={parseInt(classId)}>{className}</option>
              {/each}
            </select>
            <p class="hint">Draw boxes on the image for selected class</p>
          </div>

          <div class="section">
            <h3>Bounding Boxes ({boxes.length})</h3>
            <div class="box-list">
              {#each boxes as box, index}
                <button
                  class="box-item"
                  class:selected={index === selectedBoxIndex}
                  on:click={() => {
                    selectedBoxIndex = index;
                    render();
                  }}
                >
                  <span class="box-class"
                    >{classes[box.class_id.toString()] ||
                      `Class ${box.class_id}`}</span
                  >
                  <span
                    class="btn-delete-box"
                    role="button"
                    tabindex="0"
                    on:click|stopPropagation={() => {
                      selectedBoxIndex = index;
                      deleteSelectedBox();
                    }}
                    on:keydown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        selectedBoxIndex = index;
                        deleteSelectedBox();
                      }
                    }}
                    title="Delete box"
                  >
                    🗑️
                  </span>
                </button>
              {:else}
                <p class="empty-message">No boxes yet. Draw on the image.</p>
              {/each}
            </div>
          </div>

          <div class="section">
            <h3>Zoom Controls</h3>
            <div class="zoom-controls">
              <button class="btn btn-sm" on:click={handleZoomOut}>−</button>
              <span class="zoom-level">{Math.round(zoomLevel * 100)}%</span>
              <button class="btn btn-sm" on:click={handleZoomIn}>+</button>
              <button class="btn btn-sm btn-outline" on:click={handleZoomReset}
                >Reset</button
              >
            </div>
          </div>

          <div class="section">
            <h3>Keyboard Shortcuts</h3>
            <div class="shortcuts">
              <div class="shortcut">
                <kbd>Delete</kbd> <span>Remove selected box</span>
              </div>
              <div class="shortcut">
                <kbd>Ctrl+Z</kbd> <span>Undo</span>
              </div>
              <div class="shortcut">
                <kbd>N</kbd> <span>Save & Next</span>
              </div>
              <div class="shortcut">
                <kbd>P</kbd> <span>Save & Previous</span>
              </div>
              <div class="shortcut">
                <kbd>Esc</kbd> <span>Close editor</span>
              </div>
            </div>
          </div>
        </div>

        <div class="canvas-container">
          <canvas
            bind:this={canvas}
            on:mousedown={handleMouseDown}
            on:mousemove={handleMouseMove}
            on:mouseup={handleMouseUp}
            on:mouseleave={() => {
              if (isDrawing) {
                isDrawing = false;
                currentBox = null;
                render();
              }
            }}
          ></canvas>
        </div>
      </div>

      <div class="editor-footer">
        <div class="footer-left">
          {#if onPrevious}
            <button
              class="btn btn-outline"
              on:click={handleSaveAndPrevious}
              disabled={saving}
            >
              ← Previous (P)
            </button>
          {/if}
        </div>
        <div class="footer-center">
          <button
            class="btn btn-primary"
            on:click={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Labels"}
          </button>
        </div>
        <div class="footer-right">
          {#if onNext}
            <button
              class="btn btn-outline"
              on:click={handleSaveAndNext}
              disabled={saving}
            >
              Next (N) →
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .editor-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 20px;
  }

  .editor-container {
    background: white;
    border-radius: 12px;
    width: 95%;
    max-width: 1600px;
    height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid var(--color-border);
  }

  .header-left {
    display: flex;
    align-items: baseline;
    gap: 16px;
  }

  .editor-header h2 {
    margin: 0;
    color: var(--color-navy);
    font-size: 1.5rem;
  }

  .filename {
    color: var(--color-grey);
    font-size: 0.875rem;
  }

  .btn-icon {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--color-grey);
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    transition: all 0.15s;
  }

  .btn-icon:hover {
    background: var(--color-bg-light1);
    color: var(--color-navy);
  }

  .editor-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 16px;
  }

  .spinner {
    border: 4px solid var(--color-bg-light1);
    border-top: 4px solid var(--color-primary);
    border-radius: 50%;
    width: 48px;
    height: 48px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .editor-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .editor-sidebar {
    width: 320px;
    padding: 20px;
    border-right: 1px solid var(--color-border);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .section h3 {
    margin: 0 0 12px 0;
    font-size: 1rem;
    color: var(--color-navy);
  }

  .class-select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: 0.9375rem;
    font-family: inherit;
  }

  .hint {
    margin: 8px 0 0 0;
    font-size: 0.8125rem;
    color: var(--color-grey);
    line-height: 1.4;
  }

  .box-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 200px;
    overflow-y: auto;
  }

  .box-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--color-bg-light1);
    border: 2px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    font-size: 0.875rem;
  }

  .box-item:hover {
    background: #e8eef5;
  }

  .box-item.selected {
    border-color: var(--color-accent);
    background: #fef3f1;
  }

  .box-class {
    font-weight: 500;
    color: var(--color-navy);
  }

  .btn-delete-box {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    opacity: 0.6;
    transition: opacity 0.15s;
  }

  .btn-delete-box:hover {
    opacity: 1;
  }

  .empty-message {
    color: var(--color-grey);
    font-size: 0.8125rem;
    margin: 8px 0;
    text-align: center;
  }

  .zoom-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .zoom-level {
    font-weight: 600;
    color: var(--color-navy);
    min-width: 50px;
    text-align: center;
  }

  .shortcuts {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .shortcut {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.8125rem;
  }

  kbd {
    background: var(--color-bg-light1);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 2px 8px;
    font-family: monospace;
    font-size: 0.75rem;
    font-weight: 600;
    min-width: 60px;
    text-align: center;
  }

  .shortcut span {
    color: var(--color-grey);
  }

  .canvas-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: #f5f5f5;
    overflow: auto;
  }

  canvas {
    cursor: crosshair;
    background: white;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .editor-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-light1);
  }

  .footer-left,
  .footer-right {
    flex: 1;
  }

  .footer-right {
    display: flex;
    justify-content: flex-end;
  }

  .footer-center {
    display: flex;
    justify-content: center;
  }

  @media (max-width: 1024px) {
    .editor-sidebar {
      width: 280px;
    }
  }

  @media (max-width: 768px) {
    .editor-container {
      width: 100%;
      height: 100vh;
      border-radius: 0;
    }

    .editor-body {
      flex-direction: column;
    }

    .editor-sidebar {
      width: 100%;
      max-height: 200px;
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }

    .canvas-container {
      min-height: 300px;
    }
  }
</style>
