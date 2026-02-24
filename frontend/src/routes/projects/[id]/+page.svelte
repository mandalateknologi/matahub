<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router";
  import { location } from "svelte-spa-router";
  import { projectsAPI, type ProjectMember } from "../../../lib/api/projects";
  import { trainingAPI } from "../../../lib/api/training";
  import InferenceAPI from "../../../lib/api/inference";
  import { modelsAPI } from "../../../lib/api/models";
  import { usersAPI } from "../../../lib/api/users";
  import { uiStore } from "../../../lib/stores/uiStore";
  import {
    authStore,
    canAccessDataManagement,
  } from "../../../lib/stores/authStore";
  import LoadingSpinner from "../../../lib/components/shared/LoadingSpinner.svelte";
  import ConfirmDeleteModal from "../../../lib/components/shared/ConfirmDeleteModal.svelte";
  import MaskOverlay from "../../../lib/components/prediction/MaskOverlay.svelte";
  import PromptEditor from "../../../lib/components/visionmask/PromptEditor.svelte";
  import type {
    ProjectDetail,
    TrainingJob,
    PredictionResponse,
    DeleteConfirmation,
    UserWithResourceCounts,
  } from "@/lib/types";

  import type { InferencePrompt, InferenceConfig } from "@/lib/types";

  export let id: number | undefined = undefined;

  // Extract id from URL path since wrap props aren't working
  $: if ($location) {
    const match = $location.match(/^\/projects\/(\d+)/);
    if (match && match[1]) {
      const parsedId = parseInt(match[1]);
      if (parsedId !== id) {
        id = parsedId;
        if (id && !isNaN(id) && id > 0) {
          loadProjectData();
        }
      }
    }
  }

  let loading = true;
  let project: ProjectDetail | null = null;
  let trainingJobs: TrainingJob[] = [];
  let selectedJob: TrainingJob | null = null;
  let availableModels: any[] = [];
  let selectedModel: any | null = null;
  let activeTab: "overview" | "train" | "config" | "preview" | "models" =
    "overview";

  // Team management state
  let teamMembers: ProjectMember[] = [];
  let availableOperators: UserWithResourceCounts[] = [];
  let loadingTeam = false;
  let showAddMemberModal = false;
  let selectedOperatorId: number | null = null;

  $: currentUser = $authStore.user;
  $: isDataManager = $canAccessDataManagement;

  // Reactive variable for mask overlay visibility
  $: showMaskOverlay =
    detectionResult?.task_type === "segment" &&
    detectionResult?.masks &&
    detectionResult.masks.length > 0;

  let showArtifacts = false;
  let autoRefreshInterval: number | null = null;
  let zoomedImage: string | null = null;
  let zoomedImageLabel: string = "";

  // Preview tab state
  let previewImage: File | null = null;
  let previewImageUrl: string = "";
  let detectionResult: PredictionResponse | null = null;
  let detectingImage = false;
  let confidenceThreshold = 0.25;
  let canvasElement: HTMLCanvasElement;
  let imageZoom = 1.0; // Zoom level from 0.5x to 3x

  // SAM3 prompts state (ephemeral - reset on model change)
  let sam3Prompts: InferencePrompt[] = [];
  let showPromptEditor = false;

  // Model upload modal state
  let showUploadModal = false;
  let uploadingModel = false;
  let uploadForm = {
    name: "",
    baseModelId: null as number | null,
    taskType: "detect" as
      | "detect"
      | "classify"
      | "segment"
      | "segment_anything",
    inferenceType: "yolo" as "yolo" | "sam3",
    file: null as File | null,
    bpeFile: null as File | null,
  };
  let baseModelTypes: Array<{
    value: number;
    label: string;
    baseType: string;
  }> = [];
  let loadingBaseModels = false;

  // Delete confirmation state
  let showDeleteModal = false;
  let deleteConfirmation: DeleteConfirmation | null = null;

  // Models tab state
  let modelsViewMode: "table" | "cards" = "table";
  let showEditModal = false;
  let editingModel: any | null = null;
  let editForm = {
    name: "",
    file: null as File | null,
  };

  // Artifact image URLs
  const artifactFiles = [
    { name: "results.png", label: "Training Results" },
    { name: "confusion_matrix.png", label: "Confusion Matrix" },
    {
      name: "confusion_matrix_normalized.png",
      label: "Normalized Confusion Matrix",
    },
    {
      name: "BoxPR_curve.png",
      label: "Precision-Recall Curve",
      taskTypes: ["detect", "segment"],
    },
    {
      name: "BoxF1_curve.png",
      label: "F1 Curve",
      taskTypes: ["detect", "segment"],
    },
    {
      name: "BoxP_curve.png",
      label: "Precision Curve",
      taskTypes: ["detect", "segment"],
    },
    {
      name: "BoxR_curve.png",
      label: "Recall Curve",
      taskTypes: ["detect", "segment"],
    },
  ];

  // Get filtered artifacts based on task type
  function getFilteredArtifacts(job: TrainingJob | null) {
    const taskType = getJobTaskType(job);
    return artifactFiles.filter(
      (artifact) =>
        !artifact.taskTypes || artifact.taskTypes.includes(taskType),
    );
  }

  onMount(() => {
    startAutoRefresh();
    return () => stopAutoRefresh();
  });

  function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshInterval = window.setInterval(async () => {
      const hasRunning = trainingJobs.some((j) => j.status === "running");
      if (hasRunning) {
        await loadProjectData(true);
      }
    }, 10000); // Refresh every 10 seconds if jobs are running
  }

  function stopAutoRefresh() {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }
  }

  async function loadBaseModels() {
    if (!project) return;

    try {
      loadingBaseModels = true;
      // Load models from the SAME project
      const models = await modelsAPI.list(0, 100, project.id);
      baseModelTypes = models
        .filter((m) => m.status === "ready")
        .map((m) => ({
          value: m.id,
          label: m.name,
          baseType: m.base_type,
        }));

      // Set default if models exist
      if (baseModelTypes.length > 0 && !uploadForm.baseModelId) {
        uploadForm.baseModelId = baseModelTypes[0].value;
      }
    } catch (error: any) {
      console.error("Failed to load base models:", error);
      uiStore.showToast("Failed to load base models", "error");
    } finally {
      loadingBaseModels = false;
    }
  }

  async function loadProjectData(silent = false) {
    if (!id || isNaN(id) || id <= 0) {
      console.error("Invalid project id:", id);
      return;
    }

    try {
      if (!silent) loading = true;
      project = await projectsAPI.get(id);
      trainingJobs = await trainingAPI.list(id);

      // Load all ready models from this project
      const models = await modelsAPI.list(0, 100, id);
      availableModels = models.filter((m) => m.status === "ready");

      // Auto-select best performing completed job if none selected
      if (!selectedJob) {
        const completedJobs = trainingJobs.filter(
          (j) => j.status === "completed",
        );
        if (completedJobs.length > 0) {
          selectedJob = completedJobs.reduce((best, current) => {
            const bestMap = best.metrics_json?.["metrics/mAP50-95(B)"] || 0;
            const currentMap =
              current.metrics_json?.["metrics/mAP50-95(B)"] || 0;
            return currentMap > bestMap ? current : best;
          });
        }
      } else {
        // Update selected job with fresh data
        const updated = trainingJobs.find((j) => j.id === selectedJob?.id);
        if (updated) selectedJob = updated;
      }

      // Smart model selection: prioritize uploaded models for system projects
      if (!selectedModel && availableModels.length > 0) {
        if (project?.is_system) {
          // For system projects, prefer uploaded models (models without training jobs)
          const uploadedModels = availableModels.filter(
            (m) => !trainingJobs.some((j) => j.model_id === m.id),
          );
          selectedModel =
            uploadedModels.length > 0 ? uploadedModels[0] : availableModels[0];
        } else {
          // For regular projects, prefer models from completed training jobs
          if (selectedJob) {
            selectedModel =
              availableModels.find((m) => m.id === selectedJob.model_id) ||
              availableModels[0];
          } else {
            selectedModel = availableModels[0];
          }
        }
      } else if (selectedModel) {
        // Update selected model with fresh data
        const updated = availableModels.find((m) => m.id === selectedModel?.id);
        if (updated) selectedModel = updated;
      }
    } catch (error) {
      if (!silent) {
        uiStore.showToast("Failed to load project data", "error");
        console.error(error);
      }
    } finally {
      if (!silent) loading = false;
    }
  }

  function selectJob(job: TrainingJob) {
    selectedJob = job;
    showArtifacts = false;
  }

  function getStatusColor(status: string): string {
    const colors: Record<string, string> = {
      pending: "#FFA500",
      running: "#3B82F6",
      completed: "#10B981",
      failed: "#EF4444",
      cancelled: "#6B7280",
    };
    return colors[status] || "#6B7280";
  }

  function formatDate(dateString: string | undefined): string {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return (
      date.toLocaleDateString() +
      " " +
      date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    );
  }

  function formatMetricValue(value: any): string {
    if (value === undefined || value === null) return "N/A";
    if (typeof value === "number") {
      return value.toFixed(4);
    }
    return String(value);
  }

  function formatPercentage(value: any): string {
    if (value === undefined || value === null) return "N/A";
    if (typeof value === "number") {
      return `${(value * 100).toFixed(2)}%`;
    }
    return "N/A";
  }

  function formatDuration(
    startStr: string | undefined,
    endStr: string | undefined,
  ): string {
    if (!startStr || !endStr) return "N/A";
    const start = new Date(startStr).getTime();
    const end = new Date(endStr).getTime();
    const diff = end - start;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  }

  function getJobTaskType(job: TrainingJob | null): string {
    if (!job || !job.model_id) return "detect";
    const model = availableModels.find((m) => m.id === job.model_id);
    return model?.task_type || project?.task_type || "detect";
  }

  function hasValidMetrics(job: TrainingJob | null): boolean {
    if (!job || !job.metrics_json) return false;
    // Check for detection metrics OR classification metrics (both old and new formats)
    return (
      job.metrics_json["metrics/mAP50-95(B)"] !== undefined ||
      job.metrics_json["top1_accuracy"] !== undefined ||
      job.metrics_json["top5_accuracy"] !== undefined ||
      job.metrics_json["metrics/accuracy_top1"] !== undefined ||
      job.metrics_json["metrics/accuracy_top5"] !== undefined
    );
  }

  function getMetricOrNA(job: TrainingJob | null, key: string): string {
    if (!job || !job.metrics_json || job.metrics_json[key] === undefined) {
      return "N/A";
    }
    return formatMetricValue(job.metrics_json[key]);
  }

  function getMetricColor(value: number | undefined): string {
    if (value === undefined) return "#6B7280";
    if (value >= 0.7) return "#10B981"; // Green
    if (value >= 0.4) return "#F59E0B"; // Yellow
    return "#EF4444"; // Red
  }

  function getProjectStats() {
    const total = trainingJobs.length;
    const completed = trainingJobs.filter(
      (j) => j.status === "completed",
    ).length;
    const running = trainingJobs.filter((j) => j.status === "running").length;
    const failed = trainingJobs.filter((j) => j.status === "failed").length;

    const completedJobs = trainingJobs.filter(
      (j) => j.status === "completed" && hasValidMetrics(j),
    );
    // Get best metric (mAP for detection, top1_accuracy for classification)
    const bestmAP =
      completedJobs.length > 0
        ? Math.max(
            ...completedJobs.map(
              (j) =>
                j.metrics_json?.["metrics/mAP50-95(B)"] ||
                j.metrics_json?.["top1_accuracy"] ||
                j.metrics_json?.["metrics/accuracy_top1"] ||
                0,
            ),
          )
        : undefined;

    const jobsWithDuration = trainingJobs.filter(
      (j) => j.started_at && j.completed_at,
    );
    let avgDuration = "N/A";
    if (jobsWithDuration.length > 0) {
      const totalMs = jobsWithDuration.reduce((sum, j) => {
        const start = new Date(j.started_at!).getTime();
        const end = new Date(j.completed_at!).getTime();
        return sum + (end - start);
      }, 0);
      const avgMs = totalMs / jobsWithDuration.length;
      const hours = Math.floor(avgMs / (1000 * 60 * 60));
      const minutes = Math.floor((avgMs % (1000 * 60 * 60)) / (1000 * 60));
      avgDuration = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
    }

    return { total, completed, running, failed, bestmAP, avgDuration };
  }

  function getStatusIcon(status: string): string {
    const icons: Record<string, string> = {
      completed: "✓",
      running: "⚡",
      failed: "⚠",
      pending: "⏸",
      cancelled: "✗",
    };
    return icons[status] || "○";
  }

  function getClassCount(): number {
    if (!project?.dataset?.classes_json) return 0;
    return Object.keys(project.dataset.classes_json).length;
  }

  function getArtifactUrl(modelId: number, filename: string): string {
    return `/api/models/${modelId}/artifacts/${filename}`;
  }

  function handleArtifactError(event: Event) {
    // Hide images that fail to load (graceful degradation)
    const img = event.target as HTMLImageElement;
    img.style.display = "none";
  }

  function openImageZoom(url: string, label: string) {
    zoomedImage = url;
    zoomedImageLabel = label;
  }

  function closeImageZoom() {
    zoomedImage = null;
    zoomedImageLabel = "";
  }

  function handleModelChange(event: Event) {
    const select = event.target as HTMLSelectElement;
    const modelId = parseInt(select.value);
    selectedModel = availableModels.find((m) => m.id === modelId) || null;
    // Clear detection results when model changes
    detectionResult = null;
    // Reset SAM3 prompts when model changes (ephemeral state)
    sam3Prompts = [];
    showPromptEditor = false;
  }

  // Get task-specific label (Detection, Segmentation, Classification)
  function getTaskLabel(): string {
    const taskType = selectedModel?.task_type || "detect";
    if (taskType === "segment") return "Segmentation";
    if (taskType === "classify") return "Classification";
    return "Detection";
  }

  // Preview tab functions
  function handleImageSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      previewImage = file;
      previewImageUrl = URL.createObjectURL(file);
      detectionResult = null;

      // Draw image on canvas after load
      const img = new Image();
      img.onload = () => {
        if (canvasElement) {
          drawImageOnCanvas(img);
        }
      };
      img.src = previewImageUrl;
    }
  }

  function drawImageOnCanvas(img: HTMLImageElement) {
    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    // Resize canvas to fit image while maintaining aspect ratio and applying zoom
    const maxWidth = 800;
    const maxHeight = 600;
    let width = img.width * imageZoom;
    let height = img.height * imageZoom;

    // Scale down if exceeds max dimensions
    if (width > maxWidth * 2) {
      height = (height * (maxWidth * 2)) / width;
      width = maxWidth * 2;
    }
    if (height > maxHeight * 2) {
      width = (width * (maxHeight * 2)) / height;
      height = maxHeight * 2;
    }

    canvasElement.width = width;
    canvasElement.height = height;
    ctx.drawImage(img, 0, 0, width, height);
  }

  function drawBoundingBoxes() {
    if (!detectionResult || !canvasElement) return;
    if (!detectionResult.boxes || detectionResult.boxes.length === 0) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    const result = detectionResult; // Capture in closure
    img.onload = () => {
      drawImageOnCanvas(img);

      // Calculate scale factor: canvas dimensions / original image dimensions
      // The bounding boxes are in original image coordinates, so we need to scale them by zoom AND canvas scale
      const scaleX = canvasElement.width / img.width;
      const scaleY = canvasElement.height / img.height;

      // Draw each detection
      result.boxes!.forEach((box, i) => {
        const [x1, y1, x2, y2] = box;
        const score = result.scores[i];
        const className = result.class_names[i];

        // Scale coordinates - boxes are in original image coords, scale to canvas
        const sx1 = x1 * scaleX;
        const sy1 = y1 * scaleY;
        const sx2 = x2 * scaleX;
        const sy2 = y2 * scaleY;

        // Draw box
        ctx.strokeStyle = "#E1604C";
        ctx.lineWidth = 3 * imageZoom; // Scale line width with zoom
        ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

        // Draw label background
        const label = `${className} ${(score * 100).toFixed(1)}%`;
        const fontSize = Math.max(12, 14 * imageZoom); // Scale font with zoom
        ctx.font = `bold ${fontSize}px Montserrat, sans-serif`;
        const textWidth = ctx.measureText(label).width;
        const labelHeight = fontSize + 10;
        ctx.fillStyle = "#E1604C";
        ctx.fillRect(sx1, sy1 - labelHeight, textWidth + 10, labelHeight);

        // Draw label text
        ctx.fillStyle = "#FFFFFF";
        ctx.fillText(label, sx1 + 5, sy1 - 7);
      });
    };
    img.src = previewImageUrl;
  }

  async function runDetection() {
    if (!previewImage || !selectedModel) {
      uiStore.showToast(
        "Please select an image and ensure a model is available",
        "error",
      );
      return;
    }

    // Check if SAM3 model requires prompts
    if (selectedModel.base_type === "sam3" && sam3Prompts.length === 0) {
      uiStore.showToast(
        "Please add at least one prompt for SAM3 segmentation",
        "warning",
      );
      return;
    }

    try {
      detectingImage = true;

      // Branch detection logic based on model type
      let result: PredictionResponse;
      let inference_options: InferenceConfig = {
        modelId:selectedModel.id,
        confidence: confidenceThreshold,
        
      };

      if (selectedModel.requires_prompts) {
        inference_options.prompts = sam3Prompts;
      } 

      result = await InferenceAPI.inferPreview(
        previewImage,
        inference_options,
      )

      detectionResult = result;

      // Render result based on task type
      if (result.task_type === "classify") {
        // For classification, just display the image without boxes
        const img = new Image();
        img.onload = () => {
          drawImageOnCanvas(img);
        };
        img.src = previewImageUrl;

        uiStore.showToast(
          `Classification completed in ${result.inference_time_ms?.toFixed(0)}ms`,
          "success",
        );
      } else if (
        result.task_type === "segment" &&
        result.masks &&
        result.masks.length > 0
      ) {
        // For segmentation with masks, MaskOverlay component will render
        // No need to draw bounding boxes manually
        const instanceCount = result.masks.length;
        const modelType = selectedModel.base_type === "sam3" ? "SAM3" : "YOLO";
        uiStore.showToast(
          `${modelType} segmented ${instanceCount} instance${instanceCount !== 1 ? "s" : ""} in ${result.inference_time_ms?.toFixed(0)}ms`,
          "success",
        );
      } else {
        // For detection or segmentation without masks, draw bounding boxes
        drawBoundingBoxes();

        const objectCount = result.boxes?.length || 0;
        uiStore.showToast(
          `Detected ${objectCount} object${objectCount !== 1 ? "s" : ""} in ${result.inference_time_ms?.toFixed(0)}ms`,
          "success",
        );
      }
    } catch (error) {
      uiStore.showToast("Detection failed", "error");
      console.error(error);
    } finally {
      detectingImage = false;
    }
  }

  // Delete project handlers
  async function handleDeleteProject() {
    if (!project || project.is_system) {
      uiStore.showToast("System projects cannot be deleted", "error");
      return;
    }

    try {
      const result = await projectsAPI.delete(project.id, false);
      if (result && "requires_confirmation" in result) {
        deleteConfirmation = result;
        showDeleteModal = true;
      } else {
        uiStore.showToast(
          `Project "${project.name}" deleted successfully`,
          "success",
        );
        navigate("/projects");
      }
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to delete project", "error");
    }
  }

  async function confirmDelete() {
    if (!project) return;

    try {
      await projectsAPI.delete(project.id, true);
      uiStore.showToast(
        `Project "${project.name}" deleted successfully`,
        "success",
      );
      showDeleteModal = false;
      navigate("/projects");
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to delete project", "error");
    }
  }

  function cancelDelete() {
    showDeleteModal = false;
    deleteConfirmation = null;
  }

  async function openUploadModal() {
    uploadForm.name = "";
    uploadForm.baseModelId = null;
    uploadForm.file = null;
    showUploadModal = true;

    // Load existing models from the same project to use as base
    await loadBaseModels();
  }

  function closeUploadModal() {
    showUploadModal = false;
    uploadForm.name = "";
    uploadForm.baseModelId = null;
    uploadForm.taskType = "detect";
    uploadForm.inferenceType = "yolo";
    uploadForm.file = null;
    uploadForm.bpeFile = null;
  }

  async function handleModelUpload() {
    if (!uploadForm.name || !uploadForm.file || !project) return;

    // Validate BPE file for SegmentAnything
    if (uploadForm.taskType === "segment_anything" && !uploadForm.bpeFile) {
      uiStore.showToast(
        "BPE vocabulary file is required for SegmentAnything models",
        "error",
      );
      return;
    }

    try {
      uploadingModel = true;

      let baseType: string;

      if (uploadForm.baseModelId && baseModelTypes.length > 0) {
        // Use the base type from the selected existing model
        const selectedModel = baseModelTypes.find(
          (m) => m.value === uploadForm.baseModelId,
        );
        if (selectedModel) {
          baseType = selectedModel.baseType;
        } else {
          // Fallback: use the model name as base type
          baseType = uploadForm.name;
        }
      } else {
        // No base model selected - use the model name as base type
        baseType = uploadForm.name;
      }

      const uploadedModel = await modelsAPI.upload(
        project.id,
        uploadForm.name,
        baseType,
        uploadForm.file,
        uploadForm.taskType,
        uploadForm.bpeFile,
      );

      if (uploadedModel.status === "validating") {
        uiStore.showToast(
          "Model uploaded successfully. Validation in progress...",
          "success",
        );
      } else {
        uiStore.showToast("Model uploaded successfully", "success");
      }

      closeUploadModal();
      await loadProjectData();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to upload model", "error");
    } finally {
      uploadingModel = false;
    }
  }

  function openEditModal(model: any) {
    editingModel = model;
    editForm.name = model.name;
    showEditModal = true;
  }

  function closeEditModal() {
    showEditModal = false;
    editingModel = null;
    editForm.name = "";
    editForm.file = null;
  }

  async function handleUpdateModel() {
    if (!editingModel || !editForm.name.trim()) {
      uiStore.showToast("Please enter a model name", "error");
      return;
    }

    try {
      // If file is provided (reupload for system projects)
      if (editForm.file && project?.is_system) {
        // Delete old model and upload new one with same name
        await modelsAPI.delete(editingModel.id);
        const baseType = editingModel.base_type;
        await modelsAPI.upload(
          project.id,
          editForm.name.trim(),
          baseType,
          editForm.file,
          null, // taskType - not needed for reupload
          null, // bpeFile - not needed for reupload
        );
        uiStore.showToast("Model reuploaded successfully", "success");
      } else {
        // Just update the name
        await modelsAPI.update(editingModel.id, editForm.name.trim());
        uiStore.showToast("Model updated successfully", "success");
      }
      closeEditModal();
      await loadProjectData();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to update model", "error");
    }
  }

  async function handleDeleteModel(model: any) {
    deleteConfirmation = {
      title: "Delete Model",
      message: `Are you sure you want to delete the model "${model.name}"? This action cannot be undone.`,
      onConfirm: async () => {
        try {
          await modelsAPI.delete(model.id);
          uiStore.showToast("Model deleted successfully", "success");
          await loadProjectData();
        } catch (error: any) {
          uiStore.showToast(error.message || "Failed to delete model", "error");
        }
      },
    };
    showDeleteModal = true;
  }

  async function handleValidateModel(model: any) {
    try {
      await modelsAPI.validate(model.id);
      uiStore.showToast("Model validation started", "success");
      await loadProjectData();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to validate model", "error");
    }
  }

  function getModelSourceBadge(model: any): string {
    // Check if model was uploaded (has artifact_path but no training job)
    const hasTrainingJob = trainingJobs.some((j) => j.model_id === model.id);
    return hasTrainingJob ? "🎓 Trained" : "📤 Uploaded";
  }

  // Team Management Functions
  async function loadTeamMembers() {
    if (!project) return;

    try {
      loadingTeam = true;
      teamMembers = await projectsAPI.getMembers(project.id);
    } catch (error: any) {
      console.error("Failed to load team members:", error);
      uiStore.showToast("Failed to load team members", "error");
    } finally {
      loadingTeam = false;
    }
  }

  async function loadAvailableOperators() {
    try {
      // Load all operators who are not already in the team
      const allUsers = await usersAPI.list({
        role: "operator",
        is_active: true,
      });
      const memberIds = new Set(teamMembers.map((m) => m.user_id));
      availableOperators = allUsers.filter((u) => !memberIds.has(u.id));
    } catch (error: any) {
      console.error("Failed to load operators:", error);
      uiStore.showToast("Failed to load operators", "error");
    }
  }

  async function openAddMemberModal() {
    await loadAvailableOperators();
    showAddMemberModal = true;
    selectedOperatorId = availableOperators[0]?.id || null;
  }

  async function handleAddMember() {
    if (!project || !selectedOperatorId) return;

    try {
      await projectsAPI.addMember(project.id, selectedOperatorId);
      uiStore.showToast("Team member added successfully", "success");
      showAddMemberModal = false;
      await loadTeamMembers();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to add team member", "error");
    }
  }

  async function handleRemoveMember(userId: number, email: string) {
    if (!project) return;

    if (!confirm(`Remove ${email} from this project team?`)) return;

    try {
      await projectsAPI.removeMember(project.id, userId);
      uiStore.showToast("Team member removed successfully", "success");
      await loadTeamMembers();
    } catch (error: any) {
      uiStore.showToast(
        error.message || "Failed to remove team member",
        "error",
      );
    }
  }

  function formatDateTime(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleString();
  }
