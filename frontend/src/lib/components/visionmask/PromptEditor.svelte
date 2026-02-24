<script lang="ts">
  import { onMount, createEventDispatcher } from "svelte";
  import type { InferencePrompt } from "@/lib/types";

  export let imageUrl: string;
  export let prompts: InferencePrompt[] = [];

  const dispatch = createEventDispatcher();

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null;
  let imageElement: HTMLImageElement;
  let imageLoaded = false;

  let canvasWidth = 0;
  let canvasHeight = 0;

  let promptMode: "point" | "box" | "text" = "point";
  let textPromptValue = "";

  // Box drawing state
  let drawingBox = false;
  let boxStart: { x: number; y: number } | null = null;
  let currentBox: { x: number; y: number } | null = null;

  onMount(() => {
    initializeCanvas();
    loadImage();
  });

  function initializeCanvas() {
    if (!canvas) return;
    ctx = canvas.getContext("2d");
  }

  function loadImage() {
    if (!canvas || !ctx) return;

    imageElement = new Image();
    if (!imageUrl.startsWith("blob:")) {
      imageElement.crossOrigin = "anonymous";
    }

    imageElement.onload = () => {
      canvasWidth = imageElement.width;
      canvasHeight = imageElement.height;
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      imageLoaded = true;
      render();
    };

    imageElement.src = imageUrl;
  }

  function render() {
    if (!ctx || !imageElement || !imageLoaded) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Draw image
    ctx.drawImage(imageElement, 0, 0, canvasWidth, canvasHeight);

    // Draw existing prompts
    prompts.forEach((prompt, index) => {
      if (prompt.type === "point" && prompt.coords) {
        drawPoint(
          prompt.coords[0],
          prompt.coords[1],
          prompt.label === 1 ? "green" : "red",
          index,
        );
      } else if (prompt.type === "box" && prompt.coords) {
        drawBox(
          prompt.coords[0],
          prompt.coords[1],
          prompt.coords[2],
          prompt.coords[3],
          index,
        );
      }
    });

    // Draw current box being drawn
    if (drawingBox && boxStart && currentBox) {
      ctx.strokeStyle = "yellow";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.strokeRect(
        boxStart.x,
        boxStart.y,
        currentBox.x - boxStart.x,
        currentBox.y - boxStart.y,
      );
      ctx.setLineDash([]);
    }
  }

  function drawPoint(x: number, y: number, color: string, index: number) {
    if (!ctx) return;

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();

    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Label
    ctx.fillStyle = "white";
    ctx.font = "12px sans-serif";
    ctx.fillText(`P${index + 1}`, x + 8, y - 8);
  }

  function drawBox(
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    index: number,
  ) {
    if (!ctx) return;

    ctx.strokeStyle = "blue";
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

    // Label
    ctx.fillStyle = "blue";
    ctx.fillRect(x1, y1 - 20, 40, 20);
    ctx.fillStyle = "white";
    ctx.font = "12px sans-serif";
    ctx.fillText(`B${index + 1}`, x1 + 5, y1 - 5);
  }

  function handleCanvasClick(event: MouseEvent) {
    if (promptMode === "text") return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Scale coordinates to actual image size
    const scaleX = canvasWidth / rect.width;
    const scaleY = canvasHeight / rect.height;
    const actualX = x * scaleX;
    const actualY = y * scaleY;

    if (promptMode === "point") {
      addPointPrompt(actualX, actualY, event.shiftKey ? 0 : 1);
    }
  }

  function handleCanvasMouseDown(event: MouseEvent) {
    if (promptMode !== "box") return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Scale coordinates
    const scaleX = canvasWidth / rect.width;
    const scaleY = canvasHeight / rect.height;

    drawingBox = true;
    boxStart = { x: x * scaleX, y: y * scaleY };
    currentBox = { x: x * scaleX, y: y * scaleY };
  }

  function handleCanvasMouseMove(event: MouseEvent) {
    if (!drawingBox || !boxStart) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const scaleX = canvasWidth / rect.width;
    const scaleY = canvasHeight / rect.height;

    currentBox = { x: x * scaleX, y: y * scaleY };
    render();
  }

  function handleCanvasMouseUp(event: MouseEvent) {
    if (!drawingBox || !boxStart || !currentBox) return;

    const x1 = Math.min(boxStart.x, currentBox.x);
    const y1 = Math.min(boxStart.y, currentBox.y);
    const x2 = Math.max(boxStart.x, currentBox.x);
    const y2 = Math.max(boxStart.y, currentBox.y);

    addBoxPrompt(x1, y1, x2, y2);

    drawingBox = false;
    boxStart = null;
    currentBox = null;
  }

  function addPointPrompt(x: number, y: number, label: number) {
    prompts = [
      ...prompts,
      {
        type: "point",
        coords: [x, y],
        label,
      },
    ];
    dispatch("promptsChange", prompts);
    render();
  }

  function addBoxPrompt(x1: number, y1: number, x2: number, y2: number) {
    prompts = [
      ...prompts,
      {
        type: "box",
        coords: [x1, y1, x2, y2],
      },
    ];
    dispatch("promptsChange", prompts);
    render();
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
    dispatch("promptsChange", prompts);
    textPromptValue = "";
  }

  function removePrompt(index: number) {
    prompts = prompts.filter((_, i) => i !== index);
    dispatch("promptsChange", prompts);
    render();
  }

  function clearAllPrompts() {
    prompts = [];
    dispatch("promptsChange", prompts);
    render();
  }

  $: if (imageUrl) {
    loadImage();
  }
