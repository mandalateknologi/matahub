<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { generateClassColor } from "../../utils/segmentationFormat";

  export let imageUrl: string;
  export let polygons: number[][][] = []; // Array of polygons: [[[x,y], [x,y], ...], ...]
  export let classes: number[] = [];
  export let classNames: string[] = [];
  export let scores: number[] = [];
  export let imageWidth: number = 0;
  export let imageHeight: number = 0;

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null;
  let imageElement: HTMLImageElement;
  let imageLoaded = false;
  let loading = true;

  let canvasWidth = 0;
  let canvasHeight = 0;

  let opacity = 0.5; // Mask opacity (0-1)
  let showOutlines = true;
  let showLabels = true;

  // Map class IDs to colors
  let classColors = new Map<number, string>();

  $: {
    // Generate colors for each class
    classes.forEach((classId) => {
      if (!classColors.has(classId)) {
        classColors.set(classId, generateClassColor(classId));
      }
    });
  }

  onMount(() => {
    initializeCanvas();
    loadImageAndRenderMasks();
  });

  onDestroy(() => {
    if (imageElement) {
      imageElement.onload = null;
    }
  });

  function initializeCanvas() {
    if (!canvas) return;

    ctx = canvas.getContext("2d");
    if (!ctx) {
      console.error("Failed to get canvas context");
      return;
    }
  }

  function loadImageAndRenderMasks() {
    if (!canvas || !ctx) {
      console.log("❌ No canvas or ctx");
      return;
    }

    console.log("📸 Loading image:", imageUrl);
    loading = true;

    imageElement = new Image();
    // Only set crossOrigin for external URLs, not for blob: or same-origin /api/ URLs
    if (!imageUrl.startsWith("blob:") && !imageUrl.startsWith("/")) {
      imageElement.crossOrigin = "anonymous";
    }

    imageElement.onload = () => {
      console.log(
        "✅ Image loaded:",
        imageElement.width,
        "x",
        imageElement.height
      );

      // Set canvas size to match image
      canvasWidth = imageElement.width;
      canvasHeight = imageElement.height;
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;

      imageLoaded = true;
      loading = false;

      console.log("🎨 Canvas size set, calling renderMasks");
      renderMasks();
    };

    imageElement.onerror = (e) => {
      console.error("❌ Failed to load image:", e);
      loading = false;
    };

    imageElement.src = imageUrl;
  }

  function renderMasks() {
    if (!ctx || !imageElement || !imageLoaded) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Draw original image
    ctx.drawImage(imageElement, 0, 0, canvasWidth, canvasHeight);

    // Draw each polygon mask
    polygons.forEach((polygon, index) => {
      if (!polygon || polygon.length === 0) return;

      const classId = classes[index];
      const className = classNames[index] || `Class ${classId}`;
      const score = scores[index] || 0;
      const color = classColors.get(classId) || generateClassColor(classId);

      // Parse color to RGB
      const rgb = hexToRgb(color);
      if (!rgb) return;

      // Fill polygon with semi-transparent color
      ctx.fillStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${opacity})`;
      ctx.beginPath();
      polygon.forEach((point, i) => {
        if (i === 0) {
          ctx.moveTo(point[0], point[1]);
        } else {
          ctx.lineTo(point[0], point[1]);
        }
      });
      ctx.closePath();
      ctx.fill();

      // Draw outline if enabled
      if (showOutlines) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Draw label if enabled
      if (showLabels) {
        const bbox = getPolygonBoundingBox(polygon);
        if (bbox) {
          drawLabel(
            bbox.x,
            bbox.y,
            `${className} ${Math.round(score * 100)}%`,
            color
          );
        }
      }
    });

    ctx.globalAlpha = 1;
  }

  function getPolygonBoundingBox(polygon: number[][]): {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null {
    if (polygon.length === 0) return null;

    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;

    polygon.forEach((point) => {
      minX = Math.min(minX, point[0]);
      minY = Math.min(minY, point[1]);
      maxX = Math.max(maxX, point[0]);
      maxY = Math.max(maxY, point[1]);
    });

    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
    };
  }

  function drawLabel(x: number, y: number, text: string, color: string) {
    if (!ctx) return;

    const padding = 6;
    const fontSize = 14;

    ctx.font = `${fontSize}px Montserrat, sans-serif`;
    const textWidth = ctx.measureText(text).width;

    // Draw background
    ctx.fillStyle = color;
    ctx.fillRect(
      x,
      y - fontSize - padding * 2,
      textWidth + padding * 2,
      fontSize + padding * 2
    );

    // Draw text
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(text, x + padding, y - padding - 2);
  }

  function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
    // Handle hex colors
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (result) {
      return {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      };
    }

    // Handle hsl colors
    const hslMatch = hex.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
    if (hslMatch) {
      const h = parseInt(hslMatch[1]) / 360;
      const s = parseInt(hslMatch[2]) / 100;
      const l = parseInt(hslMatch[3]) / 100;

      const rgb = hslToRgb(h, s, l);
      return rgb;
    }

    return null;
  }

  function hslToRgb(
    h: number,
    s: number,
    l: number
  ): { r: number; g: number; b: number } {
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

    return {
      r: Math.round(r * 255),
      g: Math.round(g * 255),
      b: Math.round(b * 255),
    };
  }

  $: if (
    opacity !== undefined ||
    showOutlines !== undefined ||
    showLabels !== undefined
  ) {
    renderMasks();
  }
</script>

<div class="mask-overlay-container">
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading masks...</p>
    </div>
  {/if}

  <!-- Canvas always rendered but hidden while loading -->
  <div style="display: {loading ? 'none' : 'block'}; width: 100%;">
    <canvas bind:this={canvas} class="mask-canvas"></canvas>

    <div class="controls">
      <div class="control-group">
        <label for="opacity-slider">
          Opacity: {Math.round(opacity * 100)}%
        </label>
        <input
          id="opacity-slider"
          type="range"
          min="0"
          max="1"
          step="0.05"
          bind:value={opacity}
        />
      </div>

      <div class="control-group">
        <label>
          <input type="checkbox" bind:checked={showOutlines} />
          Show Outlines
        </label>
      </div>

      <div class="control-group">
        <label>
          <input type="checkbox" bind:checked={showLabels} />
          Show Labels
        </label>
      </div>
    </div>

    {#if polygons.length > 0}
      <div class="legend">
        <h4>Detected Objects ({polygons.length})</h4>
        {#each polygons as _, index}
          <div class="legend-item">
            <div
              class="color-box"
              style="background-color: {classColors.get(classes[index]) ||
                '#00FF00'}"
            ></div>
            <span class="legend-text">
              {classNames[index] || `Class ${classes[index]}`}
              {#if scores[index]}
                <span class="confidence"
                  >({Math.round(scores[index] * 100)}%)</span
                >
              {/if}
            </span>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .mask-overlay-container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    gap: 1rem;
    overflow-y: auto;
  }

  .mask-canvas {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    background: white;
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
  }

  .spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid var(--color-accent, #e1604c);
    border-radius: 50%;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  .controls {
    margin-top: 1.5rem;
    display: flex;
    gap: 2rem;
    padding: 1rem;
    background-color: #f8f9fa;
    border-radius: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .control-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .control-group label {
    font-size: 0.9rem;
    font-weight: 500;
    color: #666;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  input[type="range"] {
    width: 150px;
  }

  input[type="checkbox"] {
    cursor: pointer;
  }

  .legend {
    margin-top: 1.5rem;
    padding: 1rem;
    background-color: #f8f9fa;
    border-radius: 8px;
    min-width: 250px;
  }

  .legend h4 {
    margin: 0 0 0.75rem 0;
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #666;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid #e0e0e0;
  }

  .legend-item:last-child {
    border-bottom: none;
  }

  .color-box {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 1px solid #ddd;
    flex-shrink: 0;
  }

  .legend-text {
    font-size: 0.9rem;
    color: #333;
  }

  .confidence {
    color: #666;
    font-size: 0.85rem;
  }
</style>
