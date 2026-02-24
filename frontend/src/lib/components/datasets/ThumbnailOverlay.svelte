<script lang="ts">
  import { onMount } from "svelte";
  import type { BoundingBox } from "@/lib/types";

  export let imageUrl: string;
  export let boxes: BoundingBox[] = [];
  export let polygons: Array<{ class_id: number; points: number[] }> = [];
  export let classes: { [key: string]: string } = {};
  export let size: number = 200; // Thumbnail size in pixels

  let canvas: HTMLCanvasElement;
  let ctx: CanvasRenderingContext2D | null = null;
  let imageElement: HTMLImageElement | null = null;
  let imageLoaded = false;
  let imageWidth = 0;
  let imageHeight = 0;
  let currentImageUrl = "";

  // Colors for different classes
  const classColors: { [key: string]: string } = {
    "0": "#FF6B6B",
    "1": "#4ECDC4",
    "2": "#45B7D1",
    "3": "#FFA07A",
    "4": "#98D8C8",
    "5": "#F7DC6F",
    "6": "#BB8FCE",
    "7": "#85C1E2",
    "8": "#F8B739",
    "9": "#52B788",
  };

  function getClassColor(classId: string): string {
    return classColors[classId] || "#FF6B6B";
  }

  function getClassName(classId: string): string {
    return classes[classId] || `Class ${classId}`;
  }

  function loadImage() {
    // Prevent loading the same image twice
    if (currentImageUrl === imageUrl) return;

    currentImageUrl = imageUrl;
    imageLoaded = false;

    // Clean up previous image if exists
    if (imageElement) {
      imageElement.onload = null;
      imageElement.onerror = null;
    }

    imageElement = new Image();
    imageElement.crossOrigin = "anonymous";
    imageElement.onload = () => {
      if (imageElement) {
        imageWidth = imageElement.naturalWidth;
        imageHeight = imageElement.naturalHeight;
        imageLoaded = true;
        initializeCanvas();
      }
    };
    imageElement.onerror = () => {
      console.error("Failed to load thumbnail image:", imageUrl);
      imageLoaded = false;
    };
    imageElement.src = imageUrl;
  }

  function initializeCanvas() {
    if (!canvas || !imageLoaded || !imageElement) return;

    ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    canvas.width = size;
    canvas.height = size;

    // Calculate scaling and offset to fit image
    const scale = Math.min(size / imageWidth, size / imageHeight);
    const scaledWidth = imageWidth * scale;
    const scaledHeight = imageHeight * scale;
    const offsetX = (size - scaledWidth) / 2;
    const offsetY = (size - scaledHeight) / 2;

    // Clear canvas
    ctx.clearRect(0, 0, size, size);

    // Draw image
    ctx.drawImage(imageElement, offsetX, offsetY, scaledWidth, scaledHeight);

    // Draw bounding boxes if available
    if (boxes && boxes.length > 0) {
      boxes.forEach((box) => {
        drawBox(box, scale, offsetX, offsetY, scaledWidth, scaledHeight);
      });
    }

    // Draw polygons if available
    if (polygons && polygons.length > 0) {
      polygons.forEach((polygon) => {
        drawPolygon(
          polygon,
          scale,
          offsetX,
          offsetY,
          scaledWidth,
          scaledHeight
        );
      });
    }
  }

  function drawBox(
    box: BoundingBox,
    scale: number,
    offsetX: number,
    offsetY: number,
    scaledWidth: number,
    scaledHeight: number
  ) {
    if (!ctx) return;

    const color = getClassColor(box.class_id.toString());
    const className = getClassName(box.class_id.toString());

    // Convert YOLO normalized coordinates to canvas coordinates
    const boxWidth = box.width * scaledWidth;
    const boxHeight = box.height * scaledHeight;
    const boxX = offsetX + box.x_center * scaledWidth - boxWidth / 2;
    const boxY = offsetY + box.y_center * scaledHeight - boxHeight / 2;

    // Draw box outline
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.strokeRect(boxX, boxY, boxWidth, boxHeight);

    // Draw semi-transparent fill
    ctx.fillStyle = color + "20"; // 20 is hex for ~12% opacity
    ctx.fillRect(boxX, boxY, boxWidth, boxHeight);

    // Draw label background
    const labelText = className;
    ctx.font = "10px Montserrat, sans-serif";
    const textMetrics = ctx.measureText(labelText);
    const labelWidth = textMetrics.width + 8;
    const labelHeight = 16;

    // Position label above box if possible, otherwise below
    const labelX = boxX;
    const labelY = boxY > labelHeight ? boxY - labelHeight : boxY + boxHeight;

    // Draw label background
    ctx.fillStyle = color;
    ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

    // Draw label text
    ctx.fillStyle = "#FFFFFF";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, labelX + 4, labelY + labelHeight / 2);
  }

  function drawPolygon(
    polygon: { class_id: number; points: number[] },
    scale: number,
    offsetX: number,
    offsetY: number,
    scaledWidth: number,
    scaledHeight: number
  ) {
    if (!ctx || !polygon.points || polygon.points.length < 6) return;

    const color = getClassColor(polygon.class_id.toString());
    const className = getClassName(polygon.class_id.toString());

    // Start drawing polygon path
    ctx.beginPath();

    // Convert YOLO normalized coordinates to canvas coordinates
    for (let i = 0; i < polygon.points.length; i += 2) {
      const x = offsetX + polygon.points[i] * scaledWidth;
      const y = offsetY + polygon.points[i + 1] * scaledHeight;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.closePath();

    // Fill with semi-transparent color
    ctx.fillStyle = color + "20"; // 20 is hex for ~12% opacity
    ctx.fill();

    // Draw outline
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw label at the first point of polygon
    const labelX = offsetX + polygon.points[0] * scaledWidth;
    const labelY = offsetY + polygon.points[1] * scaledHeight;

    const labelText = className;
    ctx.font = "10px Montserrat, sans-serif";
    const textMetrics = ctx.measureText(labelText);
    const labelWidth = textMetrics.width + 8;
    const labelHeight = 16;

    // Draw label background
    ctx.fillStyle = color;
    ctx.fillRect(labelX, labelY - labelHeight, labelWidth, labelHeight);

    // Draw label text
    ctx.fillStyle = "#FFFFFF";
    ctx.textBaseline = "middle";
    ctx.fillText(labelText, labelX + 4, labelY - labelHeight / 2);
  }

  onMount(() => {
    loadImage();
  });

  // Reload only when imageUrl changes
  $: if (imageUrl && imageUrl !== currentImageUrl) {
    loadImage();
  }

  // Redraw when boxes or polygons change
  $: if ((boxes || polygons) && imageLoaded && canvas) {
    initializeCanvas();
  }
</script>

<canvas bind:this={canvas} class="thumbnail-canvas" />

<style>
  .thumbnail-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }
</style>