</script>

<div class="prompt-editor">
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

    <button
      class="clear-btn"
      on:click={clearAllPrompts}
      disabled={prompts.length === 0}
    >
      🗑️ Clear All
    </button>
  </div>

  {#if promptMode === "point"}
    <div class="help-bar">
      Click to add foreground point • Shift+Click for background point
    </div>
  {:else if promptMode === "box"}
    <div class="help-bar">Click and drag to draw a bounding box</div>
  {:else if promptMode === "text"}
    <div class="text-prompt-input">
      <input
        type="text"
        bind:value={textPromptValue}
        placeholder="Describe object (e.g., 'white car', 'person')"
        on:keypress={(e) => e.key === "Enter" && addTextPrompt()}
      />
      <button on:click={addTextPrompt} disabled={!textPromptValue.trim()}>
        Add
      </button>
    </div>
  {/if}

  <div class="canvas-container">
    <canvas
      bind:this={canvas}
      on:click={handleCanvasClick}
      on:mousedown={handleCanvasMouseDown}
      on:mousemove={handleCanvasMouseMove}
      on:mouseup={handleCanvasMouseUp}
      on:mouseleave={handleCanvasMouseUp}
    ></canvas>
  </div>

  {#if prompts.length > 0}
    <div class="prompts-list">
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
            <button class="remove-btn" on:click={() => removePrompt(index)}>
              ×
            </button>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .prompt-editor {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
  }

  .mode-selector {
    display: flex;
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

  .clear-btn {
    padding: var(--spacing-sm) var(--spacing-md);
    border: 1px solid var(--color-border);
    background: white;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .clear-btn:hover:not(:disabled) {
    background: var(--color-error);
    color: white;
    border-color: var(--color-error);
  }

  .clear-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .help-bar {
    padding: var(--spacing-sm);
    background: var(--color-info-bg);
    color: var(--color-info);
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    text-align: center;
  }

  .batch-help {
    background: #fff4e6;
    color: #8b4513;
    text-align: left;
    line-height: 1.5;
    font-size: 0.8rem;
  }

  .batch-help strong {
    color: #d2691e;
  }

  .text-prompt-input {
    display: flex;
    gap: var(--spacing-sm);
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
  }

  .text-prompt-input button:disabled {
    background: var(--color-border);
    cursor: not-allowed;
  }

  .canvas-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-light2);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }

  canvas {
    max-width: 100%;
    max-height: 100%;
    cursor: crosshair;
  }

  .prompts-list {
    padding: var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
    max-height: 150px;
    overflow-y: auto;
  }

  .prompts-list h4 {
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
  }

  .remove-btn:hover {
    color: var(--color-error);
  }
</style>
