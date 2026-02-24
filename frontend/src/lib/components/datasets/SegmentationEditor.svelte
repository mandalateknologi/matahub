<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from "svelte";
  import { fabric } from "fabric";
  import { datasetsAPI } from "../../api/datasets";
  import { uiStore } from "../../stores/uiStore";
  import type { DatasetFile } from "@/lib/types";
  import {
    generateClassColor,
    loadSegmentationLabelToCanvas,
    fabricCanvasToSegmentationLabel,
    type SegmentationLabel,
  } from "../../utils/segmentationFormat";

  const dispatch = createEventDispatcher();

  export let datasetId: number;
  export let file: DatasetFile;
  export let classes: { [key: string]: string };
  export let onClose: () => void;
  export let onNext: (() => void) | null = null;
  export let onPrevious: (() => void) | null = null;

  let canvasContainer: HTMLDivElement;
  let fabricCanvas: fabric.Canvas;
  let backgroundImage: fabric.Image;
  let loading = true;
  let saving = false;
  let imageLoaded = false;

  let imageWidth = 0;
  let imageHeight = 0;
  let canvasWidth = 800;
  let canvasHeight = 600;

  let selectedClassId: number;
  let selectedClassName: string = "";
  let drawingMode: "polygon" | "brush" | "select" = "polygon";
  let isDrawingPolygon = false;
  let polygonPoints: fabric.Point[] = [];
  let tempLines: fabric.Line[] = [];
  let tempCircles: fabric.Circle[] = [];

  // Map to track polygon metadata
  let polygonData = new Map<
    fabric.Polygon,
    { class_id: number; className: string }
  >();
  let classColors = new Map<number, string>();

  // Undo stack
  let undoStack: any[] = [];
  const MAX_UNDO = 10;

  // Validation warnings
  let showValidationWarning = false;
  let validationIssues: string[] = [];

  // Polygon visibility toggle
  let showPolygons = true;

  $: {
    if (selectedClassId >= 0 && classes) {
      selectedClassName = classes[selectedClassId.toString()] || "Unknown";
    }
  }

  $: classArray = Object.entries(classes).map(([id, name]) => ({
    id: parseInt(id),
    name,
  }));

  onMount(async () => {
    await initializeCanvas();
    await loadImageAndLabels();
  });

  onDestroy(() => {
    window.removeEventListener("keydown", handleKeyDown);

    if (fabricCanvas) {
      try {
        fabricCanvas.clear();
        fabricCanvas.dispose();
        fabricCanvas = null;
      } catch (error) {
        console.error("Error disposing canvas:", error);
      }
    }
  });

  async function initializeCanvas() {
    Object.keys(classes).forEach((id) => {
      const classId = parseInt(id);
      classColors.set(classId, generateClassColor(classId));
    });

    // Initialize selectedClassId to first available class after colors are set
    if (selectedClassId === undefined) {
      selectedClassId = parseInt(Object.keys(classes)[0] || "0");
    }

    await new Promise((resolve) => setTimeout(resolve, 100));

    fabricCanvas = new fabric.Canvas("segmentation-canvas", {
      selection: true,
      backgroundColor: "#f5f5f5",
    });

    updateCanvasSize();

    fabricCanvas.on("mouse:down", handleMouseDown);
    fabricCanvas.on("mouse:move", handleMouseMove);
    fabricCanvas.on("mouse:dblclick", handleDoubleClick);
    fabricCanvas.on("selection:created", handleSelection);
    fabricCanvas.on("selection:updated", handleSelection);
    fabricCanvas.on("selection:cleared", () => {});
    // Flatten polygon transformations after user edits to prevent accumulation
    fabricCanvas.on("object:modified", handleObjectModified);

    window.addEventListener("keydown", handleKeyDown);
  }

  function updateCanvasSize() {
    if (!canvasContainer) return;

    const containerWidth = canvasContainer.clientWidth - 40;
    const containerHeight = window.innerHeight * 0.7;

    canvasWidth = containerWidth;
    canvasHeight = containerHeight;

    if (fabricCanvas) {
      const bgImage = fabricCanvas.backgroundImage;
      fabricCanvas.setDimensions({
        width: canvasWidth,
        height: canvasHeight,
      });
      if (bgImage) {
        fabricCanvas.setBackgroundImage(
          bgImage,
          fabricCanvas.renderAll.bind(fabricCanvas)
        );
      }
    }
  }

  async function loadImageAndLabels() {
    loading = true;
    imageLoaded = false;

    try {
      // Load image using native Image element (same as BoundingBoxEditor)
      const token = localStorage.getItem("access_token");
      // Encode the file path to handle special characters and spaces
      const encodedPath = file.path
        .split("/")
        .map((segment) => encodeURIComponent(segment))
        .join("/");
      const imageUrl = `/api/datasets/${datasetId}/image/${encodedPath}`;
      const urlWithToken =
        token && token !== "null" && token !== "undefined"
          ? `${imageUrl}?token=${encodeURIComponent(token)}`
          : imageUrl;

      const img = new Image();
      img.crossOrigin = "anonymous";

      img.onload = () => {
        imageWidth = img.width || 0;
        imageHeight = img.height || 0;

        // Create Fabric image from loaded element
        const fabricImg = new fabric.Image(img, {
          selectable: false,
          evented: false,
        });

        // Scale image to fit canvas while maintaining aspect ratio
        const scaleX = canvasWidth / imageWidth;
        const scaleY = canvasHeight / imageHeight;
        const scale = Math.min(scaleX, scaleY, 1);

        // Calculate centered position
        const scaledWidth = imageWidth * scale;
        const scaledHeight = imageHeight * scale;
        const left = (canvasWidth - scaledWidth) / 2;
        const top = (canvasHeight - scaledHeight) / 2;

        fabricImg.set({
          scaleX: scale,
          scaleY: scale,
          left: left,
          top: top,
        });

        fabricCanvas.setBackgroundImage(fabricImg, () => {
          fabricCanvas.renderAll();
          backgroundImage = fabricImg;
          imageLoaded = true;
          loading = false;

          // Load existing labels
          loadLabels();
        });
      };

      img.onerror = (error) => {
        console.error("Failed to load image:", error);
        uiStore.showToast("Failed to load image", "error");
        loading = false;
      };

      img.src = urlWithToken;
    } catch (error) {
      console.error("Error loading image:", error);
      uiStore.showToast("Failed to load image", "error");
      loading = false;
    }
  }

  async function loadLabels() {
    try {
      const response = await datasetsAPI.getImageLabels(datasetId, file.path);

      if (response.task_type === "segment" && response.polygons) {
        const labelData: SegmentationLabel = {
          image_width: response.image_width,
          image_height: response.image_height,
          polygons: response.polygons,
          classes: response.classes,
        };

        loadSegmentationLabelToCanvas(
          fabricCanvas,
          labelData,
          classColors,
          (polygon, class_id, className) => {
            polygonData.set(polygon, { class_id, className });
          }
        );

        // Trigger Svelte reactivity after loading all polygons
        polygonData = polygonData;

        saveToUndoStack();
      }
    } catch (error) {
      // It's okay if labels don't exist yet
    }
  }

  function handleMouseDown(event: fabric.IEvent) {
    if (drawingMode === "polygon") {
      handlePolygonDrawing(event);
    }
  }

  function handleMouseMove(event: fabric.IEvent) {
    if (!isDrawingPolygon || !event.pointer) return;

    // Update temporary line to cursor
    if (tempLines.length > 0) {
      const lastLine = tempLines[tempLines.length - 1];
      lastLine.set({
        x2: event.pointer.x,
        y2: event.pointer.y,
      });
      fabricCanvas.renderAll();
    }
  }

  function handleDoubleClick(event: fabric.IEvent) {
    if (isDrawingPolygon) {
      finishPolygon();
    }
  }

  function handlePolygonDrawing(event: fabric.IEvent) {
    if (!event.pointer) return;

    const point = new fabric.Point(event.pointer.x, event.pointer.y);

    if (!isDrawingPolygon) {
      // Start new polygon
      isDrawingPolygon = true;
      polygonPoints = [point];

      // Add first point marker
      const circle = new fabric.Circle({
        radius: 5,
        fill: classColors.get(selectedClassId) || "#00FF00",
        left: point.x - 5,
        top: point.y - 5,
        selectable: false,
        evented: false,
      });
      tempCircles.push(circle);
      fabricCanvas.add(circle);
    } else {
      // Add point to existing polygon
      const lastPoint = polygonPoints[polygonPoints.length - 1];

      // Create line from last point to new point
      const line = new fabric.Line(
        [lastPoint.x, lastPoint.y, point.x, point.y],
        {
          stroke: classColors.get(selectedClassId) || "#00FF00",
          strokeWidth: 2,
          selectable: false,
          evented: false,
        }
      );
      tempLines.push(line);
      fabricCanvas.add(line);

      // Add point marker
      const circle = new fabric.Circle({
        radius: 5,
        fill: classColors.get(selectedClassId) || "#00FF00",
        left: point.x - 5,
        top: point.y - 5,
        selectable: false,
        evented: false,
      });
      tempCircles.push(circle);
      fabricCanvas.add(circle);

      polygonPoints.push(point);

      // Create temporary line to cursor
      const tempLine = new fabric.Line([point.x, point.y, point.x, point.y], {
        stroke: classColors.get(selectedClassId) || "#00FF00",
        strokeWidth: 2,
        strokeDashArray: [5, 5],
        selectable: false,
        evented: false,
      });
      tempLines.push(tempLine);
      fabricCanvas.add(tempLine);
    }

    fabricCanvas.renderAll();
  }

  function finishPolygon() {
    if (polygonPoints.length < 3) {
      cancelPolygon();
      return;
    }

    // Remove temporary lines and circles
    clearTempDrawing();

    // Ensure polygon is properly closed by connecting to first point
    // Fabric.js automatically closes polygons, but we explicitly add visual feedback
    const color = classColors.get(selectedClassId) || "#00FF00";

    // Create polygon in canvas-space (where user drew) with NO transformations
    // polygonPoints are already in canvas-space from mouse clicks
    const polygon = new fabric.Polygon(polygonPoints, {
      fill: color + "40", // Semi-transparent
      stroke: color,
      strokeWidth: 2,
      objectCaching: false,
      selectable: true,
      hasBorders: true,
      hasControls: true,
      lockRotation: true,
      perPixelTargetFind: true,
      strokeUniform: true, // Keep stroke width consistent during scaling
      strokeLineJoin: "round", // Smooth corners
    });

    fabricCanvas.add(polygon);
    polygonData.set(polygon, {
      class_id: selectedClassId,
      className: selectedClassName,
    });
    polygonData = polygonData; // Trigger Svelte reactivity

    // Reset drawing state
    isDrawingPolygon = false;
    polygonPoints = [];

    saveToUndoStack();
    fabricCanvas.renderAll();
  }

  function cancelPolygon() {
    clearTempDrawing();
    isDrawingPolygon = false;
    polygonPoints = [];
    fabricCanvas.renderAll();
  }

  function clearTempDrawing() {
    tempLines.forEach((line) => fabricCanvas.remove(line));
    tempCircles.forEach((circle) => fabricCanvas.remove(circle));
    tempLines = [];
    tempCircles = [];
  }

  function handleSelection(event: fabric.IEvent) {
    const activeObject = fabricCanvas.getActiveObject();
    if (activeObject && activeObject.type === "polygon") {
      const data = polygonData.get(activeObject as fabric.Polygon);
      if (data) {
        selectedClassId = data.class_id;
      }
    }
  }

  /**
   * Flatten polygon transformations after user edits (move/scale/rotate)
   * This prevents transformation accumulation that causes coordinate drift
   */
  function handleObjectModified(event: fabric.IEvent) {
    const obj = event.target;
    if (obj && obj.type === "polygon") {
      const polygon = obj as fabric.Polygon;
      const data = polygonData.get(polygon);

      // Get current transformed points in canvas space
      const matrix = polygon.calcTransformMatrix();
      const canvasPoints: { x: number; y: number }[] = [];

      (polygon.points || []).forEach((point) => {
        const transformed = fabric.util.transformPoint(
          { x: point.x, y: point.y },
          matrix
        );
        canvasPoints.push(transformed);
      });

      // Remove old polygon
      polygonData.delete(polygon);
      fabricCanvas.remove(polygon);

      // Create new polygon in canvas-space with NO transformations
      const color = classColors.get(data?.class_id || 0) || "#00FF00";
      const newPolygon = new fabric.Polygon(canvasPoints, {
        fill: color + "40",
        stroke: color,
        strokeWidth: 2,
        objectCaching: false,
        selectable: true,
        hasBorders: true,
        hasControls: true,
        lockRotation: true,
        perPixelTargetFind: true,
        strokeUniform: true,
        strokeLineJoin: "round",
      });

      fabricCanvas.add(newPolygon);
      if (data) {
        polygonData.set(newPolygon, data);
      }
      polygonData = polygonData; // Trigger Svelte reactivity

      fabricCanvas.renderAll();
      saveToUndoStack();
    }
  }

  function deleteSelected() {
    const activeObjects = fabricCanvas.getActiveObjects();
    if (activeObjects.length === 0) return;

    saveToUndoStack();

    activeObjects.forEach((obj) => {
      if (obj.type === "polygon") {
        polygonData.delete(obj as fabric.Polygon);
      }
      fabricCanvas.remove(obj);
    });
    polygonData = polygonData; // Trigger Svelte reactivity

    fabricCanvas.discardActiveObject();
    fabricCanvas.renderAll();
  }

  function togglePolygonVisibility() {
    showPolygons = !showPolygons;
    fabricCanvas.getObjects("polygon").forEach((obj) => {
      obj.set({ visible: showPolygons });
    });
    fabricCanvas.renderAll();
  }

  function setDrawingMode(mode: "polygon" | "brush" | "select") {
    drawingMode = mode;
    cancelPolygon();

    if (mode === "brush") {
      fabricCanvas.isDrawingMode = true;
      fabricCanvas.freeDrawingBrush.color =
        classColors.get(selectedClassId) || "#00FF00";
      fabricCanvas.freeDrawingBrush.width = 10;
    } else {
      fabricCanvas.isDrawingMode = false;
    }

    if (mode === "select") {
      fabricCanvas.selection = true;
    } else {
      fabricCanvas.selection = false;
    }
  }

  function saveToUndoStack() {
    const state = fabricCanvas.toJSON(["class_id", "className"]);
    undoStack.push(state);
    if (undoStack.length > MAX_UNDO) {
      undoStack.shift();
    }
  }

  function undo() {
    if (undoStack.length === 0) return;

    const previousState = undoStack.pop();
    if (previousState) {
      fabricCanvas.loadFromJSON(previousState, () => {
        fabricCanvas.renderAll();
        rebuildPolygonDataMap();
      });
    }
  }

  function rebuildPolygonDataMap() {
    polygonData.clear();
    fabricCanvas.getObjects("polygon").forEach((obj) => {
      const polygon = obj as any;
      if (polygon.class_id !== undefined) {
        polygonData.set(polygon, {
          class_id: polygon.class_id,
          className: polygon.className || "",
        });
      }
    });
    polygonData = polygonData; // Trigger Svelte reactivity
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      if (isDrawingPolygon) {
        cancelPolygon();
      } else {
        onClose();
      }
    } else if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      deleteSelected();
    } else if (event.ctrlKey && event.key === "z") {
      event.preventDefault();
      undo();
    } else if (event.key === "n" || event.key === "N") {
      event.preventDefault();
      handleSaveAndNext();
    } else if (event.key === "p" || event.key === "P") {
      event.preventDefault();
      handleSaveAndPrevious();
    }
  }

  async function handleSave() {
    try {
      saving = true;

      // Validate image dimensions
      if (
        !imageWidth ||
        !imageHeight ||
        imageWidth === 0 ||
        imageHeight === 0
      ) {
        console.error("Invalid image dimensions:", { imageWidth, imageHeight });
        uiStore.showToast("Cannot save: Image not loaded properly", "error");
        saving = false;
        return;
      }

      const labelData = fabricCanvasToSegmentationLabel(
        fabricCanvas,
        polygonData,
        imageWidth,
        imageHeight,
        classes
      );

      // Validate polygon coordinates before saving
      const issues: string[] = [];
      labelData.polygons.forEach((poly, idx) => {
        poly.points.forEach((coord, coordIdx) => {
          if (coord < 0 || coord > 1) {
            issues.push(
              `Polygon ${idx + 1}, coordinate ${Math.floor(coordIdx / 2) + 1}: ${coord.toFixed(4)} is out of bounds [0-1]`
            );
          }
        });
        // Check for degenerate polygons (all points the same)
        const uniquePoints = new Set(poly.points);
        if (uniquePoints.size <= 4) {
          // 2 unique coordinates = 1 point
          issues.push(
            `Polygon ${idx + 1} may be degenerate (collapsed to a point or line)`
          );
        }
      });

      if (issues.length > 0) {
        validationIssues = issues;
        showValidationWarning = true;
        saving = false;
        return;
      }

      // Debug: Log the data being sent
      console.log("Saving labels:", {
        imageWidth,
        imageHeight,
        polygonCount: labelData.polygons.length,
        polygons: labelData.polygons,
      });

      // Debug: Detailed polygon structure
      labelData.polygons.forEach((poly, idx) => {
        console.log(`Polygon ${idx}:`, {
          class_id: poly.class_id,
          class_id_type: typeof poly.class_id,
          points: poly.points,
          points_type: typeof poly.points,
          points_length: poly.points?.length,
          first_point_type: typeof poly.points?.[0],
        });
      });

      await datasetsAPI.saveSegmentationLabels(
        datasetId,
        file.path,
        labelData.polygons
      );

      uiStore.showToast("Labels saved successfully", "success");
      dispatch("labelSaved", { file, polygonCount: labelData.polygons.length });
    } catch (error) {
      console.error("Error saving labels:", error);
      if (error.response?.data) {
        console.error("Backend validation error:", error.response.data);
      }
      uiStore.showToast("Failed to save labels", "error");
    } finally {
      saving = false;
    }
  }

  async function handleSaveAndNext() {
    await handleSave();
    if (onNext) {
      onNext();
    }
  }

  async function handleSaveAndPrevious() {
    await handleSave();
    if (onPrevious) {
      onPrevious();
    }
  }
