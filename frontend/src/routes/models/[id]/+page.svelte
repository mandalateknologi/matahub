<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { location } from "svelte-spa-router";
  import { navigate } from "../../../lib/router";
  import { modelsAPI } from "../../../lib/api/models";

  import InferenceAPI from "../../../lib/api/inference";
  import type { InferencePrompt, InferenceConfig } from "@/lib/types";
  
  import { uiStore } from "../../../lib/stores/uiStore";
  import LoadingSpinner from "../../../lib/components/shared/LoadingSpinner.svelte";
  import type { PredictionResponse } from "@/lib/types";

  export let id: number | undefined = undefined;

  // Extract ID from URL
  $: if ($location) {
    const match = $location.match(/^\/models\/(\d+)/);
    if (match && match[1]) {
      const parsedId = parseInt(match[1]);
      if (parsedId !== id && !isNaN(parsedId) && parsedId > 0) {
        console.log("Extracted model id from URL:", parsedId);
        id = parsedId;
      }
    }
  }

  // Load model when id changes
  $: if (id && !isNaN(id) && id > 0) {
    loadModel();
    loadDetectionHistory();
  }

  let loading = true;
  let model: any | null = null;
  let activeTab: "main-info" | "inference" | "export" | "deployment" | "history" | "settings" =
    "main-info";

  // Inference Testing state
  let inferenceMode: "single" | "batch" = "single";
  let previewImage: File | null = null;
  let previewImageUrl: string = "";
  let detectionResult: PredictionResponse | null = null;
  let detectingImage = false;
  let confidenceThreshold = 0.25;
  let canvasElement: HTMLCanvasElement;
  let imageZoom = 1.0;

  // Model that requires prompts
  let promptRequired = false;
  let inferPrompts: InferencePrompt[] = [];
  let promptMode: "text" | "point" | "box" = "text";
  let textPrompt = "";
  let isDrawingBox = false;
  let boxStartCoords: { x: number; y: number } | null = null;
  let tempBoxCoords: { x1: number; y1: number; x2: number; y2: number } | null =
    null;

  // Batch detection state
  let batchFiles: FileList | null = null;
  let batchProgress = 0;
  let batchJobId: number | null = null;
  let batchPollingInterval: number | null = null;
  let batchResults: any[] = [];
  let batchResultsLoaded = false;

  // Usage History state
  let detectionJobs: any[] = [];
  let loadingHistory = false;
  let historyPage = 1;
  let historyLimit = 10;
  let totalJobs = 0;

  // Settings state
  let settingsForm = {
    name: "",
    description: "",
    tags: "",
  };
  let savingSettings = false;

  onMount(async () => {
    // Model and history loading now handled by reactive statement
  });

  onDestroy(async () => {
    // Clean up polling intervals
    if (batchPollingInterval) clearInterval(batchPollingInterval);
  });

  async function loadModel() {
    if (!id || isNaN(id) || id <= 0) {
      console.error("Invalid model id:", id);
      return;
    }

    try {
      loading = true;
      model = await modelsAPI.get(id);

      // Check if this is a model that requires prompts
      promptRequired = model.requires_prompts || false;
      if (promptRequired) {
        inferPrompts = [];
      }

      // Initialize settings form
      settingsForm = {
        name: model.name || "",
        description: model.description || "",
        tags: model.tags || "",
      };
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to load model", "error");
      navigate("/models");
    } finally {
      loading = false;
    }
  }

  async function loadDetectionHistory() {
    if (!id || isNaN(id) || id <= 0) {
      console.error("Invalid model id:", id);
      return;
    }

    try {
      loadingHistory = true;
      const skip = (historyPage - 1) * historyLimit;
      console.log(
        "Loading detection history for model:",
        id,
        "skip:",
        skip,
        "limit:",
        historyLimit,
      );
      const response = await InferenceAPI.getJobs(skip, historyLimit, {
        modelId: id,
      });
      console.log("Detection history response:", response);
      detectionJobs = response.jobs || [];
      totalJobs = response.total || 0;
      console.log("Loaded jobs:", detectionJobs.length, "total:", totalJobs);
    } catch (error: any) {
      console.error("Error loading detection history:", error);
      detectionJobs = []; // Ensure array on error
      totalJobs = 0;
      uiStore.showToast(
        error.message || "Failed to load detection history",
        "error",
      );
    } finally {
      loadingHistory = false;
    }
  }

  function handleImageSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      previewImage = input.files[0];
      previewImageUrl = URL.createObjectURL(previewImage);
      detectionResult = null;

      // Reset prompts when new image is selected
      if (promptRequired) {
        inferPrompts = [];
        textPrompt = "";
      }

      // Draw preview image on canvas
      setTimeout(() => {
        if (canvasElement && previewImageUrl) {
          drawImagePreview();
        }
      }, 100);
    }
  }

  function drawImagePreview() {
    if (!canvasElement || !previewImageUrl) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      const scale = imageZoom;
      canvasElement.width = img.width * scale;
      canvasElement.height = img.height * scale;

      ctx.clearRect(0, 0, canvasElement.width, canvasElement.height);
      ctx.drawImage(img, 0, 0, canvasElement.width, canvasElement.height);

      // Draw prompts if any
      if (promptRequired) {
        drawInferencePrompts();
      }
    };
    img.src = previewImageUrl;
  }

  function drawInferencePrompts() {
    if (!canvasElement) return;
    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const scale = imageZoom;

    // Draw existing prompts
    inferPrompts.forEach((prompt, index) => {
      if (prompt.type === "point" && prompt.coords) {
        const [x, y] = prompt.coords;
        const isForeground = prompt.label === 1;

        // Draw point
        ctx.beginPath();
        ctx.arc(x * scale, y * scale, 6, 0, 2 * Math.PI);
        ctx.fillStyle = isForeground ? "#4CAF50" : "#F44336";
        ctx.fill();
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (prompt.type === "box" && prompt.coords) {
        const [x1, y1, x2, y2] = prompt.coords;
        const width = (x2 - x1) * scale;
        const height = (y2 - y1) * scale;

        ctx.strokeStyle = "#2196F3";
        ctx.lineWidth = 3;
        ctx.strokeRect(x1 * scale, y1 * scale, width, height);

        // Draw corner handles
        const handleSize = 8;
        ctx.fillStyle = "#2196F3";
        ctx.fillRect(
          x1 * scale - handleSize / 2,
          y1 * scale - handleSize / 2,
          handleSize,
          handleSize,
        );
        ctx.fillRect(
          x2 * scale - handleSize / 2,
          y2 * scale - handleSize / 2,
          handleSize,
          handleSize,
        );
      }
    });

    // Draw temporary box being drawn
    if (tempBoxCoords) {
      const { x1, y1, x2, y2 } = tempBoxCoords;
      const width = (x2 - x1) * scale;
      const height = (y2 - y1) * scale;

      ctx.strokeStyle = "#2196F3";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.strokeRect(x1 * scale, y1 * scale, width, height);
      ctx.setLineDash([]);
    }
  }

  function handleCanvasClick(event: MouseEvent) {
    if (!promptRequired || !canvasElement || !previewImageUrl) return;

    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left) / imageZoom;
    const y = (event.clientY - rect.top) / imageZoom;

    if (promptMode === "point") {
      // Add point prompt (Shift = background, normal = foreground)
      const label = event.shiftKey ? 0 : 1;
      inferPrompts = [
        ...inferPrompts,
        {
          type: "point",
          coords: [Math.round(x), Math.round(y)],
          label,
        },
      ];
      drawImagePreview();
    } else if (promptMode === "box") {
      if (!isDrawingBox) {
        // Start drawing box
        isDrawingBox = true;
        boxStartCoords = { x: Math.round(x), y: Math.round(y) };
        tempBoxCoords = {
          x1: Math.round(x),
          y1: Math.round(y),
          x2: Math.round(x),
          y2: Math.round(y),
        };
      } else {
        // Finish drawing box
        if (boxStartCoords) {
          const x1 = Math.min(boxStartCoords.x, Math.round(x));
          const y1 = Math.min(boxStartCoords.y, Math.round(y));
          const x2 = Math.max(boxStartCoords.x, Math.round(x));
          const y2 = Math.max(boxStartCoords.y, Math.round(y));

          inferPrompts = [
            ...inferPrompts,
            {
              type: "box",
              coords: [x1, y1, x2, y2],
            },
          ];
        }
        isDrawingBox = false;
        boxStartCoords = null;
        tempBoxCoords = null;
        drawImagePreview();
      }
    }
  }

  function handleCanvasMouseMove(event: MouseEvent) {
    if (!promptRequired || !isDrawingBox || !boxStartCoords || !canvasElement)
      return;

    const rect = canvasElement.getBoundingClientRect();
    const x = (event.clientX - rect.left) / imageZoom;
    const y = (event.clientY - rect.top) / imageZoom;

    tempBoxCoords = {
      x1: boxStartCoords.x,
      y1: boxStartCoords.y,
      x2: Math.round(x),
      y2: Math.round(y),
    };
    drawImagePreview();
  }

  function addtextPrompt() {
    if (!textPrompt.trim()) return;

    inferPrompts = [
      ...inferPrompts,
      {
        type: "text",
        value: textPrompt.trim(),
      },
    ];
    textPrompt = "";
  }

  function removeInferencePrompt(index: number) {
    inferPrompts = inferPrompts.filter((_, i) => i !== index);
    drawImagePreview();
  }

  function clearInferencePrompts() {
    inferPrompts = [];
    textPrompt = "";
    isDrawingBox = false;
    boxStartCoords = null;
    tempBoxCoords = null;
    drawImagePreview();
  }

  function handleBatchFilesSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      batchFiles = input.files;
      batchResults = [];
      batchResultsLoaded = false;
    }
  }

  async function handleDetectImage() {
    if (!previewImage) return;

    try {
      detectingImage = true;

      let result: any;

      if (promptRequired) {
        if (inferPrompts.length === 0) {
          uiStore.showToast(
            "Please add at least one prompt (text, point, or box)",
            "warning",
          );
          detectingImage = false;
          return;
        }

        const inferOptions: InferenceConfig = {
          modelId: id!,
          prompts: inferPrompts,
          confidence: confidenceThreshold,
        };

        result = await InferenceAPI.inferSingle(previewImage, inferOptions);

        detectionResult = {
          ...result,
          boxes: result.masks?.map((m: any) => m.bbox) || [],
          scores: result.masks?.map((m: any) => m.score) || [],
          class_names: result.masks?.map((m: any) => m.class_name) || [],
          masks: result.masks || [],
        };
      } else {
        // Use regular detection API
        const inferOptions: InferenceConfig = {
          modelId: id!,
          confidence: confidenceThreshold,
        };
        
        result = await InferenceAPI.inferSingle(previewImage,inferOptions);
        detectionResult = result;
      }

      // Draw on canvas
      setTimeout(() => {
        if (canvasElement && detectionResult) {
          drawDetections();
        }
      }, 100);

      const taskLabel = promptRequired
        ? "masks"
        : model.task_type === "classify"
          ? "predictions"
          : "objects";
      const count = promptRequired
        ? result.masks?.length || 0
        : model.task_type === "classify"
          ? result.top_classes?.length || 0
          : result.boxes?.length || 0;
      uiStore.showToast(
        `Found ${count} ${taskLabel} in ${result.inference_time_ms}ms`,
        "success",
      );
    } catch (error: any) {
      uiStore.showToast(error.message || "Detection failed", "error");
    } finally {
      detectingImage = false;
    }
  }

  function drawDetections() {
    if (!canvasElement || !previewImageUrl) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      const scale = imageZoom;
      canvasElement.width = img.width * scale;
      canvasElement.height = img.height * scale;

      ctx.clearRect(0, 0, canvasElement.width, canvasElement.height);
      ctx.drawImage(img, 0, 0, canvasElement.width, canvasElement.height);

      // Handle segmentation masks with overlay
      if (
        model.task_type === "segment" &&
        detectionResult &&
        detectionResult.masks &&
        detectionResult.masks.length > 0
      ) {
        console.log("Drawing segmentation masks:", detectionResult.masks);

        // Draw semi-transparent mask overlays
        detectionResult.masks.forEach((mask: any, index: number) => {
          if (!mask || !mask.polygon) {
            console.warn("Mask missing polygon data:", mask);
            return;
          }

          // Generate a color for this mask (rotating through palette)
          const hue = (index * 137.5) % 360; // Golden angle for good color distribution

          // Polygon is array of [x,y] pairs: [[x1,y1], [x2,y2], ...]
          const polygon = mask.polygon;
          if (Array.isArray(polygon) && polygon.length > 0) {
            // Draw filled polygon
            ctx.fillStyle = `hsla(${hue}, 70%, 50%, 0.4)`; // Semi-transparent
            ctx.beginPath();

            // Move to first point
            const firstPoint = polygon[0];
            ctx.moveTo(firstPoint[0] * scale, firstPoint[1] * scale);

            // Draw lines to remaining points
            for (let i = 1; i < polygon.length; i++) {
              const point = polygon[i];
              ctx.lineTo(point[0] * scale, point[1] * scale);
            }

            ctx.closePath();
            ctx.fill();

            // Draw outline
            ctx.strokeStyle = `hsla(${hue}, 70%, 40%, 0.8)`;
            ctx.lineWidth = 2;
            ctx.stroke();
          }

          // Draw label for segmentation (using mask's own class_name)
          const className = mask.class_name || "unknown";
          const confidence = mask.score || 0;
          const label = `${className} ${(confidence * 100).toFixed(1)}%`;

          // Find top-left point for label placement (first polygon point)
          let labelX = 10;
          let labelY = 30 + index * 30;
          if (polygon && polygon.length > 0 && polygon[0]) {
            labelX = polygon[0][0] * scale;
            labelY = polygon[0][1] * scale - 5;
          }

          ctx.font = "14px Montserrat";
          const textMetrics = ctx.measureText(label);
          ctx.fillStyle = `hsla(${hue}, 70%, 40%, 0.9)`;
          ctx.fillRect(labelX, labelY - 20, textMetrics.width + 8, 22);
          ctx.fillStyle = "#FFFFFF";
          ctx.fillText(label, labelX + 4, labelY - 4);
        });
      }

      // Draw bounding boxes for detection tasks
      if (
        (model.task_type === "detect" || model.task_type === "segment") &&
        detectionResult &&
        detectionResult.boxes &&
        detectionResult.boxes.length > 0
      ) {
        detectionResult.boxes.forEach((box, index) => {
          const [x1, y1, x2, y2] = box.map((coord: number) => coord * scale);
          const width = x2 - x1;
          const height = y2 - y1;

          ctx.strokeStyle = "#E1604C";
          ctx.lineWidth = 3;
          ctx.strokeRect(x1, y1, width, height);

          ctx.fillStyle = "#E1604C";
          ctx.font = "16px Montserrat";
          const className = detectionResult?.class_names?.[index] || "unknown";
          const confidence = detectionResult?.scores?.[index] || 0;
          const label = `${className} ${(confidence * 100).toFixed(1)}%`;
          const textMetrics = ctx.measureText(label);
          ctx.fillRect(x1, y1 - 25, textMetrics.width + 10, 25);
          ctx.fillStyle = "#FFFFFF";
          ctx.fillText(label, x1 + 5, y1 - 7);
        });
      }
    };
    img.src = previewImageUrl;
  }

  async function handleBatchDetection() {
    if (!batchFiles || batchFiles.length === 0) return;

    try {
      const filesArray = Array.from(batchFiles);
      const inferOptions: InferenceConfig = {
        modelId: id!,
        confidence: confidenceThreshold,
      };

      const job = await InferenceAPI.inferBatch(
        filesArray,inferOptions
      );
      batchJobId = job.id;
      batchProgress = 0;

      // Start polling
      batchPollingInterval = window.setInterval(pollBatchJob, 2000);

      uiStore.showToast("Batch detection started", "success");
    } catch (error: any) {
      uiStore.showToast(
        error.message || "Failed to start batch detection",
        "error",
      );
    }
  }

  async function pollBatchJob() {
    if (!batchJobId) return;

    try {
      const job = await InferenceAPI.getJob(batchJobId);
      batchProgress = job.progress || 0;

      if (job.status === "completed") {
        if (batchPollingInterval) clearInterval(batchPollingInterval);
        uiStore.showToast("Batch detection completed", "success");
        await loadDetectionHistory();
        await loadBatchResults(batchJobId);
        batchJobId = null;
      } else if (job.status === "failed") {
        if (batchPollingInterval) clearInterval(batchPollingInterval);
        uiStore.showToast("Batch detection failed", "error");
        batchJobId = null;
      }
    } catch (error: any) {
      if (batchPollingInterval) clearInterval(batchPollingInterval);
      uiStore.showToast(error.message || "Failed to poll batch job", "error");
    }
  }

  async function loadBatchResults(jobId: number) {
    try {
      batchResultsLoaded = false;
      const results = await InferenceAPI.getResults(jobId);
      batchResults = results;
      batchResultsLoaded = true;

      // Draw detection boxes on canvases after a short delay
      setTimeout(async () => {
        for (let index = 0; index < results.length; index++) {
          await drawBatchResultImage(index);
        }
      }, 100);
    } catch (error: any) {
      uiStore.showToast(
        error.message || "Failed to load batch results",
        "error",
      );
    }
  }

  async function drawBatchResultImage(resultIndex: number) {
    const result = batchResults[resultIndex];
    if (!result) return;

    const canvas = document.getElementById(
      `batch-canvas-${resultIndex}`,
    ) as HTMLCanvasElement;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    try {
      const response = await InferenceAPI.getResultImage(result.id || 0);

      if (!response.ok) {
        throw new Error(
          `Failed to fetch image: ${response.status} ${response.statusText}`,
        );
      }

      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);

      const img = new Image();

      img.onload = () => {
        // Set canvas size to maintain aspect ratio
        const maxWidth = 300;
        const maxHeight = 300;
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > maxWidth) {
            height *= maxWidth / width;
            width = maxWidth;
          }
        } else {
          if (height > maxHeight) {
            width *= maxHeight / height;
            height = maxHeight;
          }
        }

        canvas.width = width;
        canvas.height = height;

        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);

        const scaleX = width / img.width;
        const scaleY = height / img.height;

        // Draw segmentation masks if present
        console.log(
          "Drawing batch result detections for result:",
          result.masks,
        );
        if (result.masks && result.masks.length > 0) {
          console.log("Drawing batch segmentation masks:", result.masks);

          result.masks.forEach((mask: any, index: number) => {
            if (!mask || !mask.polygon) {
              console.warn("Batch mask missing polygon data:", mask);
              return;
            }

            // Generate a color for this mask (same as single image)
            const hue = (index * 137.5) % 360;

            const polygon = mask.polygon;
            if (Array.isArray(polygon) && polygon.length > 0) {
              // Draw filled polygon
              ctx.fillStyle = `hsla(${hue}, 70%, 50%, 0.4)`;
              ctx.beginPath();

              // Move to first point (scaled)
              const firstPoint = polygon[0];
              ctx.moveTo(firstPoint[0] * scaleX, firstPoint[1] * scaleY);

              // Draw lines to remaining points
              for (let i = 1; i < polygon.length; i++) {
                const point = polygon[i];
                ctx.lineTo(point[0] * scaleX, point[1] * scaleY);
              }

              ctx.closePath();
              ctx.fill();

              // Draw outline
              ctx.strokeStyle = `hsla(${hue}, 70%, 40%, 0.8)`;
              ctx.lineWidth = 2;
              ctx.stroke();
            }

            // Draw label for segmentation mask
            const className = mask.class_name || "unknown";
            const confidence = mask.score || 0;
            const label = `${className} ${(confidence * 100).toFixed(1)}%`;

            // Find top-left point for label placement
            let labelX = 5;
            let labelY = 20 + index * 25;
            if (polygon && polygon.length > 0 && polygon[0]) {
              labelX = polygon[0][0] * scaleX;
              labelY = polygon[0][1] * scaleY - 5;
            }

            ctx.font = "11px Montserrat";
            const textMetrics = ctx.measureText(label);
            ctx.fillStyle = `hsla(${hue}, 70%, 40%, 0.9)`;
            ctx.fillRect(labelX, labelY - 16, textMetrics.width + 6, 18);
            ctx.fillStyle = "#FFFFFF";
            ctx.fillText(label, labelX + 3, labelY - 3);
          });
        }

        // Draw bounding boxes
        if (result.boxes && result.boxes.length > 0) {
          result.boxes.forEach((box: number[], i: number) => {
            const [x1, y1, x2, y2] = box;
            const scaledX1 = x1 * scaleX;
            const scaledY1 = y1 * scaleY;
            const scaledX2 = x2 * scaleX;
            const scaledY2 = y2 * scaleY;
            const boxWidth = scaledX2 - scaledX1;
            const boxHeight = scaledY2 - scaledY1;

            // Draw rectangle
            ctx.strokeStyle = "#E1604C";
            ctx.lineWidth = 2;
            ctx.strokeRect(scaledX1, scaledY1, boxWidth, boxHeight);

            // Draw label background (only if no masks, to avoid duplication)
            if (!result.masks || result.masks.length === 0) {
              const label = `${result.class_names[i]} ${(result.scores[i] * 100).toFixed(1)}%`;
              ctx.font = "12px Arial";
              const textWidth = ctx.measureText(label).width;
              ctx.fillStyle = "#E1604C";
              ctx.fillRect(scaledX1, scaledY1 - 20, textWidth + 8, 20);

              // Draw label text
              ctx.fillStyle = "white";
              ctx.fillText(label, scaledX1 + 4, scaledY1 - 6);
            }
          });
        }

        // Clean up the object URL after image loads
        URL.revokeObjectURL(imageUrl);
      };

      img.onerror = (e) => {
        console.error(`Failed to render image for result ${result.id}:`, e);
        URL.revokeObjectURL(imageUrl);
      };

      // Load image from blob URL
      img.src = imageUrl;
    } catch (error) {
      console.error(`Failed to load image for result ${result.id}:`, error);
    }
  }

  async function handleSaveSettings() {
    try {
      savingSettings = true;
      const updatedModel = await modelsAPI.update(
        id, 
        settingsForm.name,
        settingsForm.description,
        settingsForm.tags
      );
      // Update local model with response
      model.name = updatedModel.name;
      model.description = updatedModel.description;
      model.tags = updatedModel.tags;
      uiStore.showToast("Settings updated successfully", "success");
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to update settings", "error");
    } finally {
      savingSettings = false;
    }
  }

  async function handleDownloadModel() {
    uiStore.showToast("Download functionality coming soon", "info");
  }

  function formatDate(dateString: string) {
    return new Date(dateString).toLocaleString();
  }

  function getStatusBadgeClass(status: string) {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800";
      case "running":
        return "bg-blue-100 text-blue-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  }

  function getModeLabel(mode: string) {
    switch (mode) {
      case "single":
        return "Single Image";
      case "batch":
        return "Batch Images";
      case "video":
        return "Video";
      case "rtsp":
        return "RTSP Stream";
      default:
        return mode;
    }
  }
</script>

<div class="model-detail-page">
  {#if loading}
    <LoadingSpinner />
  {:else if model}
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <button class="back-button" on:click={() => navigate("/models")}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <div class="header-info">
          <h1>{model.name}</h1>
          <div class="header-meta">
            <span class="badge {getStatusBadgeClass(model.status)}">
              {model.status}
            </span>
            <span class="meta-item">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="3" y1="9" x2="21" y2="9" />
                <line x1="9" y1="21" x2="9" y2="9" />
              </svg>
              {model.is_system ? "System Model" : "Trained Model"}
            </span>
            <span class="meta-item">Created {formatDate(model.created_at)}</span
            >
          </div>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" on:click={handleDownloadModel}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download Model
        </button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === "main-info"}
        on:click={() => (activeTab = "main-info")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        Information
      </button>
      <button
        class="tab"
        class:active={activeTab === "inference"}
        on:click={() => (activeTab = "inference")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4" />
          <path d="M12 8h.01" />
        </svg>
        Inference Testing
      </button>
      <button
        class="tab"
        class:active={activeTab === "export"}
        on:click={() => (activeTab = "export")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        Export
      </button>
      <button
        class="tab"
        class:active={activeTab === "deployment"}
        on:click={() => (activeTab = "deployment")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
        Deployment
      </button>
      <button
        class="tab"
        class:active={activeTab === "history"}
        on:click={() => (activeTab = "history")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        Usage History
      </button>
      <button
        class="tab"
        class:active={activeTab === "settings"}
        on:click={() => (activeTab = "settings")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <circle cx="12" cy="12" r="3" />
          <path
            d="M12 1v6m0 6v6m9-9h-6m-6 0H3m15.364 6.364l-4.243-4.243m-6.122 0L3.636 17.657M17.657 3.636l-4.243 4.243m-6.122 0L3.05 3.636"
          />
        </svg>
        Settings
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      {#if activeTab === "main-info"}
        <div class="main-info-tab">
          <div class="info-grid">
            <div class="info-card">
              <h3>Model Information</h3>
              <div class="info-row">
                <span class="label">Model ID:</span>
                <span class="value">{model.id}</span>
              </div>
              <div class="info-row">
                <span class="label">Name:</span>
                <span class="value">{model.name}</span>
              </div>
              <div class="info-row">
                <span class="label">Status:</span>
                <span class="badge {getStatusBadgeClass(model.status)}">
                  {model.status}
                </span>
              </div>
              <div class="info-row">
                <span class="label">Type:</span>
                <span class="value">
                  {model.is_system ? "System Model" : "Trained Model"}
                </span>
              </div>
              <div class="info-row">
                <span class="label">Task Type:</span>
                <span class="task-type-badge task-type-{model.task_type}">
                  {#if model.task_type === "detect"}
                    🎯 Detection
                  {:else if model.task_type === "classify"}
                    📊 Classification
                  {:else if model.task_type === "segment"}
                    ✂️ Segmentation
                  {:else}
                    {model.task_type}
                  {/if}
                </span>
              </div>
              {#if model.project_id}
                <div class="info-row">
                  <span class="label">Project:</span>
                  <button
                    class="link-button"
                    on:click={() => navigate(`/projects/${model.project_id}`)}
                  >
                    View Project
                  </button>
                </div>
              {/if}
              <div class="info-row">
                <span class="label">Created:</span>
                <span class="value">{formatDate(model.created_at)}</span>
              </div>
              <div class="info-row">
                <span class="label">Updated:</span>
                <span class="value">{formatDate(model.updated_at)}</span>
              </div>
            </div>

            {#if model.metrics_json && Object.keys(model.metrics_json).length > 0}
              <div class="info-card">
                <h3>Performance Metrics</h3>

                {#if model.task_type === "classify"}
                  <!-- Classification Metrics -->
                  {#if model.metrics_json["metrics/accuracy_top1"] || model.metrics_json["top1_accuracy"]}
                    <div class="metric-row">
                      <span class="metric-label">Top-1 Accuracy:</span>
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {(model.metrics_json[
                            'metrics/accuracy_top1'
                          ] || model.metrics_json['top1_accuracy']) * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            (model.metrics_json["metrics/accuracy_top1"] ||
                              model.metrics_json["top1_accuracy"]) * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                  {#if model.metrics_json["metrics/accuracy_top5"] || model.metrics_json["top5_accuracy"]}
                    <div class="metric-row">
                      <span class="metric-label">Top-5 Accuracy:</span>
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {(model.metrics_json[
                            'metrics/accuracy_top5'
                          ] || model.metrics_json['top5_accuracy']) * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            (model.metrics_json["metrics/accuracy_top5"] ||
                              model.metrics_json["top5_accuracy"]) * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                  {#if model.metrics_json["train/loss"]}
                    <div class="metric-row">
                      <span class="metric-label">Training Loss:</span>
                      <div class="metric-bar loss-bar">
                        <span class="metric-value loss-value">
                          {model.metrics_json["train/loss"].toFixed(4)}
                        </span>
                      </div>
                    </div>
                  {/if}
                {:else}
                  <!-- Detection/Segmentation Metrics -->
                  {#if model.task_type === "segment"}
                    <!-- Segmentation-specific metrics (Mask mAP) -->
                    {#if model.metrics_json["metrics/mAP50-95(M)"]}
                      <div class="metric-row">
                        <span class="metric-label">Mask mAP50-95:</span>
                        <div class="metric-bar">
                          <div
                            class="metric-fill"
                            style="width: {model.metrics_json[
                              'metrics/mAP50-95(M)'
                            ] * 100}%"
                          />
                          <span class="metric-value">
                            {(
                              model.metrics_json["metrics/mAP50-95(M)"] * 100
                            ).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    {/if}
                    {#if model.metrics_json["metrics/mAP50(M)"]}
                      <div class="metric-row">
                        <span class="metric-label">Mask mAP50:</span>
                        <div class="metric-bar">
                          <div
                            class="metric-fill"
                            style="width: {model.metrics_json[
                              'metrics/mAP50(M)'
                            ] * 100}%"
                          />
                          <span class="metric-value">
                            {(
                              model.metrics_json["metrics/mAP50(M)"] * 100
                            ).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    {/if}
                  {/if}

                  <!-- Box metrics (shared by detection and segmentation) -->
                  {#if model.metrics_json["metrics/mAP50-95(B)"]}
                    <div class="metric-row">
                      <span class="metric-label"
                        >{model.task_type === "segment"
                          ? "Box mAP50-95:"
                          : "mAP50-95:"}</span
                      >
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {model.metrics_json[
                            'metrics/mAP50-95(B)'
                          ] * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            model.metrics_json["metrics/mAP50-95(B)"] * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                  {#if model.metrics_json["metrics/mAP50(B)"]}
                    <div class="metric-row">
                      <span class="metric-label"
                        >{model.task_type === "segment"
                          ? "Box mAP50:"
                          : "mAP50:"}</span
                      >
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {model.metrics_json[
                            'metrics/mAP50(B)'
                          ] * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            model.metrics_json["metrics/mAP50(B)"] * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                  {#if model.metrics_json["metrics/precision(B)"]}
                    <div class="metric-row">
                      <span class="metric-label">Precision:</span>
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {model.metrics_json[
                            'metrics/precision(B)'
                          ] * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            model.metrics_json["metrics/precision(B)"] * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                  {#if model.metrics_json["metrics/recall(B)"]}
                    <div class="metric-row">
                      <span class="metric-label">Recall:</span>
                      <div class="metric-bar">
                        <div
                          class="metric-fill"
                          style="width: {model.metrics_json[
                            'metrics/recall(B)'
                          ] * 100}%"
                        />
                        <span class="metric-value">
                          {(
                            model.metrics_json["metrics/recall(B)"] * 100
                          ).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  {/if}
                {/if}
              </div>
            {/if}
          </div>
        </div>
      {:else if activeTab === "inference"}
        <div class="inference-tab">
          <!-- Mode Selector -->
          {#if !promptRequired}
            <div class="mode-selector">
              <button
                class="mode-button"
                class:active={inferenceMode === "single"}
                on:click={() => (inferenceMode = "single")}
              >
                Single Image
              </button>
              <button
                class="mode-button"
                class:active={inferenceMode === "batch"}
                on:click={() => (inferenceMode = "batch")}
              >
                Batch Images
              </button>
            </div>
          {:else}
            <div class="prompt-mode-info">
              <div class="info-banner">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" />
                  <path d="M12 8h.01" />
                </svg>
                <div class="info-content">
                  <strong>🎭 Segmentation</strong>
                  <p>
                    This model requires interactive prompts for each image. Batch
                    processing is not available for prompt-based segmentation
                    models.
                  </p>
                </div>
              </div>
            </div>
          {/if}

          <!-- Single Image Mode -->
          {#if inferenceMode === "single"}
            <div class="inference-mode-content">
              <div class="controls-panel">
                <h3>
                  Single Image {model.task_type === "classify"
                    ? "Classification"
                    : model.task_type === "segment"
                      ? "Segmentation"
                      : "Detection"}
                </h3>
                <div class="form-group">
                  <label for="image-upload">Upload Image</label>
                  <input
                    id="image-upload"
                    type="file"
                    accept="image/*"
                    on:change={handleImageSelect}
                  />
                </div>
                <div class="form-group">
                  {#if !promptRequired}
                    <label for="confidence">
                      Confidence Threshold: {(
                        confidenceThreshold * 100
                      ).toFixed(0)}%
                    </label>
                    <input
                      id="confidence"
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      bind:value={confidenceThreshold}
                    />
                  {/if}
                </div>

                <!--  Prompt Controls -->
                {#if promptRequired && previewImage}
                  <div class="prompt-controls">
                    <h4>🎭 Prompts</h4>

                    <!-- Prompt Mode Selector -->
                    <div class="prompt-mode-selector">
                      <button
                        class="prompt-mode-btn"
                        class:active={promptMode === "text"}
                        on:click={() => (promptMode = "text")}
                      >
                        📝 Text
                      </button>
                      <button
                        class="prompt-mode-btn"
                        class:active={promptMode === "point"}
                        on:click={() => (promptMode = "point")}
                      >
                        📍 Point
                      </button>
                      <button
                        class="prompt-mode-btn"
                        class:active={promptMode === "box"}
                        on:click={() => (promptMode = "box")}
                      >
                        ▢ Box
                      </button>
                    </div>

                    <!-- Text Prompt Input -->
                    {#if promptMode === "text"}
                      <div class="text-prompt-input">
                        <input
                          type="text"
                          placeholder="e.g., 'white bicycle' or 'person wearing red shirt'"
                          bind:value={textPrompt}
                          on:keydown={(e) =>
                            e.key === "Enter" && addtextPrompt()}
                        />
                        <button
                          class="btn btn-secondary"
                          on:click={addtextPrompt}
                          disabled={!textPrompt.trim()}
                        >
                          Add
                        </button>
                      </div>
                    {:else if promptMode === "point"}
                      <p class="prompt-hint">
                        Click on canvas to add foreground points.<br />
                        <strong>Shift+Click</strong> for background points.
                      </p>
                    {:else if promptMode === "box"}
                      <p class="prompt-hint">
                        Click and drag on canvas to draw a bounding box.
                      </p>
                    {/if}

                    <!-- Prompts List -->
                    {#if inferPrompts.length > 0}
                      <div class="prompts-list">
                        <div class="prompts-header">
                          <span>Added Prompts ({inferPrompts.length})</span>
                          <button
                            class="btn-clear"
                            on:click={clearInferencePrompts}
                          >
                            Clear All
                          </button>
                        </div>
                        {#each inferPrompts as prompt, index}
                          <div class="prompt-item">
                            {#if prompt.type === "text"}
                              <span class="prompt-icon">📝</span>
                              <span class="prompt-text">{prompt.value}</span>
                            {:else if prompt.type === "point"}
                              <span
                                class="prompt-icon"
                                style="color: {prompt.label === 1
                                  ? '#4CAF50'
                                  : '#F44336'}"
                              >
                                📍
                              </span>
                              <span class="prompt-text">
                                {prompt.label === 1
                                  ? "Foreground"
                                  : "Background"} point at ({prompt.coords[0]}, {prompt
                                  .coords[1]})
                              </span>
                            {:else if prompt.type === "box"}
                              <span class="prompt-icon">▢</span>
                              <span class="prompt-text">
                                Box ({prompt.coords[0]}, {prompt.coords[1]}) → ({prompt
                                  .coords[2]}, {prompt.coords[3]})
                              </span>
                            {/if}
                            <button
                              class="btn-remove"
                              on:click={() => removeInferencePrompt(index)}
                            >
                              ×
                            </button>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}

                <button
                  class="btn btn-primary"
                  on:click={handleDetectImage}
                  disabled={!previewImage ||
                    detectingImage ||
                    (promptRequired && inferPrompts.length === 0)}
                >
                  {detectingImage
                    ? promptRequired
                      ? "🎯 Segmenting..."
                      : model.task_type === "classify"
                        ? "Classifying..."
                        : model.task_type === "segment"
                          ? "Segmenting..."
                          : "Detecting..."
                    : promptRequired
                      ? "🎯 Run Segmentation"
                      : model.task_type === "classify"
                        ? "Run Classification"
                        : model.task_type === "segment"
                          ? "Run Segmentation"
                          : "Run Detection"}
                </button>

                {#if detectionResult}
                  <div class="detection-stats">
                    <h4>
                      {model.task_type === "classify"
                        ? "Classification Results"
                        : model.task_type === "segment"
                          ? "Segmentation Results"
                          : "Detection Results"}
                    </h4>

                    {#if model.task_type === "classify"}
                      <!-- Classification Results -->
                      {#if detectionResult.top_classes && detectionResult.probabilities}
                        <div class="classification-results">
                          {#each detectionResult.top_classes as className, index}
                            <div class="classification-item">
                              <div class="class-label">{className}</div>
                              <div class="confidence-bar">
                                <div
                                  class="confidence-fill"
                                  style="width: {detectionResult.probabilities[
                                    index
                                  ] * 100}%"
                                ></div>
                                <span class="confidence-text"
                                  >{(
                                    detectionResult.probabilities[index] * 100
                                  ).toFixed(2)}%</span
                                >
                              </div>
                            </div>
                          {/each}
                        </div>
                      {/if}
                    {:else}
                      <!-- Detection/Segmentation Results -->
                      <div class="stat-item">
                        <span class="stat-label">
                          {model.task_type === "segment"
                            ? "Segments Detected:"
                            : "Objects Detected:"}
                        </span>
                        <span class="stat-value">
                          {detectionResult.boxes?.length ||
                            detectionResult.masks?.length ||
                            0}
                        </span>
                      </div>
                    {/if}

                    <div class="stat-item">
                      <span class="stat-label">Processing Time:</span>
                      <span class="stat-value">
                        {(detectionResult.inference_time_ms / 1000).toFixed(3)}s
                      </span>
                    </div>
                  </div>
                {/if}
              </div>

              <div class="preview-panel">
                {#if previewImageUrl}
                  <div class="canvas-container">
                    <div class="zoom-controls">
                      <button
                        class="zoom-btn"
                        on:click={() => {
                          imageZoom = Math.max(0.5, imageZoom - 0.25);
                          if (detectionResult) {
                            drawDetections();
                          } else {
                            drawImagePreview();
                          }
                        }}
                      >
                        -
                      </button>
                      <span>{(imageZoom * 100).toFixed(0)}%</span>
                      <button
                        class="zoom-btn"
                        on:click={() => {
                          imageZoom = Math.min(3, imageZoom + 0.25);
                          if (detectionResult) {
                            drawDetections();
                          } else {
                            drawImagePreview();
                          }
                        }}
                      >
                        +
                      </button>
                    </div>
                    <canvas
                      bind:this={canvasElement}
                      class="detection-canvas"
                      class:sam3-canvas={promptRequired && !detectionResult}
                      on:click={handleCanvasClick}
                      on:mousemove={handleCanvasMouseMove}
                    />
                  </div>
                {:else}
                  <div class="empty-state">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="48"
                      height="48"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                    <p>
                      Upload an image to start {model.task_type === "classify"
                        ? "classification"
                        : model.task_type === "segment"
                          ? "segmentation"
                          : "detection"}
                    </p>
                  </div>
                {/if}
              </div>
            </div>
          {:else if inferenceMode === "batch"}
            <div class="batch-mode-layout">
              <div class="batch-panel">
                <h3>
                  Batch Image {model.task_type === "classify"
                    ? "Classification"
                    : model.task_type === "segment"
                      ? "Segmentation"
                      : "Detection"}
                </h3>
                <div class="form-group">
                  <label for="batch-upload">Upload Multiple Images</label>
                  <input
                    id="batch-upload"
                    type="file"
                    accept="image/*"
                    multiple
                    on:change={handleBatchFilesSelect}
                  />
                  {#if batchFiles}
                    <p class="file-count">{batchFiles.length} files selected</p>
                  {/if}
                </div>
                <div class="form-group">
                  <label for="batch-confidence">
                    Confidence Threshold: {(confidenceThreshold * 100).toFixed(
                      0,
                    )}%
                  </label>
                  <input
                    id="batch-confidence"
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    bind:value={confidenceThreshold}
                  />
                </div>
                <button
                  class="btn btn-primary"
                  on:click={handleBatchDetection}
                  disabled={!batchFiles || batchJobId !== null}
                >
                  {batchJobId
                    ? "Processing..."
                    : model.task_type === "classify"
                      ? "Start Batch Classification"
                      : model.task_type === "segment"
                        ? "Start Batch Segmentation"
                        : "Start Batch Detection"}
                </button>

                {#if batchJobId}
                  <div class="progress-container">
                    <div class="progress-bar">
                      <div
                        class="progress-fill"
                        style="width: {batchProgress}%"
                      />
                    </div>
                    <span class="progress-text"
                      >{batchProgress.toFixed(0)}%</span
                    >
                  </div>
                {/if}
              </div>

              {#if batchResultsLoaded && batchResults.length > 0}
                <div class="batch-results-section">
                  <h3>
                    {model.task_type === "classify"
                      ? "Classification"
                      : model.task_type === "segment"
                        ? "Segmentation"
                        : "Detection"} Results ({batchResults.length} images)
                  </h3>
                  <div class="batch-results-grid">
                    {#each batchResults as result, index}
                      <div class="batch-result-card">
                        <canvas
                          id="batch-canvas-{index}"
                          class="batch-result-canvas"
                        />
                        <div class="batch-result-info">
                          <p class="result-filename">{result.file_name}</p>
                          <div class="result-stats">
                            {#if model.task_type === "classify"}
                              {#if result.top_classes && result.probabilities && result.top_classes.length > 0}
                                <span class="result-stat">
                                  🏆 {result.top_classes[0]} ({(
                                    result.probabilities[0] * 100
                                  ).toFixed(1)}%)
                                </span>
                              {/if}
                            {:else}
                              <span class="result-stat">
                                <svg
                                  xmlns="http://www.w3.org/2000/svg"
                                  width="14"
                                  height="14"
                                  viewBox="0 0 24 24"
                                  fill="none"
                                  stroke="currentColor"
                                  stroke-width="2"
                                >
                                  <path
                                    d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
                                  />
                                  <circle cx="12" cy="7" r="4" />
                                </svg>
                                {result.boxes.length} objects
                              </span>
                            {/if}
                          </div>
                        </div>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {:else if activeTab === "export"}
        <div class="export-tab">
          <div class="export-content">
            <div class="info-card export-files-card">
              <h3>Export Model</h3>
              <p class="card-description">
                Download your trained model file to deploy in your application.
              </p>
              
              {#if model.artifact_path}
                <div class="export-section">
                  <h4>Model File</h4>
                  <div class="export-file-info">
                    <div class="file-details">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="12" y1="18" x2="12" y2="12" />
                        <line x1="9" y1="15" x2="15" y2="15" />
                      </svg>
                      <div class="file-info-text">
                        <span class="file-name">{model.name}.pt</span>
                        <span class="file-path">{model.artifact_path}</span>
                      </div>
                    </div>
                    <button
                      class="btn btn-primary btn-download-model"
                      on:click={handleDownloadModel}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Download Model File
                    </button>
                  </div>
                </div>

                <div class="export-section">
                  <h4>Integration Guide</h4>
                  <p class="section-description">
                    Use this model in your application with the following code:
                  </p>
                  <div class="code-block">
                    <code>
from ultralytics import YOLO

# Load the model
model = YOLO('{model.name}.pt')

# Run inference
results = model('path/to/image.jpg', conf={confidenceThreshold})

# Process results
for result in results:
    boxes = result.boxes  # Bounding boxes
    names = result.names  # Class names
                    </code>
                  </div>
                </div>

                <div class="export-section">
                  <h4>Model Information</h4>
                  <div class="info-grid-small">
                    <div class="info-row">
                      <span class="label">Task Type:</span>
                      <span class="value">{model.task_type}</span>
                    </div>
                    <div class="info-row">
                      <span class="label">Base Model:</span>
                      <span class="value">{model.base_type || 'yolov8n'}</span>
                    </div>
                    <div class="info-row">
                      <span class="label">Status:</span>
                      <span class="badge {getStatusBadgeClass(model.status)}">
                        {model.status}
                      </span>
                    </div>
                  </div>
                </div>
              {:else}
                <div class="empty-state">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="48"
                    height="48"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <p>No deployment files available</p>
                  <p class="subtitle">
                    This model doesn't have any deployment files yet.
                  </p>
                </div>
              {/if}
            </div>
          </div>
        </div>
      {:else if activeTab === "deployment"}
        <div class="deployment-tab">
          <div class="deployment-content">
            <div class="info-card deployment-card">
              <h3>🔌 External Inference API</h3>
              <p class="card-description">
                Use your model via REST API without workflows. Perfect for integrating into your applications.
              </p>

              <!-- Model Key Display -->
              <div class="api-key-container">
                <div class="api-key-label">
                  <span class="label">Model Key:</span>
                  <span class="api-key-hint">(Keep this secret!)</span>
                </div>
                <div class="api-key-display">
                  <code class="api-key-value">{model.api_key || 'Generating...'}</code>
                  <button
                    class="btn-copy"
                    on:click={() => {
                      navigator.clipboard.writeText(model.api_key);
                      uiStore.showToast('Model key copied to clipboard', 'success');
                    }}
                    title="Copy Model Key"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  </button>
                </div>
                <div class="api-rate-limit">
                  <span class="rate-limit-icon">⚡</span>
                  <span class="rate-limit-text">Rate Limit: 100 requests/hour</span>
                </div>
              </div>

              <!-- API Endpoints -->
              <div class="api-endpoints">
                <h5>Available Endpoints</h5>
                
                <div class="api-endpoint">
                  <div class="endpoint-header">
                    <span class="http-method method-post">POST</span>
                    <code class="endpoint-url">/api/external/inference/single</code>
                  </div>
                  <p class="endpoint-description">Run inference on a single image</p>
                </div>

                {#if !model.requires_prompts}
                  <div class="api-endpoint">
                    <div class="endpoint-header">
                      <span class="http-method method-post">POST</span>
                      <code class="endpoint-url">/api/external/inference/batch</code>
                    </div>
                    <p class="endpoint-description">Run inference on multiple images</p>
                  </div>
                {/if}

                <div class="api-endpoint">
                  <div class="endpoint-header">
                    <span class="http-method method-get">GET</span>
                    <code class="endpoint-url">/api/external/inference/models/{'{model_key}'}/info</code>
                  </div>
                  <p class="endpoint-description">Get model capabilities and information</p>
                </div>

                <div class="api-endpoint">
                  <div class="endpoint-header">
                    <span class="http-method method-get">GET</span>
                    <code class="endpoint-url">/api/external/inference/usage/stats</code>
                  </div>
                  <p class="endpoint-description">Get your API usage statistics</p>
                </div>
              </div>

              <!-- Code Examples -->
              <div class="api-examples">
                <h5>Code Examples</h5>
                
                <!-- Python Example -->
                <div class="code-example">
                  <div class="code-example-header">
                    <span class="code-lang">Python</span>
                    <button
                      class="btn-copy-code"
                      on:click={() => {
                        const code = `import requests

# Single image inference
url = "http://localhost:8082/api/external/inference/single"
headers = {{"Authorization": "Bearer YOUR_API_KEY_HERE"}}
files = {{"file": open("image.jpg", "rb")}}
data = {{
    "model_key": "${model.api_key}",
    "confidence_threshold": 0.25${model.requires_prompts ? ',\n    "prompts": [{"type": "text", "value": "person"}]' : ''}
}}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()
print(f"Detected {{len(result['boxes'])}} objects")`;
                        navigator.clipboard.writeText(code);
                        uiStore.showToast('Code copied to clipboard', 'success');
                      }}
                    >
                      Copy
                    </button>
                  </div>
                  <div class="code-block">
                    <code>{`import requests

# Single image inference
url = "http://localhost:8082/api/external/inference/single"
headers = {"Authorization": "Bearer YOUR_API_KEY_HERE"}
files = {"file": open("image.jpg", "rb")}
data = {
    "model_key": "${model.api_key}",
    "confidence_threshold": 0.25${model.requires_prompts ? ',\n    "prompts": [{"type": "text", "value": "person"}]' : ''}
}

response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()
print(f"Detected {len(result['boxes'])} objects")`}</code>
                  </div>
                </div>

                <!-- cURL Example -->
                <div class="code-example">
                  <div class="code-example-header">
                    <span class="code-lang">cURL</span>
                    <button
                      class="btn-copy-code"
                      on:click={() => {
                        const code = `curl -X POST "http://localhost:8082/api/external/inference/single" \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -F "file=@image.jpg" \\
  -F "model_key=${model.api_key}" \\
  -F "confidence_threshold=0.25"${model.requires_prompts ? ' \\\n  -F "prompts=[{\\"type\\":\\"text\\",\\"value\\":\\"person\\"}]"' : ''}`;
                        navigator.clipboard.writeText(code);
                        uiStore.showToast('Code copied to clipboard', 'success');
                      }}
                    >
                      Copy
                    </button>
                  </div>
                  <div class="code-block">
                    <code>{`curl -X POST "http://localhost:8082/api/external/inference/single" \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -F "file=@image.jpg" \\
  -F "model_key=${model.api_key}" \\
  -F "confidence_threshold=0.25"${model.requires_prompts ? ' \\\n  -F "prompts=[{\\"type\\":\\"text\\",\\"value\\":\\"person\\"}]"' : ''}`}</code>
                  </div>
                </div>

                <!-- JavaScript Example -->
                <div class="code-example">
                  <div class="code-example-header">
                    <span class="code-lang">JavaScript (Fetch API)</span>
                    <button
                      class="btn-copy-code"
                      on:click={() => {
                        const code = `const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('model_key', '${model.api_key}');
formData.append('confidence_threshold', '0.25');${model.requires_prompts ? "\nformData.append('prompts', JSON.stringify([{type: 'text', value: 'person'}]));" : ''}

const response = await fetch('http://localhost:8082/api/external/inference/single', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY_HERE'
  },
  body: formData
});

const result = await response.json();
console.log(\`Detected \${result.boxes.length} objects\`);`;
                        navigator.clipboard.writeText(code);
                        uiStore.showToast('Code copied to clipboard', 'success');
                      }}
                    >
                      Copy
                    </button>
                  </div>
                  <div class="code-block">
                    <code>{`const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('model_key', '${model.api_key}');
formData.append('confidence_threshold', '0.25');${model.requires_prompts ? "\nformData.append('prompts', JSON.stringify([{type: 'text', value: 'person'}]));" : ''}

const response = await fetch('http://localhost:8082/api/external/inference/single', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY_HERE'
  },
  body: formData
});

const result = await response.json();
console.log(\`Detected \${result.boxes.length} objects\`);`}</code>
                  </div>
                </div>
              </div>

              <!-- Important Notes -->
              <div class="api-notes">
                <h5>⚠️ Important Notes</h5>
                <ul>
                  <li>Replace <code>YOUR_API_KEY_HERE</code> with your actual <strong>User API Key</strong> (from Settings → API Keys)</li>
                  <li>The <code>model_key</code> parameter uses the <strong>Model Key</strong> shown above (unique per model)</li>
                  <li>Rate limit: 100 requests per hour per user</li>
                  <li>Maximum file size: 100MB for single images</li>
                  {#if model.requires_prompts}
                    <li>This model requires prompts (text, point, or box) for inference</li>
                  {/if}
                  <li>Replace <code>http://localhost:8082</code> with your deployment URL in production</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      {:else if activeTab === "history"}
        <div class="history-tab">
          <div class="history-header">
            <h3>Detection History</h3>
            <p class="subtitle">
              Total detections: {totalJobs}
            </p>
          </div>

          {#if loadingHistory}
            <LoadingSpinner />
          {:else if !detectionJobs || detectionJobs.length === 0}
            <div class="empty-state">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <p>No detection history yet</p>
              <p class="subtitle">
                Run some detections using this model in the Inference Testing
                tab to see results here.
              </p>
            </div>
          {:else}
            <div class="history-table-container">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Created</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Results</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each detectionJobs || [] as job}
                    <tr>
                      <td>#{job.id}</td>
                      <td>{formatDate(job.created_at)}</td>
                      <td>
                        <span class="mode-badge">
                          {getModeLabel(job.mode)}
                        </span>
                      </td>
                      <td>
                        <span class="badge {getStatusBadgeClass(job.status)}">
                          {job.status}
                        </span>
                      </td>
                      <td>
                        {job.summary_json?.total_detections || 0}
                      </td>
                      <td>
                        {job.summary_json?.processing_time
                          ? `${job.summary_json.processing_time.toFixed(2)}s`
                          : "N/A"}
                      </td>
                      <td>
                        <button
                          class="btn btn-sm"
                          on:click={() =>
                            navigate(`/predictions/jobs/${job.id}`)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      {:else if activeTab === "settings"}
        <div class="settings-tab">
          <div class="settings-card">
            <h3>Model Settings</h3>
            <form on:submit|preventDefault={handleSaveSettings}>
              <div class="form-group">
                <label for="model-name">Model Name</label>
                <input
                  id="model-name"
                  type="text"
                  bind:value={settingsForm.name}
                  required
                />
              </div>

              <div class="form-group">
                <label for="model-description">
                  Description
                </label>
                <textarea
                  id="model-description"
                  bind:value={settingsForm.description}
                  rows="4"
                  placeholder="Describe your model's purpose and capabilities..."
                  maxlength="1000"
                />
                <p class="help-text">
                  {settingsForm.description?.length || 0}/1000 characters
                </p>
              </div>

              <div class="form-group">
                <label for="model-tags">
                  Tags
                </label>
                <input
                  id="model-tags"
                  type="text"
                  bind:value={settingsForm.tags}
                  placeholder="construction, ppe, safety (comma-separated)"
                  maxlength="500"
                />
                <p class="help-text">
                  Add comma-separated tags to categorize your model ({settingsForm.tags?.length || 0}/500 characters)
                </p>
              </div>

              <div class="form-actions">
                <button
                  type="submit"
                  class="btn btn-primary"
                  disabled={savingSettings}
                >
                  {savingSettings ? "Saving..." : "Save Changes"}
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  on:click={() => {
                    settingsForm.name = model.name || "";
                    settingsForm.description = model.description || "";
                    settingsForm.tags = model.tags || "";
                  }}
                >
                  Reset
                </button>
              </div>
            </form>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  /* Import modular CSS files - maintains Svelte scoping */
  @import "./styles/layout.css";
  @import "./styles/information.css";
  @import "./styles/inference-controls.css";
  @import "./styles/inference-preview.css";
  @import "./styles/batch-detection.css";
  @import "./styles/video-detection.css";
  @import "./styles/rtsp-detection.css";
  @import "./styles/data-management.css";
  @import "./styles/export-api.css";
</style>