</script>

<div class="page">
  {#if loading}
    <LoadingSpinner />
  {:else if !project}
    <div class="error">
      <h2>Project Not Found</h2>
      <p>The requested project could not be found.</p>
    </div>
  {:else}
    <!-- Header -->
    <div class="header">
      <div>
        <div class="title-row">
          <h1>{project.name}</h1>
          {#if project.is_system}
            <span class="system-badge" title="System Project">🔒 SYSTEM</span>
          {/if}
        </div>
        <p class="subtitle">
          Task: {project.task_type} | Dataset: {project.dataset?.name ||
          project.dataset_id
            ? `#${project.dataset_id}`
            : "None"} | Status:
          <span class="status" style="color: {getStatusColor(project.status)}"
            >{project.status}</span
          >
        </p>
      </div>
      <div class="header-actions">
        <button class="btn-back" on:click={() => window.history.back()}>
          ← Back to Projects
        </button>
        <button class="btn-secondary" on:click={() => loadProjectData()}>
          Refresh
        </button>
        {#if project.is_system}
          <button class="btn btn-primary" on:click={openUploadModal}>
            📤 Upload Model
          </button>
        {/if}
        {#if !project.is_system}
          <button class="btn btn-danger" on:click={handleDeleteProject}>
            🗑️ Delete Project
          </button>
        {/if}
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === "overview"}
        on:click={() => (activeTab = "overview")}
      >
        <span class="tab-icon">📊</span>
        Overview
      </button>
      <button
        class="tab"
        class:active={activeTab === "train"}
        on:click={() => (activeTab = "train")}
      >
        <span class="tab-icon">⚡</span>
        Training
      </button>
      <button
        class="tab"
        class:active={activeTab === "config"}
        on:click={() => (activeTab = "config")}
      >
        <span class="tab-icon">⚙️</span>
        Configuration
      </button>
      <button
        class="tab"
        class:active={activeTab === "preview"}
        on:click={() => (activeTab = "preview")}
      >
        <span class="tab-icon">🎯</span>
        Preview & Test
      </button>
      <button
        class="tab"
        class:active={activeTab === "models"}
        on:click={() => (activeTab = "models")}
      >
        <span class="tab-icon">🤖</span>
        Models
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      {#if activeTab === "overview"}
        <!-- Overview Dashboard -->
        <div class="overview-section">
          <!-- Summary Stats -->
          <div class="stats-grid">
            <div class="stat-card gradient-blue">
              <div class="stat-icon">📁</div>
              <div class="stat-content">
                <p class="stat-label">Total Training Jobs</p>
                <p class="stat-value">{getProjectStats().total}</p>
                <p class="stat-detail">
                  {getProjectStats().completed} completed, {getProjectStats()
                    .running} running
                </p>
              </div>
            </div>

            <div class="stat-card gradient-green">
              <div class="stat-icon">🎯</div>
              <div class="stat-content">
                <p class="stat-label">Best mAP Score</p>
                <p class="stat-value">
                  {getProjectStats().bestmAP !== undefined
                    ? formatPercentage(getProjectStats().bestmAP)
                    : "N/A"}
                </p>
                <p class="stat-detail">Mean Average Precision</p>
              </div>
            </div>

            <div class="stat-card gradient-purple">
              <div class="stat-icon">⏱️</div>
              <div class="stat-content">
                <p class="stat-label">Avg Training Time</p>
                <p class="stat-value">{getProjectStats().avgDuration}</p>
                <p class="stat-detail">Per training job</p>
              </div>
            </div>

            <div class="stat-card gradient-orange">
              <div class="stat-icon">📈</div>
              <div class="stat-content">
                <p class="stat-label">Project Status</p>
                <p
                  class="stat-value"
                  style="color: {getStatusColor(project.status)}"
                >
                  {project.status.toUpperCase()}
                </p>
                <p class="stat-detail">
                  {getProjectStats().failed} failed jobs
                </p>
              </div>
            </div>
          </div>

          <!-- Recent Training History -->
          {#if trainingJobs.length > 0}
            <div class="history-section">
              <h2>Recent Training History</h2>
              <div class="timeline">
                {#each trainingJobs.slice(0, 5) as job, index}
                  <div
                    class="timeline-item"
                    class:selected={selectedJob?.id === job.id}
                  >
                    <div
                      class="timeline-marker"
                      style="background: {getStatusColor(job.status)}"
                    >
                      {getStatusIcon(job.status)}
                    </div>
                    <div
                      class="timeline-content"
                      on:click={() => selectJob(job)}
                      on:keydown={(e) => e.key === "Enter" && selectJob(job)}
                      role="button"
                      tabindex={index}
                    >
                      <div class="timeline-header">
                        <span class="timeline-title">Job #{job.id}</span>
                        <span class="timeline-date"
                          >{formatDate(job.created_at)}</span
                        >
                      </div>
                      <div class="timeline-body">
                        {#if job.status === "completed" && hasValidMetrics(job)}
                          <div class="timeline-metrics">
                            <span class="metric-badge">
                              mAP: {formatPercentage(
                                job.metrics_json?.["metrics/mAP50-95(B)"],
                              )}
                            </span>
                            <span class="metric-badge">
                              Duration: {formatDuration(
                                job.started_at,
                                job.completed_at,
                              )}
                            </span>
                          </div>
                        {:else if job.status === "running"}
                          <div class="timeline-progress">
                            <div class="mini-progress-bar">
                              <div
                                class="mini-progress-fill"
                                style="width: {job.progress}%"
                              ></div>
                            </div>
                            <span class="progress-text"
                              >{job.progress}% - Epoch {job.current_epoch}/{job.total_epochs}</span
                            >
                          </div>
                        {:else if job.status === "failed"}
                          <p class="error-text">
                            {job.error_message || "Training failed"}
                          </p>
                        {:else}
                          <p class="status-text">{job.status}</p>
                        {/if}
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {:else}
            <div class="empty-state-card">
              <div class="empty-icon">🚀</div>
              <h3>No Training Jobs Yet</h3>
              <p>Start training your first model to see results here</p>
              <button
                class="btn-primary"
                on:click={() => (activeTab = "train")}
              >
                View Training Options
              </button>
            </div>
          {/if}

          <!-- Dataset Info Card -->
          {#if project.dataset_id && project.dataset}
            <div class="dataset-card">
              <div class="dataset-header">
                <h2>
                  <span class="dataset-icon">📦</span>
                  Dataset Information
                </h2>
              </div>
              <div class="dataset-grid">
                <div class="dataset-item">
                  <span class="dataset-label">Name</span>
                  <span class="dataset-value">{project.dataset.name}</span>
                </div>
                <div class="dataset-item">
                  <span class="dataset-label">Task Type</span>
                  <span class="dataset-value">{project.task_type}</span>
                </div>
                <div class="dataset-item">
                  <span class="dataset-label">Total Images</span>
                  <span class="dataset-value"
                    >{project.dataset.images_count || 0}</span
                  >
                </div>
                <div class="dataset-item">
                  <span class="dataset-label">Total Classes</span>
                  <span class="dataset-value">{getClassCount()}</span>
                </div>
                <div class="dataset-item">
                  <span class="dataset-label">Status</span>
                  <span
                    class="dataset-value"
                    style="color: {project.dataset.status === 'valid'
                      ? '#10B981'
                      : '#F59E0B'}"
                  >
                    {project.dataset.status}
                  </span>
                </div>
                <div class="dataset-item">
                  <span class="dataset-label">Created</span>
                  <span class="dataset-value"
                    >{formatDate(project.dataset.created_at)}</span
                  >
                </div>
              </div>
            </div>
          {:else}
            <div class="info-card">
              <div class="info-icon">📦</div>
              <h3>Generic Project</h3>
              <p>
                This project doesn't have a dataset. Use the "Upload Model"
                button to add pre-trained models.
              </p>
            </div>
          {/if}
        </div>
      {:else if activeTab === "train"}
        <div class="train-layout">
          <!-- Enhanced Training Jobs List -->
          <div class="jobs-list">
            <div class="jobs-header">
              <h2>Training History</h2>
              <span class="jobs-count">{trainingJobs.length}</span>
            </div>
            {#if trainingJobs.length === 0}
              <div class="empty-state-small">
                <p class="empty-icon">📝</p>
                <p>No training jobs yet</p>
              </div>
            {:else}
              <div class="jobs">
                {#each trainingJobs as job}
                  <button
                    class="job-card-enhanced"
                    class:selected={selectedJob?.id === job.id}
                    on:click={() => selectJob(job)}
                    style="border-left-color: {getStatusColor(job.status)}"
                  >
                    <div class="job-card-main">
                      <div class="job-header-enhanced">
                        <span class="job-icon">{getStatusIcon(job.status)}</span
                        >
                        <span class="job-id">Job #{job.id}</span>
                        <span
                          class="job-status-pill"
                          style="background-color: {getStatusColor(job.status)}"
                        >
                          {job.status}
                        </span>
                      </div>
                      <div class="job-details-enhanced">
                        {#if job.status === "running"}
                          <div class="running-indicator">
                            <div class="progress-circle-small">
                              <svg viewBox="0 0 36 36" class="circular-chart">
                                <path
                                  class="circle-bg"
                                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                />
                                <path
                                  class="circle"
                                  stroke-dasharray="{job.progress}, 100"
                                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                />
                                <text x="18" y="20.35" class="percentage"
                                  >{job.progress}%</text
                                >
                              </svg>
                            </div>
                            <div class="progress-info">
                              <p class="progress-main">
                                Epoch {job.current_epoch}/{job.total_epochs}
                              </p>
                              <p class="progress-sub">
                                {job.progress}% complete
                              </p>
                            </div>
                          </div>
                        {:else if job.status === "completed"}
                          <div class="completed-info">
                            {#if getJobTaskType(job) === "classify"}
                              <p class="metric-primary">
                                Top-1: <span
                                  style="color: {getMetricColor(
                                    job.metrics_json?.['top1_accuracy'] ||
                                      job.metrics_json?.[
                                        'metrics/accuracy_top1'
                                      ],
                                  )}"
                                  >{formatPercentage(
                                    job.metrics_json?.["top1_accuracy"] ||
                                      job.metrics_json?.[
                                        "metrics/accuracy_top1"
                                      ],
                                  )}</span
                                >
                              </p>
                            {:else}
                              <p class="metric-primary">
                                mAP: <span
                                  style="color: {getMetricColor(
                                    job.metrics_json?.['metrics/mAP50-95(B)'],
                                  )}"
                                  >{formatPercentage(
                                    job.metrics_json?.["metrics/mAP50-95(B)"],
                                  )}</span
                                >
                              </p>
                            {/if}
                            <p class="metric-secondary">
                              Duration: {formatDuration(
                                job.started_at,
                                job.completed_at,
                              )}
                            </p>
                          </div>
                        {:else if job.status === "failed"}
                          <p class="error-text-small">
                            {job.error_message || "Training failed"}
                          </p>
                        {:else}
                          <p class="status-text-small">{job.status}</p>
                        {/if}
                        <p class="date-small">{formatDate(job.created_at)}</p>
                      </div>
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          </div>

          <!-- Enhanced Metrics Detail -->
          <div class="metrics-detail">
            {#if !selectedJob}
              <div class="empty-state-card">
                <div class="empty-icon">📊</div>
                <h3>No Job Selected</h3>
                <p>
                  Select a training job from the left sidebar to view detailed
                  metrics and results
                </p>
              </div>
            {:else}
              <div class="metrics-header-enhanced">
                <div>
                  <h2>Training Job #{selectedJob.id}</h2>
                  <span
                    class="job-badge"
                    style="background: {getStatusColor(selectedJob.status)}"
                  >
                    {getStatusIcon(selectedJob.status)}
                    {selectedJob.status}
                  </span>
                </div>
              </div>

              <!-- Hero Metric (for completed jobs) -->
              {#if selectedJob.status === "completed" && hasValidMetrics(selectedJob)}
                {#if getJobTaskType(selectedJob) === "classify"}
                  <!-- Classification Hero Metric -->
                  <div
                    class="hero-metric"
                    style="background: linear-gradient(135deg, {getMetricColor(
                      selectedJob.metrics_json?.['top1_accuracy'] ||
                        selectedJob.metrics_json?.['metrics/accuracy_top1'],
                    )} 0%, {getMetricColor(
                      selectedJob.metrics_json?.['top1_accuracy'] ||
                        selectedJob.metrics_json?.['metrics/accuracy_top1'],
                    )}dd 100%)"
                  >
                    <div class="hero-content">
                      <p class="hero-label">Primary Performance Metric</p>
                      <p class="hero-title">Top-1 Accuracy</p>
                      <p class="hero-value">
                        {formatPercentage(
                          selectedJob.metrics_json["top1_accuracy"] ||
                            selectedJob.metrics_json["metrics/accuracy_top1"],
                        )}
                      </p>
                      <p class="hero-subtitle">Classification Accuracy</p>
                    </div>
                    <div class="hero-icon">🎯</div>
                  </div>
                {:else}
                  <!-- Detection Hero Metric -->
                  <div
                    class="hero-metric"
                    style="background: linear-gradient(135deg, {getMetricColor(
                      selectedJob.metrics_json?.['metrics/mAP50-95(B)'],
                    )} 0%, {getMetricColor(
                      selectedJob.metrics_json?.['metrics/mAP50-95(B)'],
                    )}dd 100%)"
                  >
                    <div class="hero-content">
                      <p class="hero-label">Primary Performance Metric</p>
                      <p class="hero-title">Mean Average Precision</p>
                      <p class="hero-value">
                        {formatPercentage(
                          selectedJob.metrics_json["metrics/mAP50-95(B)"],
                        )}
                      </p>
                      <p class="hero-subtitle">mAP50-95 (IoU 0.5:0.95)</p>
                    </div>
                    <div class="hero-icon">🎯</div>
                  </div>
                {/if}

                <!-- Secondary Metrics Grid -->
                {#if getJobTaskType(selectedJob) === "classify"}
                  <!-- Classification Metrics -->
                  <div class="metrics-grid-enhanced">
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #3B82F610">
                        🥇
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">Top-1 Accuracy</p>
                        <p
                          class="metric-value-modern"
                          style="color: {getMetricColor(
                            selectedJob.metrics_json?.['top1_accuracy'] ||
                              selectedJob.metrics_json?.[
                                'metrics/accuracy_top1'
                              ],
                          )}"
                        >
                          {formatPercentage(
                            selectedJob.metrics_json["top1_accuracy"] ||
                              selectedJob.metrics_json["metrics/accuracy_top1"],
                          )}
                        </p>
                        <p class="metric-subtitle">Best Prediction Accuracy</p>
                      </div>
                    </div>
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #10B98110">
                        🥈
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">Top-5 Accuracy</p>
                        <p
                          class="metric-value-modern"
                          style="color: {getMetricColor(
                            selectedJob.metrics_json?.['top5_accuracy'] ||
                              selectedJob.metrics_json?.[
                                'metrics/accuracy_top5'
                              ],
                          )}"
                        >
                          {formatPercentage(
                            selectedJob.metrics_json["top5_accuracy"] ||
                              selectedJob.metrics_json["metrics/accuracy_top5"],
                          )}
                        </p>
                        <p class="metric-subtitle">Top-5 Prediction Accuracy</p>
                      </div>
                    </div>
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #F59E0B10">
                        📊
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">Training Loss</p>
                        <p class="metric-value-modern" style="color: #6B7280">
                          {getMetricOrNA(selectedJob, "train/loss")}
                        </p>
                        <p class="metric-subtitle">Final Training Loss</p>
                      </div>
                    </div>
                  </div>
                {:else}
                  <!-- Detection Metrics -->
                  <div class="metrics-grid-enhanced">
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #3B82F610">
                        📐
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">mAP50</p>
                        <p
                          class="metric-value-modern"
                          style="color: {getMetricColor(
                            selectedJob.metrics_json?.['metrics/mAP50(B)'],
                          )}"
                        >
                          {formatPercentage(
                            selectedJob.metrics_json["metrics/mAP50(B)"],
                          )}
                        </p>
                        <p class="metric-subtitle">mAP at IoU 0.5</p>
                      </div>
                    </div>
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #10B98110">
                        ✓
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">Precision</p>
                        <p
                          class="metric-value-modern"
                          style="color: {getMetricColor(
                            selectedJob.metrics_json?.['metrics/precision(B)'],
                          )}"
                        >
                          {formatPercentage(
                            selectedJob.metrics_json["metrics/precision(B)"],
                          )}
                        </p>
                        <p class="metric-subtitle">Detection Precision</p>
                      </div>
                    </div>
                    <div class="metric-card-modern">
                      <div class="metric-icon" style="background: #F59E0B10">
                        ↻
                      </div>
                      <div class="metric-content">
                        <p class="metric-title">Recall</p>
                        <p
                          class="metric-value-modern"
                          style="color: {getMetricColor(
                            selectedJob.metrics_json?.['metrics/recall(B)'],
                          )}"
                        >
                          {formatPercentage(
                            selectedJob.metrics_json["metrics/recall(B)"],
                          )}
                        </p>
                        <p class="metric-subtitle">Detection Recall</p>
                      </div>
                    </div>
                  </div>
                {/if}

                <!-- Training Losses -->
                <div class="loss-section-enhanced">
                  <h3>Training Losses</h3>
                  {#if getJobTaskType(selectedJob) === "classify"}
                    <!-- Classification Losses -->
                    <div class="loss-bars">
                      <div class="loss-bar-item">
                        <div class="loss-bar-header">
                          <span class="loss-bar-label">Training Loss</span>
                          <span class="loss-bar-value"
                            >{getMetricOrNA(selectedJob, "train/loss")}</span
                          >
                        </div>
                        <div class="loss-bar-bg">
                          <div
                            class="loss-bar-fill"
                            style="width: {Math.min(
                              (selectedJob.metrics_json?.['train/loss'] || 0) *
                                20,
                              100,
                            )}%; background: #3B82F6"
                          ></div>
                        </div>
                      </div>
                      <div class="loss-bar-item">
                        <div class="loss-bar-header">
                          <span class="loss-bar-label">Validation Loss</span>
                          <span class="loss-bar-value"
                            >{getMetricOrNA(selectedJob, "val/loss")}</span
                          >
                        </div>
                        <div class="loss-bar-bg">
                          <div
                            class="loss-bar-fill"
                            style="width: {Math.min(
                              (selectedJob.metrics_json?.['val/loss'] || 0) *
                                20,
                              100,
                            )}%; background: #10B981"
                          ></div>
                        </div>
                      </div>
                    </div>
                  {:else}
                    <!-- Detection Losses -->
                    <div class="loss-bars">
                      <div class="loss-bar-item">
                        <div class="loss-bar-header">
                          <span class="loss-bar-label">Box Loss</span>
                          <span class="loss-bar-value"
                            >{getMetricOrNA(
                              selectedJob,
                              "train/box_loss",
                            )}</span
                          >
                        </div>
                        <div class="loss-bar-bg">
                          <div
                            class="loss-bar-fill"
                            style="width: {Math.min(
                              (selectedJob.metrics_json?.['train/box_loss'] ||
                                0) * 20,
                              100,
                            )}%; background: #3B82F6"
                          ></div>
                        </div>
                      </div>
                      <div class="loss-bar-item">
                        <div class="loss-bar-header">
                          <span class="loss-bar-label">Class Loss</span>
                          <span class="loss-bar-value"
                            >{getMetricOrNA(
                              selectedJob,
                              "train/cls_loss",
                            )}</span
                          >
                        </div>
                        <div class="loss-bar-bg">
                          <div
                            class="loss-bar-fill"
                            style="width: {Math.min(
                              (selectedJob.metrics_json?.['train/cls_loss'] ||
                                0) * 20,
                              100,
                            )}%; background: #10B981"
                          ></div>
                        </div>
                      </div>
                      <div class="loss-bar-item">
                        <div class="loss-bar-header">
                          <span class="loss-bar-label">DFL Loss</span>
                          <span class="loss-bar-value"
                            >{getMetricOrNA(
                              selectedJob,
                              "train/dfl_loss",
                            )}</span
                          >
                        </div>
                        <div class="loss-bar-bg">
                          <div
                            class="loss-bar-fill"
                            style="width: {Math.min(
                              (selectedJob.metrics_json?.['train/dfl_loss'] ||
                                0) * 20,
                              100,
                            )}%; background: #F59E0B"
                          ></div>
                        </div>
                      </div>
                    </div>
                  {/if}
                </div>

                <!-- Key Training Artifacts (Show 3 by default) -->
                {#if selectedJob.model_id}
                  {@const filteredArtifacts = getFilteredArtifacts(selectedJob)}
                  <div class="artifacts-section-enhanced">
                    <div class="artifacts-header">
                      <h3>📈 Training Visualizations</h3>
                      <button
                        class="btn-text"
                        on:click={() => (showArtifacts = !showArtifacts)}
                      >
                        {showArtifacts ? "Show Less" : "View All"} ({filteredArtifacts.length})
                      </button>
                    </div>
                    <div class="artifacts-grid-enhanced">
                      {#each filteredArtifacts.slice(0, showArtifacts ? filteredArtifacts.length : 3) as artifact}
                        <div class="artifact-card">
                          <p class="artifact-title">{artifact.label}</p>
                          <div
                            class="artifact-image-wrapper"
                            on:click={() =>
                              openImageZoom(
                                getArtifactUrl(
                                  selectedJob.model_id,
                                  artifact.name,
                                ),
                                artifact.label,
                              )}
                            role="button"
                            tabindex="0"
                            on:keydown={(e) =>
                              e.key === "Enter" &&
                              openImageZoom(
                                getArtifactUrl(
                                  selectedJob.model_id,
                                  artifact.name,
                                ),
                                artifact.label,
                              )}
                          >
                            <img
                              src={getArtifactUrl(
                                selectedJob.model_id,
                                artifact.name,
                              )}
                              alt={artifact.label}
                              on:error={handleArtifactError}
                              loading="lazy"
                              class="artifact-image"
                            />
                            <div class="zoom-hint">🔍 Click to zoom</div>
                          </div>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}
              {:else if selectedJob.status === "running"}
                <div class="progress-section">
                  <h3>Training in Progress</h3>
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      style="width: {selectedJob.progress}%"
                    ></div>
                  </div>
                  <p>
                    Epoch {selectedJob.current_epoch} of {selectedJob.total_epochs}
                    ({selectedJob.progress}%)
                  </p>
                </div>
              {:else if selectedJob.status === "failed"}
                <div class="error-section">
                  <h3>Training Failed</h3>
                  <p class="error-text">
                    {selectedJob.error_message || "Unknown error"}
                  </p>
                </div>
              {:else}
                <p class="info-text">Training job is {selectedJob.status}</p>
              {/if}
            {/if}
          </div>
        </div>
      {:else if activeTab === "config"}
        <div class="config-section-enhanced">
          <div class="config-header">
            <h2>⚙️ Training Configuration</h2>
            <p class="config-subtitle">
              Detailed parameters and settings for Job #{selectedJob?.id ||
                "N/A"}
            </p>
          </div>

          {#if selectedJob}
            <div class="config-grid-enhanced">
              <!-- Training Parameters -->
              <div class="config-card">
                <div class="config-card-header">
                  <span class="config-icon">🎯</span>
                  <h3>Training Parameters</h3>
                </div>
                <div class="config-items">
                  <div class="config-row">
                    <span class="config-key">Total Epochs</span>
                    <span class="config-val">{selectedJob.total_epochs}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Current Epoch</span>
                    <span class="config-val">{selectedJob.current_epoch}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Progress</span>
                    <span class="config-val">{selectedJob.progress}%</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Status</span>
                    <span class="config-val">
                      <span
                        class="status-badge-small"
                        style="background: {getStatusColor(selectedJob.status)}"
                      >
                        {selectedJob.status}
                      </span>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Model Information -->
              <div class="config-card">
                <div class="config-card-header">
                  <span class="config-icon">🤖</span>
                  <h3>Model Information</h3>
                </div>
                <div class="config-items">
                  <div class="config-row">
                    <span class="config-key">Model ID</span>
                    <span class="config-val">#{selectedJob.model_id}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Project ID</span>
                    <span class="config-val">#{selectedJob.project_id}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Job ID</span>
                    <span class="config-val">#{selectedJob.id}</span>
                  </div>
                </div>
              </div>

              <!-- Dataset Information -->
              <div class="config-card">
                <div class="config-card-header">
                  <span class="config-icon">📦</span>
                  <h3>Dataset Information</h3>
                </div>
                <div class="config-items">
                  <div class="config-row">
                    <span class="config-key">Dataset Name</span>
                    <span class="config-val"
                      >{project.dataset?.name || "N/A"}</span
                    >
                  </div>
                  <div class="config-row">
                    <span class="config-key">Task Type</span>
                    <span class="config-val">{project.task_type}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Total Images</span>
                    <span class="config-val"
                      >{project.dataset?.images_count || 0}</span
                    >
                  </div>
                  <div class="config-row">
                    <span class="config-key">Number of Classes</span>
                    <span class="config-val">{getClassCount()}</span>
                  </div>
                  <div class="config-row">
                    <span class="config-key">Dataset Status</span>
                    <span class="config-val">
                      <span
                        class="status-badge-small"
                        style="background: {project.dataset?.status === 'valid'
                          ? '#10B981'
                          : '#F59E0B'}"
                      >
                        {project.dataset?.status || "unknown"}
                      </span>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Timing Information -->
              <div class="config-card">
                <div class="config-card-header">
                  <span class="config-icon">⏱️</span>
                  <h3>Timing Information</h3>
                </div>
                <div class="config-items">
                  <div class="config-row">
                    <span class="config-key">Created At</span>
                    <span class="config-val"
                      >{formatDate(selectedJob.created_at)}</span
                    >
                  </div>
                  <div class="config-row">
                    <span class="config-key">Started At</span>
                    <span class="config-val"
                      >{formatDate(selectedJob.started_at)}</span
                    >
                  </div>
                  <div class="config-row">
                    <span class="config-key">Completed At</span>
                    <span class="config-val"
                      >{formatDate(selectedJob.completed_at)}</span
                    >
                  </div>
                  <div class="config-row">
                    <span class="config-key">Duration</span>
                    <span class="config-val highlight"
                      >{formatDuration(
                        selectedJob.started_at,
                        selectedJob.completed_at,
                      )}</span
                    >
                  </div>
                </div>
              </div>
            </div>
          {:else}
            <div class="empty-state-card">
              <div class="empty-icon">⚙️</div>
              <h3>No Job Selected</h3>
              <p>Select a training job to view its detailed configuration</p>
            </div>
          {/if}
        </div>
      {:else if activeTab === "preview"}
        <div class="preview-section-enhanced">
          <div class="preview-header">
            <h2>🎯 Model Preview & Testing</h2>
            <p class="preview-subtitle">
              Test your trained model on sample images with real-time detection
            </p>
          </div>

          {#if availableModels.length === 0}
            <div class="empty-state-card">
              <div class="empty-icon">🎯</div>
              <h3>No Models Available</h3>
              <p>
                {#if project?.is_system}
                  Upload a model to the system project to start testing.
                {:else}
                  Complete a training job first to test the model with live
                  detection.
                {/if}
              </p>
              {#if project?.is_system}
                <button class="btn-primary" on:click={openUploadModal}>
                  Upload Model
                </button>
              {:else}
                <button
                  class="btn-primary"
                  on:click={() => (activeTab = "train")}
                >
                  View Training Jobs
                </button>
              {/if}
            </div>
          {:else}
            <div class="preview-layout-enhanced">
              <!-- Enhanced Controls -->
              <div class="preview-controls-enhanced">
                <!-- Model Selector -->
                <div class="controls-card model-selector-card">
                  <h3>🤖 Select Model</h3>
                  <div class="model-selector-wrapper">
                    <select
                      class="model-select"
                      value={selectedModel?.id || ""}
                      on:change={handleModelChange}
                    >
                      {#each availableModels as model}
                        <option value={model.id}>
                          {model.name}
                          {#if model.base_type}
                            ({model.base_type})
                          {/if}
                        </option>
                      {/each}
                    </select>
                    <div class="model-count-badge">
                      {availableModels.length} model{availableModels.length !==
                      1
                        ? "s"
                        : ""} available
                    </div>
                  </div>

                  {#if selectedModel}
                    <div class="model-info-display">
                      <div class="info-row">
                        <span class="info-label">Base Type:</span>
                        <span class="info-value"
                          >{selectedModel.base_type || "N/A"}</span
                        >
                      </div>
                      <div class="info-row">
                        <span class="info-label">Status:</span>
                        <span class="info-value status-ready">✓ Ready</span>
                      </div>
                      {#if selectedModel.metrics_json && selectedModel.metrics_json["metrics/mAP50-95(B)"]}
                        <div class="info-row">
                          <span class="info-label">mAP50-95:</span>
                          <span class="info-value metric-value">
                            {(
                              selectedModel.metrics_json[
                                "metrics/mAP50-95(B)"
                              ] * 100
                            ).toFixed(2)}%
                          </span>
                        </div>
                      {/if}
                      <div class="info-row">
                        <span class="info-label">Created:</span>
                        <span class="info-value">
                          {new Date(
                            selectedModel.created_at,
                          ).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  {/if}
                </div>

                <div class="controls-card">
                  <h3>🖼️ Upload Image</h3>
                  <div class="upload-area">
                    <input
                      id="image-upload"
                      type="file"
                      accept="image/*"
                      on:change={handleImageSelect}
                      class="file-input"
                    />
                    <label for="image-upload" class="upload-label">
                      {#if previewImage}
                        <span class="upload-icon">✓</span>
                        <span>{previewImage.name}</span>
                      {:else}
                        <span class="upload-icon">📁</span>
                        <span>Choose an image file</span>
                      {/if}
                    </label>
                  </div>
                </div>

                {#if selectedModel?.task_type !== "classify"}
                  {#if selectedModel?.base_type === "sam3"}
                    <!-- SAM3 Prompt Controls -->
                    <div class="controls-card">
                      <h3>🎭 SAM3 Prompts</h3>
                      <p class="info-text">
                        SAM3 requires prompts for segmentation. Add text
                        descriptions, click points, or draw boxes.
                      </p>
                      <div class="prompt-controls">
                        <button
                          class="btn-secondary"
                          on:click={() =>
                            (showPromptEditor = !showPromptEditor)}
                        >
                          {showPromptEditor ? "Hide" : "Show"} Prompt Editor
                        </button>
                        <div class="prompt-count">
                          <span class="stat-icon">📝</span>
                          <span
                            ><strong>{sam3Prompts.length}</strong>
                            prompt{sam3Prompts.length !== 1 ? "s" : ""}</span
                          >
                        </div>
                        {#if sam3Prompts.length > 0}
                          <button
                            class="btn-text"
                            on:click={() => {
                              sam3Prompts = [];
                              detectionResult = null;
                            }}
                          >
                            Clear All Prompts
                          </button>
                        {/if}
                      </div>
                    </div>
                  {:else}
                    <!-- YOLO Confidence Threshold -->
                    <div class="controls-card">
                      <h3>🎚️ {getTaskLabel()} Settings</h3>
                      <div class="slider-control">
                        <label for="confidence" class="slider-label">
                          <span>Confidence Threshold</span>
                          <span class="slider-value"
                            >{(confidenceThreshold * 100).toFixed(0)}%</span
                          >
                        </label>
                        <input
                          id="confidence"
                          type="range"
                          min="0.1"
                          max="0.9"
                          step="0.05"
                          bind:value={confidenceThreshold}
                          class="slider"
                        />
                        <div class="slider-markers">
                          <span>Low (10%)</span>
                          <span>High (90%)</span>
                        </div>
                      </div>
                    </div>
                  {/if}
                {/if}

                {#if !showMaskOverlay}
                  <div class="controls-card">
                    <h3>🔍 Image Zoom</h3>
                    <div class="slider-control">
                      <label for="zoom" class="slider-label">
                        <span>Zoom Level</span>
                        <span class="slider-value"
                          >{(imageZoom * 100).toFixed(0)}%</span
                        >
                      </label>
                      <input
                        id="zoom"
                        type="range"
                        min="0.5"
                        max="3.0"
                        step="0.1"
                        bind:value={imageZoom}
                        on:input={() => {
                          if (previewImageUrl) {
                            const img = new Image();
                            img.onload = () => {
                              if (
                                detectionResult &&
                                detectionResult.task_type !== "classify"
                              ) {
                                drawBoundingBoxes();
                              } else {
                                drawImageOnCanvas(img);
                              }
                            };
                            img.src = previewImageUrl;
                          }
                        }}
                        class="slider"
                      />
                      <div class="slider-markers">
                        <span>50%</span>
                        <span>300%</span>
                      </div>
                    </div>
                  </div>
                {/if}

                <button
                  class="btn-detect"
                  on:click={runDetection}
                  disabled={!previewImage || !selectedModel || detectingImage}
                >
                  {#if detectingImage}
                    <span class="spinner"></span>
                    Running...
                  {:else}
                    <span>🚀</span>
                    {selectedModel?.task_type === "classify"
                      ? "Classify Image"
                      : `Run ${getTaskLabel()}`}
                  {/if}
                </button>

                {#if detectionResult}
                  <div class="results-card">
                    <h3>
                      📊 {getTaskLabel()} Results
                    </h3>

                    {#if detectionResult.task_type === "classify"}
                      <!-- Classification Results -->
                      <div class="results-stats">
                        <div class="result-stat">
                          <span class="stat-icon">🏆</span>
                          <div class="stat-info">
                            <p class="stat-value">
                              {detectionResult.top_class || "N/A"}
                            </p>
                            <p class="stat-label">Predicted Class</p>
                          </div>
                        </div>
                        <div class="result-stat">
                          <span class="stat-icon">📈</span>
                          <div class="stat-info">
                            <p class="stat-value">
                              {detectionResult.top_confidence
                                ? (
                                    detectionResult.top_confidence * 100
                                  ).toFixed(1)
                                : "0"}%
                            </p>
                            <p class="stat-label">Confidence</p>
                          </div>
                        </div>
                        <div class="result-stat">
                          <span class="stat-icon">⚡</span>
                          <div class="stat-info">
                            <p class="stat-value">
                              {Math.round(
                                detectionResult.inference_time_ms * 10,
                              ) / 10}ms
                            </p>
                            <p class="stat-label">Inference Time</p>
                          </div>
                        </div>
                      </div>

                      {#if detectionResult.top_classes && detectionResult.probabilities}
                        <div class="classification-results">
                          <h4>
                            Top {detectionResult.top_classes.length} Predictions:
                          </h4>
                          <div class="class-probabilities">
                            {#each detectionResult.top_classes as className, idx}
                              <div class="probability-bar">
                                <div class="probability-label">
                                  <span class="class-name">{className}</span>
                                  <span class="probability-value">
                                    {(
                                      detectionResult.probabilities[idx] * 100
                                    ).toFixed(2)}%
                                  </span>
                                </div>
                                <div class="probability-track">
                                  <div
                                    class="probability-fill"
                                    style="width: {detectionResult
                                      .probabilities[idx] *
                                      100}%; background: {idx === 0
                                      ? '#10B981'
                                      : idx === 1
                                        ? '#3B82F6'
                                        : '#6B7280'}"
                                  ></div>
                                </div>
                              </div>
                            {/each}
                          </div>
                        </div>
                      {/if}
                    {:else}
                      <!-- Detection/Segmentation Results -->
                      <div class="results-stats">
                        <div class="result-stat">
                          <span class="stat-icon">🎯</span>
                          <div class="stat-info">
                            <p class="stat-value">
                              {detectionResult.task_type === "segment"
                                ? detectionResult.masks?.length ||
                                  detectionResult.boxes?.length ||
                                  0
                                : detectionResult.boxes?.length || 0}
                            </p>
                            <p class="stat-label">
                              {detectionResult.task_type === "segment"
                                ? "Instances Segmented"
                                : "Objects Detected"}
                            </p>
                          </div>
                        </div>
                        <div class="result-stat">
                          <span class="stat-icon">⚡</span>
                          <div class="stat-info">
                            <p class="stat-value">
                              {Math.round(
                                detectionResult.inference_time_ms * 10,
                              ) / 10}ms
                            </p>
                            <p class="stat-label">Inference Time</p>
                          </div>
                        </div>
                      </div>
                      {#if detectionResult.boxes && detectionResult.boxes.length > 0}
                        <div class="detected-classes-card">
                          <h4>Detected Classes:</h4>
                          <div class="class-tags">
                            {#each [...new Set(detectionResult.class_names || [])].map( (className) => {
                                // Find the highest confidence for this class
                                const maxConfidence = Math.max(...(detectionResult.class_names || []).map( (name, idx) => (name === className ? (detectionResult.scores || [])[idx] : 0), ));
                                return { name: className, confidence: maxConfidence };
                              }, ) as classInfo}
                              <span class="class-tag">
                                {classInfo.name} ({(
                                  classInfo.confidence * 100
                                ).toFixed(0)}%)
                              </span>
                            {/each}
                          </div>
                        </div>
                      {/if}
                    {/if}
                  </div>
                {/if}
              </div>

              <!-- Canvas / PromptEditor -->
              <div class="preview-canvas">
                {#if !previewImageUrl}
                  <div class="canvas-placeholder">
                    <p>Upload an image to test the model</p>
                  </div>
                {:else if selectedModel?.base_type === "sam3" && showPromptEditor && !detectionResult}
                  <!-- SAM3 Prompt Editor (before detection) -->
                  <PromptEditor
                    imageUrl={previewImageUrl}
                    prompts={sam3Prompts}
                    on:promptsChange={(e) => (sam3Prompts = e.detail)}
                  />
                {:else if showMaskOverlay}
                  <!-- Show mask overlay for segmentation results -->
                  <MaskOverlay
                    imageUrl={previewImageUrl}
                    polygons={(detectionResult.masks || []).map(
                      (m) => m.polygon,
                    )}
                    classes={(detectionResult.masks || []).map(
                      (m) => m.class_id,
                    )}
                    classNames={(detectionResult.masks || []).map(
                      (m) => m.class_name,
                    )}
                    scores={(detectionResult.masks || []).map((m) => m.score)}
                    imageWidth={detectionResult.masks?.[0]?.width || 0}
                    imageHeight={detectionResult.masks?.[0]?.height || 0}
                  />
                {:else}
                  <!-- Show regular canvas for detection or YOLO segmentation -->
                  <canvas bind:this={canvasElement}></canvas>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {:else if activeTab === "models"}
        <!-- Models Management Tab -->
        <div class="models-section">
          <div class="models-header">
            <div>
              <h2>Model Management</h2>
              <p class="section-subtitle">Manage all models in this project</p>
            </div>
            <div class="models-controls">
              <div class="view-toggle">
                <button
                  class="view-btn"
                  class:active={modelsViewMode === "table"}
                  on:click={() => (modelsViewMode = "table")}
                  title="Table View"
                >
                  📋
                </button>
                <button
                  class="view-btn"
                  class:active={modelsViewMode === "cards"}
                  on:click={() => (modelsViewMode = "cards")}
                  title="Cards View"
                >
                  📇
                </button>
              </div>
            </div>
          </div>

          {#if availableModels.length === 0}
            <div class="empty-state-card">
              <div class="empty-icon">🤖</div>
              <h3>No Models Yet</h3>
              <p>
                {#if project.is_system}
                  Upload a model to get started
                {:else}
                  Train or upload a model to get started
                {/if}
              </p>
            </div>
          {:else if modelsViewMode === "table"}
            <!-- Table View -->
            <div class="models-table-wrapper">
              <table class="models-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Base Type</th>
                    <th>Inference Type</th>
                    <th>Task Type</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Metrics</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each availableModels as model}
                    <tr class="model-row">
                      <td>#{model.id}</td>
                      <td>
                        <div class="model-name-cell">
                          <strong>{model.name}</strong>
                        </div>
                      </td>
                      <td>
                        <span class="badge badge-info">{model.base_type}</span>
                      </td>
                      <td>
                        <span class="badge badge-secondary"
                          >{model.inference_type || "yolo"}</span
                        >
                      </td>
                      <td>
                        <span
                          class="task-type-badge task-type-{model.task_type}"
                        >
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
                      </td>
                      <td>
                        <span class="badge badge-source">
                          {getModelSourceBadge(model)}
                        </span>
                      </td>
                      <td>
                        <span
                          class="status-badge"
                          class:status-ready={model.status === "ready"}
                          class:status-validating={model.status ===
                            "validating"}
                          class:status-failed={model.status === "failed"}
                        >
                          {model.status}
                        </span>
                      </td>
                      <td>
                        {#if model.metrics_json}
                          <div class="metrics-cell">
                            {#if model.task_type === "classify"}
                              <span class="metric-mini">
                                Top-1: {formatPercentage(
                                  model.metrics_json["top1_accuracy"] ||
                                    model.metrics_json["metrics/accuracy_top1"],
                                )}
                              </span>
                              <span class="metric-mini">
                                Top-5: {formatPercentage(
                                  model.metrics_json["top5_accuracy"] ||
                                    model.metrics_json["metrics/accuracy_top5"],
                                )}
                              </span>
                            {:else}
                              <span class="metric-mini">
                                mAP: {formatPercentage(
                                  model.metrics_json["metrics/mAP50-95(B)"] ||
                                    model.metrics_json["mAP50-95"],
                                )}
                              </span>
                              <span class="metric-mini">
                                P: {formatPercentage(
                                  model.metrics_json["metrics/precision(B)"] ||
                                    model.metrics_json["precision"],
                                )}
                              </span>
                            {/if}
                          </div>
                        {:else}
                          <span class="text-muted">N/A</span>
                        {/if}
                      </td>
                      <td>
                        <span class="date-text">
                          {formatDate(model.created_at)}
                        </span>
                      </td>
                      <td>
                        <div class="action-buttons">
                          <button
                            class="btn-icon"
                            on:click={() => openEditModal(model)}
                            title="Rename Model"
                          >
                            ✏️
                          </button>
                          {#if model.status === "ready" && !project.is_system}
                            <button
                              class="btn-icon"
                              on:click={() => handleValidateModel(model)}
                              title="Validate Model"
                            >
                              ✅
                            </button>
                          {/if}
                          {#if project.is_system}
                            <button
                              class="btn-icon btn-icon-danger"
                              on:click={() => handleDeleteModel(model)}
                              title="Delete Model"
                            >
                              🗑️
                            </button>
                          {/if}
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <!-- Cards View -->
            <div class="models-grid">
              {#each availableModels as model}
                <div class="model-card">
                  <div class="model-card-header">
                    <div>
                      <h3>{model.name}</h3>
                      <span class="model-id">ID: #{model.id}</span>
                    </div>
                    <span
                      class="status-badge"
                      class:status-ready={model.status === "ready"}
                      class:status-validating={model.status === "validating"}
                      class:status-failed={model.status === "failed"}
                    >
                      {model.status}
                    </span>
                  </div>

                  <div class="model-card-body">
                    <div class="model-info-row">
                      <span class="info-label">Base Type:</span>
                      <span class="badge badge-info">{model.base_type}</span>
                    </div>
                    <div class="model-info-row">
                      <span class="info-label">Inference Type:</span>
                      <span class="badge badge-secondary"
                        >{model.inference_type || "yolo"}</span
                      >
                    </div>
                    <div class="model-info-row">
                      <span class="info-label">Task Type:</span>
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
                    <div class="model-info-row">
                      <span class="info-label">Source:</span>
                      <span class="badge badge-source">
                        {getModelSourceBadge(model)}
                      </span>
                    </div>
                    <div class="model-info-row">
                      <span class="info-label">Created:</span>
                      <span>{formatDate(model.created_at)}</span>
                    </div>

                    {#if model.metrics_json}
                      <div class="model-metrics">
                        <h4>Metrics</h4>
                        {#if model.task_type === "classify"}
                          <div class="metrics-grid-mini">
                            <div class="metric-item-mini">
                              <span class="metric-label">Top-1 Accuracy</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["top1_accuracy"] ||
                                    model.metrics_json["metrics/accuracy_top1"],
                                )}
                              </span>
                            </div>
                            <div class="metric-item-mini">
                              <span class="metric-label">Top-5 Accuracy</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["top5_accuracy"] ||
                                    model.metrics_json["metrics/accuracy_top5"],
                                )}
                              </span>
                            </div>
                          </div>
                        {:else}
                          <div class="metrics-grid-mini">
                            <div class="metric-item-mini">
                              <span class="metric-label">mAP50-95</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["metrics/mAP50-95(B)"] ||
                                    model.metrics_json["mAP50-95"],
                                )}
                              </span>
                            </div>
                            <div class="metric-item-mini">
                              <span class="metric-label">Precision</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["metrics/precision(B)"] ||
                                    model.metrics_json["precision"],
                                )}
                              </span>
                            </div>
                            <div class="metric-item-mini">
                              <span class="metric-label">Recall</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["metrics/recall(B)"] ||
                                    model.metrics_json["recall"],
                                )}
                              </span>
                            </div>
                            <div class="metric-item-mini">
                              <span class="metric-label">mAP50</span>
                              <span class="metric-value">
                                {formatPercentage(
                                  model.metrics_json["metrics/mAP50(B)"] ||
                                    model.metrics_json["mAP50"],
                                )}
                              </span>
                            </div>
                          </div>
                        {/if}
                      </div>
                    {:else}
                      <div class="no-metrics">
                        <p>No metrics available</p>
                      </div>
                    {/if}

                    {#if model.validation_error}
                      <div class="validation-error">
                        <strong>⚠️ Validation Error:</strong>
                        <p>{model.validation_error}</p>
                      </div>
                    {/if}
                  </div>

                  <div class="model-card-footer">
                    <button
                      class="btn btn-secondary btn-sm"
                      on:click={() => openEditModal(model)}
                    >
                      ✏️ Rename
                    </button>
                    {#if model.status === "ready" && !project.is_system}
                      <button
                        class="btn btn-primary btn-sm"
                        on:click={() => handleValidateModel(model)}
                      >
                        ✅ Validate
                      </button>
                    {/if}
                    {#if project.is_system}
                      <button
                        class="btn btn-danger btn-sm"
                        on:click={() => handleDeleteModel(model)}
                      >
                        🗑️ Delete
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {:else if activeTab === "team"}
        <!-- Team Management Tab -->
        <div class="team-container">
          <div class="team-header">
            <div>
              <h2>Project Team</h2>
              <p class="team-subtitle">
                Manage operators assigned to this project
              </p>
            </div>
            {#if isDataManager}
              <button class="btn btn-primary" on:click={openAddMemberModal}>
                <span>👤 Add Member</span>
              </button>
            {/if}
          </div>

          {#if loadingTeam}
            <LoadingSpinner />
          {:else if teamMembers.length === 0}
            <div class="empty-state-card">
              <div class="empty-icon">👥</div>
              <h3>No Team Members</h3>
              <p>
                Add operators to give them access to detection features for this
                project
              </p>
              {#if isDataManager}
                <button class="btn-primary" on:click={openAddMemberModal}>
                  Add First Member
                </button>
              {/if}
            </div>
          {:else}
            <div class="team-table-container">
              <table class="team-table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Added</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each teamMembers as member}
                    <tr>
                      <td>
                        <div class="member-name">
                          <span class="member-icon">👤</span>
                          {member.email.split("@")[0]}
                        </div>
                      </td>
                      <td>{member.email}</td>
                      <td>
                        <span class="role-badge role-operator">
                          🎯 {member.role.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span class="date-text"
                          >{formatDateTime(member.added_at)}</span
                        >
                      </td>
                      <td>
                        {#if isDataManager}
                          <button
                            class="btn btn-danger btn-sm"
                            on:click={() =>
                              handleRemoveMember(member.user_id, member.email)}
                          >
                            Remove
                          </button>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      {:else if activeTab === "sessionForm"}
        <!-- Session Form Configuration -->
        <div class="session-form-container">
          <div class="session-form-header">
            <div>
              <h2>Session Form Configuration</h2>
              <p class="section-subtitle">
                Define custom form fields that will appear when creating new
                detection sessions
              </p>
            </div>
            <div class="session-form-actions">
              <button
                class="btn btn-secondary"
                on:click={() => openFieldModal()}
                disabled={loadingFormConfig}
              >
                <span>➕ Add Field</span>
              </button>
              <button
                class="btn btn-primary"
                on:click={saveSessionForm}
                disabled={savingFormConfig || formFields.length === 0}
              >
                {savingFormConfig ? "Saving..." : "💾 Save Configuration"}
              </button>
              {#if formFields.length > 0}
                <button class="btn btn-danger" on:click={clearSessionForm}>
                  🗑️ Clear All
                </button>
              {/if}
            </div>
          </div>

          {#if loadingFormConfig}
            <LoadingSpinner />
          {:else if formFields.length === 0}
            <div class="empty-state-card">
              <div class="empty-icon">📝</div>
              <h3>No Form Fields Configured</h3>
              <p>
                Add custom form fields to collect additional information when
                creating detection sessions
              </p>
              <button class="btn btn-primary" on:click={() => openFieldModal()}>
                Add First Field
              </button>
            </div>
          {:else}
            <div class="fields-table-container">
              <table class="fields-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Field Name</th>
                    <th>Label</th>
                    <th>Type</th>
                    <th>Required</th>
                    <th>Options</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each formFields as field, index}
                    <tr>
                      <td>
                        <div class="order-controls">
                          <button
                            class="btn-icon-mini"
                            on:click={() => moveFieldUp(index)}
                            disabled={index === 0}
                            title="Move Up"
                          >
                            ▲
                          </button>
                          <span>{index + 1}</span>
                          <button
                            class="btn-icon-mini"
                            on:click={() => moveFieldDown(index)}
                            disabled={index === formFields.length - 1}
                            title="Move Down"
                          >
                            ▼
                          </button>
                        </div>
                      </td>
                      <td><code>{field.field_name}</code></td>
                      <td>{field.label}</td>
                      <td>
                        <span class="badge badge-info">{field.field_type}</span>
                      </td>
                      <td>
                        {#if field.required}
                          <span class="badge badge-danger">Required</span>
                        {:else}
                          <span class="badge badge-secondary">Optional</span>
                        {/if}
                      </td>
                      <td>
                        {#if field.field_type === "select" && field.options}
                          <span class="text-sm"
                            >{field.options.length} options</span
                          >
                        {:else}
                          <span class="text-muted text-sm">—</span>
                        {/if}
                      </td>
                      <td>
                        <div class="action-buttons">
                          <button
                            class="btn-icon"
                            on:click={() => openFieldModal(index)}
                            title="Edit"
                          >
                            ✏️
                          </button>
                          <button
                            class="btn-icon btn-icon-danger"
                            on:click={() => deleteField(index)}
                            title="Delete"
                          >
                            🗑️
                          </button>
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <div class="info-message">
              <strong>ℹ️ Note:</strong> These fields will appear in the session creation
              modal. Save the configuration to make it available.
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- Add Team Member Modal -->
{#if showAddMemberModal}
  <div
    class="modal-overlay"
    on:click={() => (showAddMemberModal = false)}
    role="button"
    tabindex="0"
  >
    <div class="modal-content modal-small" on:click|stopPropagation>
      <div class="modal-header">
        <h3>Add Team Member</h3>
        <button
          class="modal-close"
          on:click={() => (showAddMemberModal = false)}>✕</button
        >
      </div>
      <div class="modal-body">
        {#if availableOperators.length === 0}
          <p class="info-message">
            No available operators. All operators are already assigned to this
            project.
          </p>
        {:else}
          <form on:submit|preventDefault={handleAddMember}>
            <div class="form-group">
              <label for="operator-select">Select Operator</label>
              <select
                id="operator-select"
                bind:value={selectedOperatorId}
                required
              >
                {#each availableOperators as operator}
                  <option value={operator.id}>
                    {operator.username || operator.email} ({operator.email})
                  </option>
                {/each}
              </select>
              <small>Only operators can be added to project teams</small>
            </div>
            <div class="modal-actions">
              <button
                type="button"
                class="btn btn-secondary"
                on:click={() => (showAddMemberModal = false)}
              >
                Cancel
              </button>
              <button type="submit" class="btn btn-primary">
                Add Member
              </button>
            </div>
          </form>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Edit Model Modal -->
{#if showEditModal}
  <div
    class="modal-overlay"
    on:click={closeEditModal}
    role="button"
    tabindex="0"
  >
    <div class="modal-content modal-small" on:click|stopPropagation>
      <div class="modal-header">
        <h3>Edit Model</h3>
        <button class="modal-close" on:click={closeEditModal}>✕</button>
      </div>
      <div class="modal-body">
        <form on:submit|preventDefault={handleUpdateModel}>
          <div class="form-group">
            <label for="edit-model-name">Model Name</label>
            <input
              id="edit-model-name"
              type="text"
              bind:value={editForm.name}
              placeholder="Enter model name"
              required
            />
          </div>

          {#if project?.is_system}
            <div class="form-group">
              <label for="edit-model-file">Reupload Model File (Optional)</label
              >
              <input
                id="edit-model-file"
                type="file"
                accept=".pt,.pth"
                on:change={(e) => {
                  const files = e.target.files;
                  if (files && files.length > 0) {
                    editForm.file = files[0];
                  }
                }}
              />
              <small
                >Select a new .pt or .pth file to replace the existing model.
                Leave empty to only rename.</small
              >
            </div>
          {/if}

          <div class="modal-actions">
            <button
              type="button"
              class="btn btn-secondary"
              on:click={closeEditModal}
            >
              Cancel
            </button>
            <button type="submit" class="btn btn-primary">
              Update Model
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<!-- Image Zoom Modal -->
{#if zoomedImage}
  <div
    class="modal-overlay"
    on:click={closeImageZoom}
    role="button"
    tabindex="0"
    on:keydown={(e) => e.key === "Escape" && closeImageZoom()}
  >
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h3>{zoomedImageLabel}</h3>
        <button class="modal-close" on:click={closeImageZoom}>✕</button>
      </div>
      <div class="modal-body">
        <img src={zoomedImage} alt={zoomedImageLabel} class="zoomed-image" />
      </div>
    </div>
  </div>
{/if}

<!-- Model Upload Modal -->
{#if showUploadModal}
  <div
    class="modal-overlay"
    on:click={closeUploadModal}
    role="button"
    tabindex="0"
  >
    <div class="modal-content modal-medium" on:click|stopPropagation>
      <div class="modal-header">
        <h3>Upload Model</h3>
        <button class="modal-close" on:click={closeUploadModal}>✕</button>
      </div>
      <div class="modal-body">
        <form on:submit|preventDefault={handleModelUpload}>
          <div class="form-group">
            <label for="model-name">Model Name</label>
            <input
              type="text"
              id="model-name"
              bind:value={uploadForm.name}
              placeholder="e.g., PPE Detector v1"
              required
            />
          </div>

          <div class="form-group">
            <label for="task-type">Task Type</label>
            <select id="task-type" bind:value={uploadForm.taskType} required>
              <option value="detect">🎯 Detection</option>
              <option value="classify">📊 Classification</option>
              <option value="segment">✂️ Segmentation</option>
              <option value="segment_anything">🎭 SegmentAnything (SAM3)</option
              >
            </select>
            <small>Select the task type this model is trained for</small>
          </div>

          <div class="form-group">
            <label for="base-model">Base Model (Optional)</label>
            {#if loadingBaseModels}
              <div class="loading-text">Loading existing models...</div>
            {:else if baseModelTypes.length === 0}
              <div class="info-text">
                No existing models in this project. The model name will be used
                as base type.
              </div>
            {:else}
              <select id="base-model" bind:value={uploadForm.baseModelId}>
                <option value={null}>-- Use model name as base type --</option>
                {#each baseModelTypes as type}
                  <option value={type.value}
                    >{type.label} ({type.baseType})</option
                  >
                {/each}
              </select>
              <small
                >Select an existing model to use its base type, or leave
                unselected to use the model name</small
              >
            {/if}
          </div>

          <div class="form-group">
            <label for="model-file">
              Model File {uploadForm.taskType === "segment_anything"
                ? "(.pt/.safetensors)"
                : "(.pt)"}
            </label>
            <input
              type="file"
              id="model-file"
              accept={uploadForm.taskType === "segment_anything"
                ? ".pt,.safetensors"
                : ".pt"}
              on:change={(e) => {
                const file = e.target?.files?.[0];
                if (file) uploadForm.file = file;
              }}
              required
            />
            <small>
              Maximum file size: {uploadForm.taskType === "segment_anything"
                ? "3GB"
                : "100MB"}
            </small>
          </div>

          {#if uploadForm.taskType === "segment_anything"}
            <div class="form-group">
              <label for="bpe-file">
                BPE Vocabulary File (.txt.gz) <span
                  style="color: var(--color-error);">*</span
                >
              </label>
              <input
                type="file"
                id="bpe-file"
                accept=".txt.gz,.gz"
                on:change={(e) => {
                  const file = e.target?.files?.[0];
                  if (file) uploadForm.bpeFile = file;
                }}
                required
              />
              <small
                >Required for SAM3 models (e.g., bpe_simple_vocab_16e6.txt.gz)</small
              >
            </div>
          {/if}

          <div class="modal-actions">
            <button
              type="button"
              class="btn btn-secondary"
              on:click={closeUploadModal}
              disabled={uploadingModel}
            >
              Cancel
            </button>
            <button
              type="submit"
              class="btn btn-primary"
              disabled={uploadingModel}
            >
              {#if uploadingModel}
                Uploading...
              {:else}
                Upload Model
              {/if}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Confirmation Modal -->
<ConfirmDeleteModal
  show={showDeleteModal}
  projectName={project?.name || ""}
  modelsCount={deleteConfirmation?.models_count || 0}
  jobsCount={deleteConfirmation?.jobs_count || 0}
  onCancel={cancelDelete}
  onConfirm={confirmDelete}
/>

<style>
  /* Base Styles */
  .page {
    padding: var(--spacing-lg);
    width: 100%;
    max-width: 100%;
    margin: 0;
    box-sizing: border-box;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-lg);
    padding-bottom: var(--spacing-md);
    border-bottom: 2px solid var(--color-border);
  }

  .header-actions {
    display: flex;
    gap: var(--spacing-sm);
    align-items: center;
  }

  .subtitle {
    color: var(--color-text-secondary);
    font-size: 0.95rem;
    margin-top: var(--spacing-xs);
  }

  .status {
    font-weight: 600;
    text-transform: capitalize;
  }

  /* Enhanced Tabs */
  .tabs {
    display: flex;
    gap: var(--spacing-sm);
    border-bottom: 3px solid var(--color-border);
    margin-bottom: var(--spacing-lg);
    background: var(--color-bg-secondary);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    padding: var(--spacing-xs);
    border-radius: var(--border-radius-md) var(--border-radius-md) 0 0;
    border: 2px solid var(--color-border);
    border-bottom: 3px solid var(--color-border);
  }

  .tab {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm) var(--spacing-lg);
    background: transparent;
    border: 2px solid transparent;
    color: var(--color-text);
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    border-radius: var(--border-radius-sm);
    transition: all 200ms ease;
  }

  .tab-icon {
    font-size: 1.2rem;
  }

  .tab:hover {
    background: var(--color-bg-primary);
    color: var(--color-accent);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .tab.active {
    background: var(--color-bg-primary);
    color: var(--color-accent);
    font-weight: 700;
    border: 2px solid var(--color-accent);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .tab-content {
    min-height: 500px;
  }

  /* Overview Dashboard Styles */
  .overview-section {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: var(--spacing-md);
  }

  .stat-card {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    color: white;
    position: relative;
    overflow: hidden;
    transition: transform 200ms ease;
    border: 3px solid rgba(255, 255, 255, 0.3);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
  }

  .gradient-blue {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  }

  .gradient-green {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  }

  .gradient-purple {
    background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
  }

  .gradient-orange {
    background: linear-gradient(135deg, #f59e0b 0%, #e1604c 100%);
  }

  .stat-icon {
    font-size: 3rem;
    opacity: 0.9;
  }

  .stat-content {
    flex: 1;
  }

  .stat-label {
    font-size: 0.85rem;
    opacity: 0.95;
    margin-bottom: var(--spacing-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .stat-value {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: var(--spacing-xs);
  }

  .stat-detail {
    font-size: 0.9rem;
    opacity: 0.9;
  }

  /* Timeline Styles */
  .history-section {
    background: var(--color-bg-secondary);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .history-section h2 {
    margin-bottom: var(--spacing-lg);
    font-size: 1.5rem;
  }

  .timeline {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    position: relative;
  }

  .timeline-item {
    display: flex;
    gap: var(--spacing-md);
    position: relative;
    padding: var(--spacing-md);
    border-radius: var(--border-radius-sm);
    transition: all 200ms ease;
    border: 2px solid transparent;
    background: var(--color-bg-secondary);
  }

  .timeline-item:hover {
    background: white;
    border-color: var(--color-accent);
    transform: translateX(4px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .timeline-item.selected {
    background: var(--color-bg-primary);
    border: 2px solid var(--color-accent);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.3);
  }

  .timeline-marker {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: white;
    font-weight: bold;
    font-size: 1.2rem;
  }

  .timeline-content {
    flex: 1;
    cursor: pointer;
  }

  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xs);
  }

  .timeline-title {
    font-weight: 600;
    font-size: 1.05rem;
  }

  .timeline-date {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .timeline-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .timeline-metrics {
    display: flex;
    gap: var(--spacing-sm);
    flex-wrap: wrap;
  }

  .metric-badge {
    padding: 4px 12px;
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
    font-weight: 500;
  }

  .timeline-progress {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .mini-progress-bar {
    height: 8px;
    background: var(--color-border);
    border-radius: 4px;
    overflow: hidden;
  }

  .mini-progress-fill {
    height: 100%;
    background: #3b82f6;
    transition: width 300ms ease;
  }

  .progress-text {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  /* Dataset Card */
  .dataset-card {
    background: var(--color-bg-secondary);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .dataset-header {
    margin-bottom: var(--spacing-md);
  }

  .dataset-header h2 {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    font-size: 1.3rem;
  }

  .dataset-icon {
    font-size: 1.5rem;
  }

  .dataset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-md);
  }

  .dataset-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-sm);
    border: 2px solid var(--color-border);
  }

  .dataset-label {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .dataset-value {
    font-size: 1.1rem;
    font-weight: 600;
  }

  /* Empty State Cards */
  .empty-state-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xl) var(--spacing-lg);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-md);
    border: 2px dashed var(--color-border);
    text-align: center;
    min-height: 300px;
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-md);
    opacity: 0.7;
  }

  .empty-state-card h3 {
    font-size: 1.5rem;
    margin-bottom: var(--spacing-sm);
  }

  .empty-state-card p {
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-lg);
  }

  /* Enhanced Training Layout */
  .train-layout {
    display: grid;
    grid-template-columns: 400px 1fr;
    gap: var(--spacing-lg);
  }

  .jobs-list {
    background: white;
    padding: var(--spacing-md);
    border-radius: var(--border-radius-md);
    height: fit-content;
    max-height: 800px;
    overflow-y: auto;
    border: 4px solid #1d2f43;
    box-shadow: 0 4px 16px rgba(29, 47, 67, 0.15);
  }

  .jobs-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-md);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-border);
  }

  .jobs-header h2 {
    font-size: 1.2rem;
  }

  .jobs-count {
    background: var(--color-accent);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .empty-state-small {
    text-align: center;
    padding: var(--spacing-lg);
    color: var(--color-text-secondary);
  }

  .empty-state-small .empty-icon {
    font-size: 2.5rem;
    margin-bottom: var(--spacing-sm);
  }

  .jobs {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .job-card-enhanced {
    width: 100%;
    padding: var(--spacing-md);
    background: var(--color-bg-secondary);
    border: 2px solid var(--color-border);
    border-left: 5px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    text-align: left;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .job-card-enhanced:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    background: var(color-bg-primary);
    border-right-width: 3px;
  }

  .job-card-enhanced.selected {
    background: var(--color-bg-primary);
    border: 3px solid var(--color-accent);
    border-left-width: 5px;
    box-shadow: 0 4px 16px rgba(225, 96, 76, 0.3);
  }

  .job-header-enhanced {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-sm);
  }

  .job-icon {
    font-size: 1.2rem;
  }

  .job-id {
    font-weight: 600;
    flex: 1;
  }

  .job-status-pill {
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    color: white;
    font-weight: 600;
  }

  .job-details-enhanced {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .running-indicator {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .progress-circle-small {
    width: 50px;
    height: 50px;
    flex-shrink: 0;
  }

  .circular-chart {
    display: block;
    margin: 0 auto;
    max-width: 100%;
    max-height: 100%;
  }

  .circle-bg {
    fill: none;
    stroke: #e6e6e6;
    stroke-width: 2.8;
  }

  .circle {
    fill: none;
    stroke: #3b82f6;
    stroke-width: 2.8;
    stroke-linecap: round;
    animation: progress 1s ease-out forwards;
  }

  @keyframes progress {
    0% {
      stroke-dasharray: 0 100;
    }
  }

  .percentage {
    fill: var(--color-text);
    font-family: Montserrat, sans-serif;
    font-size: 0.5em;
    font-weight: bold;
    text-anchor: middle;
  }

  .progress-info {
    flex: 1;
  }

  .progress-main {
    font-weight: 600;
    margin-bottom: 2px;
  }

  .progress-sub {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .completed-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .metric-primary {
    font-weight: 600;
    font-size: 0.95rem;
  }

  .metric-secondary {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .error-text-small {
    font-size: 0.85rem;
    color: #ef4444;
  }

  .status-text-small {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .date-small {
    font-size: 0.8rem;
    color: var(--color-text-secondary);
    margin-top: 4px;
  }

  .metrics-header-enhanced {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-md);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-md);
  }

  .metrics-header-enhanced h2 {
    font-size: 1.5rem;
    margin-bottom: var(--spacing-xs);
  }

  .job-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    color: white;
  }

  /* Hero Metric */
  .hero-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    color: white;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    position: relative;
    overflow: hidden;
    border: 3px solid rgba(255, 255, 255, 0.3);
  }

  .hero-content {
    flex: 1;
  }

  .hero-label {
    font-size: 0.85rem;
    opacity: 0.9;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--spacing-xs);
  }

  .hero-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: var(--spacing-sm);
    opacity: 0.95;
  }

  .hero-value {
    font-size: 3.5rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: var(--spacing-xs);
  }

  .hero-subtitle {
    font-size: 0.9rem;
    opacity: 0.9;
  }

  .hero-icon {
    font-size: 6rem;
    opacity: 0.2;
  }

  /* Modern Metric Cards */
  .metrics-grid-enhanced {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-md);
  }

  .metric-card-modern {
    display: flex;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-lg);
    background: var(--color-bg-card);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    transition: all 200ms ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .metric-card-modern:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
    border-color: var(--color-accent);
  }

  .metric-icon {
    width: 50px;
    height: 50px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    flex-shrink: 0;
  }

  .metric-content {
    flex: 1;
  }

  .metric-title {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--spacing-xs);
  }

  .metric-value-modern {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: var(--spacing-xs);
  }

  .metric-subtitle {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  /* Loss Section with Bars */
  .loss-section-enhanced {
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-md);
    border: 2px solid var(--color-border);
  }

  .loss-section-enhanced h3 {
    margin-bottom: var(--spacing-md);
    font-size: 1.2rem;
  }

  .loss-bars {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .loss-bar-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .loss-bar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .loss-bar-label {
    font-weight: 600;
    font-size: 0.95rem;
  }

  .loss-bar-value {
    font-family: monospace;
    font-size: 0.9rem;
    color: var(--color-text-secondary);
  }

  .loss-bar-bg {
    height: 12px;
    background: var(--color-bg-primary);
    border-radius: 6px;
    overflow: hidden;
  }

  .loss-bar-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 300ms ease;
  }

  /* Artifacts Section */
  .artifacts-section-enhanced {
    padding: var(--spacing-lg);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-md);
    border: 2px solid var(--color-border);
  }

  .artifacts-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-md);
  }

  .artifacts-header h3 {
    font-size: 1.2rem;
  }

  .btn-text {
    background: none;
    border: none;
    color: var(--color-accent);
    font-weight: 600;
    cursor: pointer;
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--border-radius-sm);
    transition: all 200ms ease;
  }

  .btn-text:hover {
    background: rgba(225, 96, 76, 0.1);
  }

  .artifacts-grid-enhanced {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--spacing-md);
  }

  .artifact-card {
    background: white;
    border-radius: var(--border-radius-md);
    overflow: hidden;
    border: 3px solid var(--color-border);
    transition: all 200ms ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .artifact-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
    border-color: var(--color-accent);
  }

  .artifact-title {
    padding: var(--spacing-sm) var(--spacing-md);
    font-weight: 600;
    font-size: 0.9rem;
    background: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
  }

  .artifact-image-wrapper {
    padding: var(--spacing-sm);
    background: white;
  }

  .artifact-image {
    width: 100%;
    height: auto;
    display: block;
    border-radius: var(--border-radius-sm);
  }

  .artifact-image-wrapper {
    padding: var(--spacing-sm);
    background: white;
    position: relative;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .artifact-image-wrapper:hover {
    transform: scale(1.02);
  }

  .artifact-image-wrapper:hover .zoom-hint {
    opacity: 1;
  }

  .zoom-hint {
    position: absolute;
    bottom: var(--spacing-md);
    right: var(--spacing-md);
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 6px 12px;
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
    opacity: 0;
    transition: opacity 200ms ease;
    pointer-events: none;
  }

  /* Modal Styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: var(--spacing-lg);
    animation: fadeIn 200ms ease;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal-content {
    background: white;
    border-radius: var(--border-radius-md);
    max-width: 90vw;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    animation: scaleIn 200ms ease;
  }

  @keyframes scaleIn {
    from {
      transform: scale(0.9);
      opacity: 0;
    }
    to {
      transform: scale(1);
      opacity: 1;
    }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-lg);
    border-bottom: 2px solid var(--color-border);
  }

  .modal-header h3 {
    font-size: 1.3rem;
    color: var(--color-text);
    margin: 0;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 2rem;
    color: var(--color-text-secondary);
    cursor: pointer;
    padding: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 200ms ease;
  }

  .modal-close:hover {
    background: var(--color-bg-secondary);
    color: var(--color-accent);
    transform: rotate(90deg);
  }

  .modal-body {
    padding: var(--spacing-lg);
    overflow: auto;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .zoomed-image {
    max-width: 100%;
    max-height: calc(90vh - 120px);
    height: auto;
    border-radius: var(--border-radius-sm);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  /* Enhanced Configuration Section */
  .config-section-enhanced {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
  }

  .config-header {
    padding: var(--spacing-md);
    background: var(--color-bg-primary);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .config-header h2 {
    font-size: 1.5rem;
    margin-bottom: var(--spacing-xs);
  }

  .config-subtitle {
    color: var(--color-text-secondary);
    font-size: 0.95rem;
  }

  .config-grid-enhanced {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: var(--spacing-md);
  }

  .config-card {
    background: var(--color-bg-secondary);
    border: 3px solid var(--color-border);
    border-radius: var(--border-radius-md);
    overflow: hidden;
    transition: all 200ms ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .config-card:hover {
    border-color: var(--color-accent);
    box-shadow: 0 6px 16px rgba(225, 96, 76, 0.2);
    transform: translateY(-2px);
  }

  .config-card-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    background: var(--color-bg-primary);
    border-bottom: 2px solid var(--color-border);
  }

  .config-icon {
    font-size: 1.5rem;
  }

  .config-card-header h3 {
    font-size: 1.1rem;
    flex: 1;
  }

  .config-items {
    padding: var(--spacing-md);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .config-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .config-row:last-child {
    border-bottom: none;
  }

  .config-key {
    font-size: 0.9rem;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .config-val {
    font-weight: 600;
    text-align: right;
  }

  .config-val.highlight {
    color: var(--color-accent);
    font-size: 1.1rem;
  }

  .status-badge-small {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    color: white;
    font-weight: 600;
  }

  /* Enhanced Preview Section */
  .preview-section-enhanced {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
  }

  .preview-header {
    padding: var(--spacing-md);
    background: var(--color-bg-primary);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .preview-header h2 {
    font-size: 1.5rem;
    margin-bottom: var(--spacing-xs);
  }

  .preview-subtitle {
    color: var(--color-text-secondary);
    font-size: 0.95rem;
  }

  .preview-layout-enhanced {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: var(--spacing-lg);
  }

  .preview-controls-enhanced {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .controls-card {
    background: var(--color-bg-secondary);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .controls-card h3 {
    font-size: 1.1rem;
    margin-bottom: var(--spacing-md);
  }

  /* Model Selector Styles */
  .model-selector-card {
    border-color: var(--color-accent);
    border-width: 2px;
  }

  .model-selector-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .model-select {
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    background: white;
    font-size: 1rem;
    font-weight: 500;
    color: var(--color-navy);
    cursor: pointer;
    transition: all 200ms ease;
  }

  .model-select:hover {
    border-color: var(--color-accent);
  }

  .model-select:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .model-count-badge {
    display: inline-flex;
    padding: 4px 12px;
    background: var(--color-bg-primary);
    border-radius: 12px;
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .model-info-display {
    margin-top: var(--spacing-md);
    padding: var(--spacing-md);
    background: var(--color-bg-primary);
    border-radius: var(--border-radius-sm);
    border-left: 3px solid var(--color-accent);
  }

  .model-info-display .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
  }

  .model-info-display .info-row:not(:last-child) {
    border-bottom: 1px solid var(--color-border);
  }

  .model-info-display .info-label {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .model-info-display .info-value {
    font-size: 0.9rem;
    color: var(--color-navy);
    font-weight: 600;
  }

  .model-info-display .status-ready {
    color: #10b981;
  }

  .model-info-display .metric-value {
    color: var(--color-accent);
  }

  .upload-area {
    position: relative;
  }

  .file-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    overflow: hidden;
  }

  .upload-label {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-lg);
    background: var(--color-bg-secondary);
    border: 3px dashed var(--color-border);
    border-radius: var(--border-radius-md);
    cursor: pointer;
    transition: all 200ms ease;
  }

  .upload-label:hover {
    border-color: var(--color-accent);
    border-width: 3px;
    border-style: dashed;
    background: rgba(225, 96, 76, 0.08);
    transform: scale(1.02);
  }

  .upload-icon {
    font-size: 2rem;
  }

  .slider-control {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .slider-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 0.95rem;
  }

  .slider-value {
    color: var(--color-accent);
    font-size: 1.1rem;
  }

  .slider {
    width: 100%;
    height: 8px;
    border-radius: 4px;
    background: var(--color-bg-primary);
    outline: none;
    -webkit-appearance: none;
    appearance: none;
  }

  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--color-accent);
    cursor: pointer;
    transition: all 200ms ease;
  }

  .slider::-webkit-slider-thumb:hover {
    transform: scale(1.2);
  }

  .slider::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--color-accent);
    cursor: pointer;
    border: none;
    transition: all 200ms ease;
  }

  .slider::-moz-range-thumb:hover {
    transform: scale(1.2);
  }

  .slider-markers {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .btn-detect {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    width: 100%;
    padding: var(--spacing-md) var(--spacing-lg);
    background: linear-gradient(135deg, var(--color-accent) 0%, #f97316 100%);
    color: white;
    border: none;
    border-radius: var(--border-radius-md);
    font-weight: 700;
    font-size: 1.05rem;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .btn-detect:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(225, 96, 76, 0.3);
  }

  .btn-detect:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .results-card {
    background: white;
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-accent);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.2);
  }

  .results-card h3 {
    font-size: 1.1rem;
    margin-bottom: var(--spacing-md);
  }

  .results-stats {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-md);
  }

  .result-stat {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm);
    background: var(--color-bg-primary);
    border-radius: var(--border-radius-sm);
  }

  .stat-icon {
    font-size: 2rem;
  }

  .stat-info {
    flex: 1;
  }

  .stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    line-height: 1;
    color: var(--color-accent);
    margin-bottom: 4px;
  }

  .stat-label {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .detected-classes-card {
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-border);
  }

  .detected-classes-card h4 {
    font-size: 0.95rem;
    margin-bottom: var(--spacing-sm);
    color: var(--color-text-secondary);
  }

  .class-tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .class-tag {
    padding: 6px 12px;
    background: var(--color-bg-primary);
    border: 1px solid var(--color-accent);
    color: var(--color-accent);
    border-radius: 16px;
    font-size: 0.85rem;
    font-weight: 600;
  }

  /* Classification Results */
  .classification-results {
    margin-top: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-border);
  }

  .classification-results h4 {
    font-size: 0.95rem;
    margin-bottom: var(--spacing-md);
    color: var(--color-text-secondary);
  }

  .class-probabilities {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .probability-bar {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .probability-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
  }

  .class-name {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .probability-value {
    font-weight: 700;
    color: var(--color-accent);
  }

  .probability-track {
    height: 12px;
    background: var(--color-bg-primary);
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--color-border);
  }

  .probability-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  /* Canvas Area */
  .preview-canvas {
    background: var(--color-bg-secondary);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 2px solid var(--color-border);
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 600px;
  }

  .preview-canvas canvas {
    max-width: 100%;
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .canvas-placeholder {
    text-align: center;
    color: var(--color-text-secondary);
  }

  /* Button Styles */
  .btn-primary {
    padding: var(--spacing-md) var(--spacing-xl);
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--border-radius-md);
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(225, 96, 76, 0.3);
  }

  .btn-secondary {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-bg-primary);
    color: var(--color-text);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-weight: 600;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .btn-secondary:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  /* Responsive Design */
  @media (max-width: 1200px) {
    .train-layout {
      grid-template-columns: 350px 1fr;
    }

    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 1024px) {
    .train-layout,
    .preview-layout-enhanced {
      grid-template-columns: 1fr;
    }

    .config-grid-enhanced {
      grid-template-columns: 1fr;
    }

    .stats-grid {
      grid-template-columns: 1fr;
    }

    .hero-value {
      font-size: 2.5rem;
    }
  }

  @media (max-width: 768px) {
    .page {
      padding: var(--spacing-md);
    }

    .tabs {
      flex-wrap: wrap;
    }

    .tab {
      flex: 1;
      min-width: 120px;
    }
  }

  /* Training Layout */
  .train-layout {
    display: grid;
    grid-template-columns: 350px 1fr;
    gap: var(--spacing-lg);
  }

  .jobs-list {
    background: var(--color-bg-secondary);
    padding: var(--spacing-md);
    border-radius: var(--border-radius-md);
    height: fit-content;
  }

  .jobs-list h2 {
    font-size: 1.2rem;
    margin-bottom: var(--spacing-md);
  }

  .jobs {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .metrics-detail {
    background: var(--color-bg-secondary);
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-md);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .progress-section,
  .error-section {
    background: white;
    padding: var(--spacing-lg);
    border-radius: var(--border-radius-sm);
    border: 3px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .progress-bar {
    width: 100%;
    height: 30px;
    background: var(--color-border);
    border-radius: var(--border-radius-sm);
    overflow: hidden;
    margin: var(--spacing-md) 0;
  }

  .progress-fill {
    height: 100%;
    background: var(--color-accent);
    transition: width var(--transition-base);
  }

  .preview-canvas canvas {
    max-width: 100%;
    border: 3px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .canvas-placeholder {
    color: var(--color-text-secondary);
    text-align: center;
  }

  /* Button Styles */
  .btn-secondary {
    padding: var(--spacing-sm) var(--spacing-lg);
    background: var(--color-bg-secondary);
    color: var(--color-accent);
    border: 3px solid var(--color-accent);
    border-radius: var(--border-radius-md);
    font-weight: 700;
    font-size: 1rem;
    cursor: pointer;
    transition: all 200ms ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .btn-secondary:hover {
    background: var(--color-accent);
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.4);
  }

  .btn-text {
    background: none;
    border: 2px solid var(--color-accent);
    color: var(--color-accent);
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--border-radius-sm);
    font-weight: 600;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .btn-text:hover {
    background: var(--color-accent);
    color: white;
  }

  .btn-back {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm) var(--spacing-lg);
    background: var(--color-bg-secondary);
    color: var(--color-text);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-md);
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: all 200ms ease;
  }

  .btn-back:hover {
    background: var(--color-bg-primary);
    border-color: var(--color-accent);
    color: var(--color-accent);
    transform: translateY(-2px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* Utility Classes */
  .hint {
    font-size: 0.9rem;
    margin-top: var(--spacing-xs);
  }

  .error-text {
    color: #ef4444;
  }

  .info-text {
    color: var(--color-text-secondary);
    font-style: italic;
  }

  /* Responsive Design */
  @media (max-width: 1400px) {
    .train-layout {
      grid-template-columns: 350px 1fr;
    }

    .preview-layout-enhanced {
      grid-template-columns: 350px 1fr;
    }
  }

  @media (max-width: 1200px) {
    .page {
      padding: var(--spacing-md);
    }

    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .train-layout {
      grid-template-columns: 320px 1fr;
    }

    .preview-layout-enhanced {
      grid-template-columns: 320px 1fr;
    }

    .config-grid-enhanced {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  /* System Project Styles */
  .title-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    flex-wrap: wrap;
  }

  .system-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
    color: #78350f;
    font-size: 0.75rem;
    font-weight: 700;
    border-radius: var(--border-radius-sm);
    border: 2px solid #f59e0b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
  }

  .info-card {
    padding: var(--spacing-lg);
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border: 2px solid #3b82f6;
    border-radius: var(--border-radius-md);
    color: #1e3a8a;
  }

  .info-card h3 {
    color: #1e40af;
    margin: 0 0 var(--spacing-sm) 0;
    font-size: 1.1rem;
  }

  .info-card p {
    margin: 0;
    font-size: 0.95rem;
    line-height: 1.6;
  }

  /* Modal Medium Size */
  .modal-medium {
    max-width: 600px;
  }

  .form-group {
    margin-bottom: var(--spacing-md);
  }

  .form-group label {
    display: block;
    font-weight: 600;
    color: var(--color-text);
    margin-bottom: var(--spacing-xs);
  }

  .form-group input,
  .form-group select {
    width: 100%;
    padding: var(--spacing-sm);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-size: 1rem;
    transition: border-color 200ms ease;
  }

  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .form-group small {
    display: block;
    margin-top: var(--spacing-xs);
    color: var(--color-text-secondary);
    font-size: 0.85rem;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-lg);
  }

  /* Danger Button */
  .btn-danger {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    color: white;
    border: 2px solid #991b1b;
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #b91c1c 0%, #991b1b 100%);
    border-color: #7f1d1d;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(220, 38, 38, 0.4);
  }

  .btn-danger:disabled {
    background: #9ca3af;
    border-color: #6b7280;
    cursor: not-allowed;
    opacity: 0.6;
  }

  /* Upload Modal Loading/Error States */
  .loading-text {
    padding: var(--spacing-sm);
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .error-text {
    padding: var(--spacing-sm);
    color: #dc2626;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .info-text {
    padding: var(--spacing-sm);
    color: #3b82f6;
    font-size: 0.9rem;
    line-height: 1.5;
    background: #eff6ff;
    border-radius: var(--border-radius-sm);
  }

  /* Models Tab Styles */
  .models-section {
    width: 100%;
  }

  .models-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-lg);
    padding-bottom: var(--spacing-md);
    border-bottom: 2px solid var(--color-border);
  }

  .section-subtitle {
    color: var(--color-text-secondary);
    font-size: 0.95rem;
    margin-top: var(--spacing-xs);
  }

  .models-controls {
    display: flex;
    gap: var(--spacing-md);
    align-items: center;
  }

  .view-toggle {
    display: flex;
    gap: 0;
    background: var(--color-bg-secondary);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    padding: 2px;
  }

  .view-btn {
    padding: var(--spacing-xs) var(--spacing-md);
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1.2rem;
    transition: all 200ms ease;
    border-radius: var(--border-radius-sm);
  }

  .view-btn:hover {
    background: rgba(225, 96, 76, 0.1);
  }

  .view-btn.active {
    background: var(--color-accent);
    color: white;
  }

  /* Table View */
  .models-table-wrapper {
    overflow-x: auto;
    background: white;
    border-radius: var(--border-radius-md);
    border: 2px solid var(--color-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .models-table {
    width: 100%;
    border-collapse: collapse;
  }

  .models-table thead {
    background: var(--color-bg-secondary);
    border-bottom: 2px solid var(--color-border);
  }

  .models-table th {
    padding: var(--spacing-md);
    text-align: left;
    font-weight: 700;
    color: var(--color-text);
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .models-table td {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
  }

  .model-row:hover {
    background: var(--color-bg-secondary);
  }

  .model-name-cell strong {
    color: var(--color-text);
    font-size: 1rem;
  }

  .badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
  }

  .badge-info {
    background: #dbeafe;
    color: #1e40af;
  }

  .badge-source {
    background: #fef3c7;
    color: #92400e;
  }

  .task-type-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid;
  }

  .task-type-detect {
    background: rgba(34, 197, 94, 0.15);
    border-color: #16a34a;
    color: #16a34a;
  }

  .task-type-classify {
    background: rgba(59, 130, 246, 0.15);
    border-color: #2563eb;
    color: #2563eb;
  }

  .task-type-segment {
    background: rgba(168, 85, 247, 0.15);
    border-color: #9333ea;
    color: #9333ea;
  }

  .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .status-ready {
    background: #d1fae5;
    color: #065f46;
  }

  .status-validating {
    background: #dbeafe;
    color: #1e40af;
  }

  .status-failed {
    background: #fee2e2;
    color: #991b1b;
  }

  .metrics-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .metric-mini {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .date-text {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .text-muted {
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .action-buttons {
    display: flex;
    gap: var(--spacing-xs);
  }

  .btn-icon {
    padding: var(--spacing-xs);
    background: transparent;
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    cursor: pointer;
    font-size: 1rem;
    transition: all 200ms ease;
  }

  .btn-icon:hover {
    background: var(--color-bg-secondary);
    border-color: var(--color-accent);
    transform: translateY(-1px);
  }

  .btn-icon-danger:hover {
    background: #fee2e2;
    border-color: #dc2626;
  }

  /* Cards View */
  .models-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: var(--spacing-lg);
  }

  .model-card {
    background: var(--color-bg-card);
    border-radius: var(--border-radius-md);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    transition: all 200ms ease;
    border: 2px solid transparent;
  }

  .model-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
    border-color: var(--color-accent);
  }

  .model-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-md);
    padding-bottom: var(--spacing-md);
    border-bottom: 2px solid var(--color-border);
  }

  .model-card-header h3 {
    margin: 0;
    font-size: 1.2rem;
    color: var(--color-text);
  }

  .model-id {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    display: block;
    margin-top: 4px;
  }

  .model-card-body {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .model-info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .info-label {
    font-weight: 600;
    color: var(--color-text-secondary);
    font-size: 0.9rem;
  }

  .model-metrics {
    margin-top: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 2px solid var(--color-border);
  }

  .model-metrics h4 {
    margin: 0 0 var(--spacing-sm) 0;
    font-size: 0.95rem;
    color: var(--color-text);
  }

  .metrics-grid-mini {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--spacing-sm);
  }

  .metric-item-mini {
    display: flex;
    flex-direction: column;
  }

  .metric-label {
    font-size: 0.8rem;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .metric-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-accent);
  }

  .no-metrics {
    padding: var(--spacing-md);
    background: var(--color-bg-secondary);
    border-radius: var(--border-radius-sm);
    text-align: center;
  }

  .no-metrics p {
    margin: 0;
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .validation-error {
    margin-top: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: #fee2e2;
    border: 2px solid #dc2626;
    border-radius: var(--border-radius-sm);
    font-size: 0.85rem;
  }

  .validation-error strong {
    display: block;
    margin-bottom: 4px;
    color: #991b1b;
  }

  .validation-error p {
    margin: 0;
    color: #7f1d1d;
  }

  .model-card-footer {
    display: flex;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 2px solid var(--color-border);
  }

  .btn-sm {
    padding: var(--spacing-xs) var(--spacing-md);
    font-size: 0.9rem;
  }

  .modal-small {
    max-width: 450px;
  }

  @media (max-width: 1024px) {
    .train-layout,
    .preview-layout-enhanced {
      grid-template-columns: 1fr;
    }

    .jobs-list {
      max-height: none;
    }

    .config-grid-enhanced {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .page {
      padding: var(--spacing-sm);
    }

    .header {
      flex-direction: column;
      gap: var(--spacing-md);
    }

    .header-actions {
      width: 100%;
      justify-content: space-between;
    }

    .btn-back,
    .btn-secondary {
      flex: 1;
      justify-content: center;
    }

    .tabs {
      overflow-x: auto;
      flex-wrap: nowrap;
      -webkit-overflow-scrolling: touch;
    }

    .tab {
      flex-shrink: 0;
      padding: var(--spacing-xs) var(--spacing-md);
      font-size: 0.9rem;
    }

    .stats-grid {
      grid-template-columns: 1fr;
    }

    .stat-value {
      font-size: 2rem;
    }

    .hero-value {
      font-size: 2.5rem;
    }

    .dataset-grid {
      grid-template-columns: 1fr;
    }

    .artifacts-grid-enhanced {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .page {
      padding: var(--spacing-xs);
    }

    h1 {
      font-size: 1.5rem;
    }

    .stat-card {
      padding: var(--spacing-md);
    }

    .stat-icon {
      font-size: 2rem;
    }

    .stat-value {
      font-size: 1.8rem;
    }
  }

  /* Team Management Styles */
  .team-container {
    max-width: 1200px;
    margin: 0 auto;
    border: 2px solid rgba(225, 96, 76, 0.15);
    border-radius: 16px;
    padding: 2rem;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  }

  .team-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xl);
    padding-bottom: var(--spacing-md);
    border-bottom: 2px solid var(--color-bg-light1);
  }

  .team-subtitle {
    color: var(--color-text-light);
    margin-top: var(--spacing-xs);
  }

  .team-table-container {
    background: var(--color-white);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }

  .team-table {
    width: 100%;
    border-collapse: collapse;
  }

  .team-table thead {
    background-color: var(--color-bg-light1);
  }

  .team-table th {
    padding: var(--spacing-md);
    text-align: left;
    font-weight: 600;
    color: var(--color-navy);
    border-bottom: 2px solid var(--color-border);
  }

  .team-table td {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
  }

  .team-table tbody tr:hover {
    background-color: var(--color-bg-light1);
  }

  .member-name {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    font-weight: 500;
  }

  .member-icon {
    font-size: 1.2rem;
  }

  .role-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .role-operator {
    background-color: #e0f2fe;
    color: #0369a1;
  }

  .date-text {
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .info-message {
    padding: var(--spacing-lg);
    background-color: var(--color-bg-light1);
    border-radius: 8px;
    text-align: center;
    color: var(--color-text-light);
  }

  /* Session Form Styles */
  .session-form-container {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .session-form-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
    gap: 1rem;
  }

  .session-form-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .fields-table-container {
    overflow-x: auto;
    margin-bottom: 1rem;
  }

  .fields-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
  }

  .fields-table thead {
    background: #f8f9fa;
  }

  .fields-table th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    color: var(--color-navy);
    border-bottom: 2px solid #dee2e6;
  }

  .fields-table td {
    padding: 1rem;
    border-bottom: 1px solid #dee2e6;
  }

  .fields-table tbody tr:hover {
    background: #f8f9fa;
  }

  .order-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .btn-icon-mini {
    padding: 2px 6px;
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
    transition: all 0.2s;
  }

  .btn-icon-mini:hover:not(:disabled) {
    background: #e9ecef;
    border-color: var(--color-accent);
  }

  .btn-icon-mini:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .options-input {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .options-input input {
    flex: 1;
  }

  .options-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .option-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 4px;
    border: 1px solid #dee2e6;
  }

  .modal-medium {
    max-width: 600px;
  }

  .field-form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-md);
    align-items: start;
  }

  .field-form-grid .full-width {
    grid-column: 1 / -1;
  }

  .checkbox-group {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }

  .checkbox-label {
    display: flex !important;
    align-items: center;
    gap: var(--spacing-xs);
    margin-bottom: 0 !important;
    font-weight: 600 !important;
    cursor: pointer;
  }

  .checkbox-label input[type="checkbox"] {
    width: auto !important;
    margin: 0 !important;
  }

  .form-group {
    margin-bottom: 0;
    display: flex;
    flex-direction: column;
  }

  .form-group label {
    display: block;
    margin-bottom: var(--spacing-xs);
    font-weight: 600;
    color: var(--color-text);
  }

  .form-group input[type="text"],
  .form-group input[type="email"],
  .form-group input[type="number"],
  .form-group input[type="date"],
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: var(--spacing-sm);
    border: 2px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-family: inherit;
    font-size: 1rem;
    transition: all 200ms ease;
  }

  .form-group input[type="text"]:focus,
  .form-group input[type="email"]:focus,
  .form-group input[type="number"]:focus,
  .form-group input[type="date"]:focus,
  .form-group select:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .form-group small {
    display: block;
    margin-top: var(--spacing-xs);
    font-size: 0.85rem;
    color: var(--color-text-secondary);
  }

  .text-danger {
    color: #dc2626;
  }

  /* SAM3 Prompt Controls */
  .prompt-controls {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-sm);
  }

  .prompt-count {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--color-background-secondary);
    border-radius: var(--border-radius-md);
    font-size: 0.9rem;
  }

  .prompt-count strong {
    color: var(--color-accent);
  }

  @media (max-width: 768px) {
    .field-form-grid {
      grid-template-columns: 1fr;
    }

    .field-form-grid .full-width {
      grid-column: 1;
    }
    .session-form-header {
      flex-direction: column;
    }

    .session-form-actions {
      width: 100%;
    }

    .fields-table {
      font-size: 0.85rem;
    }

    .fields-table th,
    .fields-table td {
      padding: 0.75rem;
    }
  }
</style>