</script>

<div class="segmentation-editor-overlay">
  <div class="segmentation-editor-modal">
    <!-- Header -->
    <div class="editor-header">
      <h3>Polygon Segmentation - {file.name}</h3>
      <button class="close-btn" on:click={onClose}>×</button>
    </div>

    <!-- Main Content -->
    <div class="editor-content">
      <!-- Sidebar -->
      <div class="sidebar">
        <div class="controls-section">
          <h4>Drawing Mode</h4>
          <div class="mode-buttons">
            <button
              class:active={drawingMode === "polygon"}
              on:click={() => setDrawingMode("polygon")}
              title="Draw polygon (click points, double-click to finish)"
            >
              <span>🔷</span> Polygon
            </button>
            <button
              class:active={drawingMode === "select"}
              on:click={() => setDrawingMode("select")}
              title="Select and edit polygons"
            >
              <span>↖</span> Select
            </button>
          </div>
        </div>

        <div class="controls-section">
          <h4>Class</h4>
          <select bind:value={selectedClassId} class="class-select">
            {#each classArray as classItem}
              <option value={classItem.id}>
                {classItem.name}
              </option>
            {/each}
          </select>
          <div
            class="color-preview"
            style="background-color: {classColors.get(selectedClassId) ||
              '#00FF00'}"
          ></div>
        </div>

        <div class="controls-section">
          <h4>Actions</h4>
          <button on:click={togglePolygonVisibility} class="action-btn">
            {showPolygons ? "👁️ Hide Polygons" : "👁️‍🗨️ Show Polygons"}
          </button>
          <button
            on:click={undo}
            disabled={undoStack.length === 0}
            class="action-btn"
          >
            ↶ Undo
          </button>
          <button on:click={deleteSelected} class="action-btn delete-btn">
            🗑️ Delete Selected
          </button>
        </div>

        <div class="controls-section">
          <h4>Polygons</h4>
          <div class="polygon-list">
            {#each Array.from(polygonData.entries()) as [polygon, data]}
              <div
                class="polygon-item"
                style="border-left: 4px solid {classColors.get(data.class_id)}"
                on:click={() => fabricCanvas.setActiveObject(polygon)}
              >
                <span class="polygon-class">{data.className}</span>
              </div>
            {/each}
            {#if polygonData.size === 0}
              <p class="no-polygons">No polygons yet</p>
            {/if}
          </div>
        </div>

        <div class="controls-section">
          <h4>Keyboard Shortcuts</h4>
          <div class="shortcuts">
            <div><kbd>N</kbd> Save & Next</div>
            <div><kbd>P</kbd> Save & Previous</div>
            <div><kbd>Ctrl+Z</kbd> Undo</div>
            <div><kbd>Del</kbd> Delete</div>
            <div><kbd>Esc</kbd> Cancel/Close</div>
            <div><kbd>Double-click</kbd> Finish polygon</div>
          </div>
        </div>
      </div>

      <!-- Canvas Area -->
      <div class="canvas-area" bind:this={canvasContainer}>
        {#if loading}
          <div class="loading-overlay">
            <div class="spinner"></div>
            <p>Loading image...</p>
          </div>
        {/if}

        <canvas id="segmentation-canvas"></canvas>

        {#if isDrawingPolygon}
          <div class="drawing-hint">
            Click to add points, double-click to finish polygon
          </div>
        {/if}
      </div>
    </div>

    <!-- Footer -->
    <div class="editor-footer">
      <div class="footer-left">
        <span class="info-text">
          Image: {imageWidth} × {imageHeight} | Polygons: {polygonData.size}
        </span>
      </div>

      <div class="footer-right">
        {#if onPrevious}
          <button
            on:click={handleSaveAndPrevious}
            disabled={saving}
            class="nav-btn"
          >
            ← Previous
          </button>
        {/if}

        <button on:click={handleSave} disabled={saving} class="save-btn">
          {saving ? "Saving..." : "Save"}
        </button>

        {#if onNext}
          <button
            on:click={handleSaveAndNext}
            disabled={saving}
            class="nav-btn"
          >
            Next →
          </button>
        {/if}

        <button on:click={onClose} class="cancel-btn">Close</button>
      </div>
    </div>
  </div>
</div>

<!-- Validation Warning Modal -->
{#if showValidationWarning}
  <div class="modal-overlay" on:click={() => (showValidationWarning = false)}>
    <div class="modal-content validation-modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>⚠️ Invalid Polygon Coordinates</h2>
        <button
          class="close-btn"
          on:click={() => (showValidationWarning = false)}
        >
          ×
        </button>
      </div>
      <div class="modal-body">
        <p class="warning-message">
          Some polygon coordinates are out of valid bounds. This may indicate
          corrupted label data from previous saves. Please review and fix the
          affected polygons.
        </p>
        <div class="issues-list">
          {#each validationIssues.slice(0, 10) as issue}
            <div class="issue-item">• {issue}</div>
          {/each}
          {#if validationIssues.length > 10}
            <div class="issue-item">
              ... and {validationIssues.length - 10} more issues
            </div>
          {/if}
        </div>
        <div class="warning-actions">
          <p><strong>Recommended actions:</strong></p>
          <ul>
            <li>Delete affected polygons and redraw them</li>
            <li>Or close without saving and report this issue</li>
          </ul>
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn-secondary"
          on:click={() => (showValidationWarning = false)}
        >
          Continue Editing
        </button>
        <button class="btn-danger" on:click={onClose}>
          Close Without Saving
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .segmentation-editor-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .segmentation-editor-modal {
    background-color: white;
    width: 95%;
    height: 90vh;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    max-width: 1600px;
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e0e0e0;
    background-color: var(--color-navy, #1d2f43);
    color: white;
    border-radius: 8px 8px 0 0;
  }

  .editor-header h3 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
  }

  .close-btn {
    background: none;
    border: none;
    color: white;
    font-size: 2rem;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s;
  }

  .close-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }

  .editor-content {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .sidebar {
    width: 320px;
    padding: 1.5rem;
    background-color: #f8f9fa;
    border-right: 1px solid #e0e0e0;
    overflow-y: auto;
  }

  .controls-section {
    margin-bottom: 1.5rem;
  }

  .controls-section h4 {
    margin: 0 0 0.75rem 0;
    font-size: 0.875rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #666;
  }

  .mode-buttons {
    display: flex;
    gap: 0.5rem;
    flex-direction: column;
  }

  .mode-buttons button {
    padding: 0.75rem;
    border: 2px solid #ddd;
    background-color: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .mode-buttons button:hover {
    border-color: var(--color-accent, #e1604c);
    background-color: #f8f9fa;
  }

  .mode-buttons button.active {
    border-color: var(--color-accent, #e1604c);
    background-color: var(--color-accent, #e1604c);
    color: white;
  }

  .class-select {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
  }

  .color-preview {
    width: 100%;
    height: 40px;
    border-radius: 6px;
    border: 1px solid #ddd;
  }

  .zoom-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    justify-content: center;
  }

  .zoom-controls button {
    width: 36px;
    height: 36px;
    border: 1px solid #ddd;
    background-color: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1.25rem;
    transition: all 0.2s;
  }

  .zoom-controls button:hover:not(:disabled) {
    border-color: var(--color-accent, #e1604c);
    color: var(--color-accent, #e1604c);
  }

  .zoom-controls button:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .zoom-controls span {
    font-weight: 600;
    min-width: 50px;
    text-align: center;
  }

  .action-btn {
    width: 100%;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border: 1px solid #ddd;
    background-color: white;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .action-btn:hover:not(:disabled) {
    border-color: var(--color-accent, #e1604c);
    background-color: #f8f9fa;
  }

  .action-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .delete-btn:hover:not(:disabled) {
    border-color: #dc3545;
    color: #dc3545;
  }

  .polygon-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid #ddd;
    border-radius: 6px;
    background-color: white;
  }

  .polygon-item {
    padding: 0.75rem;
    cursor: pointer;
    transition: background-color 0.2s;
    border-bottom: 1px solid #f0f0f0;
  }

  .polygon-item:last-child {
    border-bottom: none;
  }

  .polygon-item:hover {
    background-color: #f8f9fa;
  }

  .polygon-class {
    font-size: 0.9rem;
    font-weight: 500;
  }

  .no-polygons {
    padding: 1rem;
    text-align: center;
    color: #999;
    font-size: 0.875rem;
  }

  .shortcuts {
    font-size: 0.75rem;
    color: #666;
  }

  .shortcuts div {
    margin-bottom: 0.5rem;
  }

  .shortcuts kbd {
    background-color: #fff;
    border: 1px solid #ccc;
    border-radius: 3px;
    padding: 2px 6px;
    font-family: monospace;
    font-size: 0.75rem;
  }

  .canvas-area {
    flex: 1;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #f5f5f5;
    overflow: hidden;
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(255, 255, 255, 0.9);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 10;
  }

  .spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid var(--color-accent, #e1604c);
    border-radius: 50%;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  .drawing-hint {
    position: absolute;
    top: 1rem;
    left: 50%;
    transform: translateX(-50%);
    background-color: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-size: 0.9rem;
    pointer-events: none;
  }

  .editor-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-top: 1px solid #e0e0e0;
    background-color: #f8f9fa;
    border-radius: 0 0 8px 8px;
  }

  .footer-left {
    display: flex;
    gap: 1rem;
  }

  .info-text {
    color: #666;
    font-size: 0.875rem;
  }

  .footer-right {
    display: flex;
    gap: 0.75rem;
  }

  .footer-right button {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .save-btn {
    background-color: var(--color-accent, #e1604c);
    color: white;
  }

  .save-btn:hover:not(:disabled) {
    opacity: 0.9;
    transform: translateY(-1px);
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .nav-btn {
    background-color: var(--color-navy, #1d2f43);
    color: white;
  }

  .nav-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .cancel-btn {
    background-color: #6c757d;
    color: white;
  }

  .cancel-btn:hover {
    background-color: #5a6268;
  }

  /* Validation Modal Styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }

  .modal-content {
    background: white;
    border-radius: 12px;
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .validation-modal {
    max-width: 700px;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e0e0e0;
  }

  .modal-header h2 {
    margin: 0;
    color: #d32f2f;
    font-size: 1.5rem;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    color: #666;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
  }

  .close-btn:hover {
    background-color: #f5f5f5;
    color: #333;
  }

  .modal-body {
    padding: 1.5rem;
  }

  .warning-message {
    color: #666;
    line-height: 1.6;
    margin-bottom: 1rem;
  }

  .issues-list {
    background-color: #fff3e0;
    border-left: 4px solid #ff9800;
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 4px;
    max-height: 300px;
    overflow-y: auto;
  }

  .issue-item {
    color: #e65100;
    padding: 0.25rem 0;
    font-family: monospace;
    font-size: 0.9rem;
  }

  .warning-actions {
    margin-top: 1rem;
    padding: 1rem;
    background-color: #f5f5f5;
    border-radius: 4px;
  }

  .warning-actions p {
    margin: 0 0 0.5rem;
    color: #333;
  }

  .warning-actions ul {
    margin: 0;
    padding-left: 1.5rem;
    color: #666;
  }

  .warning-actions li {
    margin: 0.25rem 0;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid #e0e0e0;
  }

  .modal-footer button {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary {
    background-color: #6c757d;
    color: white;
  }

  .btn-secondary:hover {
    background-color: #5a6268;
  }

  .btn-danger {
    background-color: #d32f2f;
    color: white;
  }

  .btn-danger:hover {
    background-color: #b71c1c;
  }
</style>
