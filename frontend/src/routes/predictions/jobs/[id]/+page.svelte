<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { location, link } from "svelte-spa-router";
  import { navigate } from "../../../../lib/router";
  import { InferenceAPI } from "../../../../lib/api/inference";
  import { uiStore } from "../../../../lib/stores/uiStore";
  import StatCard from "../../../../lib/components/shared/StatCard.svelte";
  import LoadingSpinner from "../../../../lib/components/shared/LoadingSpinner.svelte";
  import EmptyState from "../../../../lib/components/shared/EmptyState.svelte";
  import ExportProgressModal from "../../../../lib/components/shared/ExportProgressModal.svelte";
  import { debounce } from "../../../../lib/utils/filterStorage";
  import type { PredictionJob, PredictionResult } from "@/lib/types";

  export let id: number | undefined = undefined;

  // State
  let job: PredictionJob | null = null;
  let results: PredictionResult[] = [];
  let selectedResult: PredictionResult | null = null;
  let selectedResultImage: string | null = null;
  let loading = true;
  let loadingResults = false;
  let loadingImage = false;
  let error = "";

  // Pagination
  let currentPage = 1;
  let pageSize = 50;
  let totalResults = 0;

  // Filters
  let selectedClasses: Set<string> = new Set();
  let confidenceThreshold = 0.25;
  let availableClasses: string[] = [];

  // Image viewer
  let imageZoom = 1.0;
  let showBoxes = true;
  let canvasElement: HTMLCanvasElement;
  let imageElement: HTMLImageElement;
  let imageLoadController: AbortController | null = null;

  // Export
  let showExportModal = false;
  let exportJobId: number | null = null;
  let exportType: string = "";

  // Polling
  let pollInterval: number | null = null;

  // Responsive
  let isMobile = false;

  // Extract ID from URL
  $: if ($location) {
    const match = $location.match(/^\/predictions\/jobs\/(\d+)/);
    if (match && match[1]) {
      const parsedId = parseInt(match[1]);
      if (parsedId !== id && !isNaN(parsedId) && parsedId > 0) {
        console.log("Extracted prediction job id from URL:", parsedId);
        id = parsedId;
      }
    }
  }

  $: jobId = id as number;

  // Load data when id changes
  $: if (id && !isNaN(id) && id > 0) {
    loadJob();
    loadResults();
  }
  $: totalPages = Math.ceil(totalResults / pageSize);
  $: skip = (currentPage - 1) * pageSize;

  // Start polling when job is running
  $: if (job && job.status === "running" && !pollInterval) {
    pollInterval = window.setInterval(async () => {
      await loadJob();
      if (job && job.status !== "running") {
        clearInterval(pollInterval!);
        pollInterval = null;
        await loadResults(); // Reload results when completed
      }
    }, 3000);
  }

  onMount(async () => {
    checkMobile();
    window.addEventListener("resize", checkMobile);
  });

  onDestroy(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
    if (imageLoadController) {
      imageLoadController.abort();
    }
    window.removeEventListener("resize", checkMobile);
  });

  function checkMobile() {
    isMobile = window.innerWidth < 768;
  }

  async function loadJob() {
    if (!id || isNaN(id) || id <= 0) {
      console.error("Invalid prediction job id:", id);
      return;
    }

    try {
      job = await InferenceAPI.getJob(jobId);

      // Extract available classes
      if (job.summary_json?.class_counts) {
        availableClasses = Object.keys(job.summary_json.class_counts);
      }
    } catch (err: any) {
      error = err.response?.data?.detail || "Failed to load prediction job";
      uiStore.showToast(error, "error");
    } finally {
      loading = false;
    }
  }

  async function loadResults() {
    if (!id || isNaN(id) || id <= 0) {
      console.error("Invalid prediction job id:", id);
      return;
    }

    try {
      loadingResults = true;
      results = await InferenceAPI.getResults(jobId, skip, pageSize);
      totalResults = job?.results_count || 0;

      // Auto-select first result
      if (results.length > 0 && !selectedResult) {
        await selectResult(results[0]);
      }
    } catch (err: any) {
      console.error("Error loading results:", err);
      uiStore.showToast("Failed to load results", "error");
    } finally {
      loadingResults = false;
    }
  }

  async function selectResult(result: PredictionResult) {
    selectedResult = result;
    selectedResultImage = null;
    loadingImage = true;

    // Cancel previous load
    if (imageLoadController) {
      imageLoadController.abort();
    }

    // Create new controller
    imageLoadController = new AbortController();

    try {
      const response = await InferenceAPI.getResultImage(result.id || 0);

      // response.data contains the blob (axios with responseType: 'blob')
      const blob = response.data;
      selectedResultImage = URL.createObjectURL(blob);

      // Draw on canvas after image loads
      setTimeout(() => drawCanvas(), 100);
    } catch (err: any) {
      if (err.name !== "AbortError") {
        console.error("Error loading image:", err);
        uiStore.showToast("Failed to load image", "error");
      }
    } finally {
      loadingImage = false;
      imageLoadController = null;
    }
  }

  function drawCanvas() {
    if (!canvasElement || !imageElement || !selectedResultImage) return;

    const ctx = canvasElement.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    canvasElement.width = imageElement.naturalWidth * imageZoom;
    canvasElement.height = imageElement.naturalHeight * imageZoom;

    // Draw image
    ctx.drawImage(
      imageElement,
      0,
      0,
      canvasElement.width,
      canvasElement.height
    );

    // Draw boxes if enabled
    if (showBoxes && selectedResult) {
      drawBoundingBoxes(ctx);
    }
  }

  function drawBoundingBoxes(ctx: CanvasRenderingContext2D) {
    if (!selectedResult) return;

    const scaleX = imageZoom;
    const scaleY = imageZoom;

    // Draw segmentation masks first (if available)
    if (selectedResult.masks && selectedResult.masks.length > 0) {
      selectedResult.masks.forEach((mask, idx) => {
        const score = selectedResult!.scores[idx];
        const className = mask.class_name || selectedResult!.class_names[idx];

        // Filter by confidence and selected classes
        if (score < confidenceThreshold) return;
        if (selectedClasses.size > 0 && !selectedClasses.has(className)) return;

        if (mask.polygon && mask.polygon.length > 0) {
          // Generate color using golden angle
          const hue = (idx * 137.508) % 360;
          ctx.fillStyle = `hsla(${hue}, 70%, 50%, 0.3)`;
          ctx.strokeStyle = `hsl(${hue}, 70%, 40%)`;
          ctx.lineWidth = 2;

          // Draw polygon with scaling
          ctx.beginPath();
          ctx.moveTo(mask.polygon[0][0] * scaleX, mask.polygon[0][1] * scaleY);
          for (let i = 1; i < mask.polygon.length; i++) {
            ctx.lineTo(
              mask.polygon[i][0] * scaleX,
              mask.polygon[i][1] * scaleY
            );
          }
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        }
      });
    }

    // Draw bounding boxes
    selectedResult.boxes.forEach((box, idx) => {
      const score = selectedResult!.scores[idx];
      const className = selectedResult!.class_names[idx];

      // Filter by confidence and selected classes
      if (score < confidenceThreshold) return;
      if (selectedClasses.size > 0 && !selectedClasses.has(className)) return;

      const [x1, y1, x2, y2] = box;
      const sx1 = x1 * scaleX;
      const sy1 = y1 * scaleY;
      const sx2 = x2 * scaleX;
      const sy2 = y2 * scaleY;

      // Draw box
      ctx.strokeStyle = "#E1604C";
      ctx.lineWidth = 3;
      ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

      // Draw label
      const label = `${className} ${(score * 100).toFixed(1)}%`;
      ctx.font = "14px Montserrat";
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = "#E1604C";
      ctx.fillRect(sx1, sy1 - 25, textWidth + 10, 25);
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(label, sx1 + 5, sy1 - 7);
    });
  }

  // Debounced redraw on filter changes
  const debouncedRedraw = debounce(() => {
    drawCanvas();
  }, 300);

  function handleZoomChange() {
    drawCanvas();
  }

  function toggleShowBoxes() {
    showBoxes = !showBoxes;
    drawCanvas();
  }

  function toggleClassFilter(className: string) {
    if (selectedClasses.has(className)) {
      selectedClasses.delete(className);
    } else {
      selectedClasses.add(className);
    }
    selectedClasses = selectedClasses;
    debouncedRedraw();
  }

  function handleConfidenceChange() {
    debouncedRedraw();
  }

  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
      loadResults();
    }
  }

  // Download functions
  async function downloadImageWithBoxes() {
    if (!canvasElement) return;

    canvasElement.toBlob((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `annotated_${selectedResult!.file_name}`;
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  async function downloadOriginalImage() {
    if (!selectedResultImage) return;

    const link = document.createElement("a");
    link.href = selectedResultImage;
    link.download = selectedResult!.file_name;
    link.click();
  }

  function downloadResultJSON() {
    if (!selectedResult) return;

    const data = {
      file_name: selectedResult.file_name,
      frame_number: selectedResult.frame_number,
      detections: selectedResult.boxes.map((box, i) => ({
        class: selectedResult!.class_names[i],
        confidence: selectedResult!.scores[i],
        box: box,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedResult.file_name}_data.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function downloadResultPDF() {
    if (!selectedResult) return;

    try {
      const response = await InferenceAPI.exportSingleResultPDF(
        selectedResult.id || 0
      );
      exportJobId = response.export_job_id;
      exportType = "report_pdf";
      showExportModal = true;
    } catch (err: any) {
      uiStore.showToast(
        err.response?.data?.detail || "Failed to start PDF export",
        "error"
      );
    }
  }

  // Bulk export functions
  async function startExport(type: "images" | "json" | "csv" | "pdf") {
    try {
      let response;

      if (type === "images") {
        response = await InferenceAPI.exportImages(jobId, { annotated: true });
        exportType = "images_zip";
      } else if (type === "json") {
        response = await InferenceAPI.exportData(jobId, { format: "json" });
        exportType = "data_json";
      } else if (type === "csv") {
        response = await InferenceAPI.exportData(jobId, { format: "csv" });
        exportType = "data_csv";
      } else if (type === "pdf") {
        response = await InferenceAPI.exportPDF(jobId, {});
        exportType = "report_pdf";
      }

      if (response) {
        exportJobId = response.export_job_id;
        showExportModal = true;
      }
    } catch (err: any) {
      uiStore.showToast(
        err.response?.data?.detail || "Failed to start export",
        "error"
      );
    }
  }

  function closeExportModal() {
    showExportModal = false;
    exportJobId = null;
    exportType = "";
  }

  async function handleStopRTSP() {
    if (!job) return;

    const streamType = job.mode === "rtsp" ? "RTSP stream" : "video processing";

    try {
      await InferenceAPI.stopJob(jobId);
      uiStore.showToast(`${streamType} stopped`, "success");
      await loadJob();
    } catch (err: any) {
      uiStore.showToast(
        err.response?.data?.detail || `Failed to stop ${streamType}`,
        "error"
      );
    }
  }

  function getStatusClass(status: string): string {
    const statusMap: Record<string, string> = {
      pending: "badge-pending",
      running: "badge-running",
      completed: "badge-completed",
      failed: "badge-failed",
    };
    return statusMap[status] || "badge-neutral";
  }

  function getModeIcon(mode: string): string {
    const iconMap: Record<string, string> = {
      single: "🖼️",
      batch: "📦",
      video: "🎬",
      rtsp: "📡",
    };
    return iconMap[mode] || "🔍";
  }

  function formatDuration(start: string, end?: string): string {
    if (!end) return "In progress";
    const duration = new Date(end).getTime() - new Date(start).getTime();
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  }

  function getTopClass(): string {
    if (!job?.summary_json?.class_counts) return "N/A";
    const counts = job.summary_json.class_counts;
    const entries = Object.entries(counts);
    if (entries.length === 0) return "N/A";

    const sorted = entries.sort((a: any, b: any) => b[1] - a[1]);
    return `${sorted[0][0]} (${sorted[0][1]})`;
  }
</script>

<div class="page-container">
  {#if loading}
    <LoadingSpinner />
  {:else if error}
    <EmptyState
      icon="❌"
      title="Error Loading Prediction Job"
      message={error}
      actionLabel="Go Back"
      onAction={() => navigate("/predictions")}
    />
  {:else if job}
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <button
          class="breadcrumb-link"
          on:click={() => navigate("/predictions")}
        >
          Prediction Jobs
        </button>
        <span class="breadcrumb-separator">›</span>
        <span class="breadcrumb-current">Job #{job.id}</span>
      </div>

      <div class="header-right">
        {#if job.campaign_id}
          <a
            href="/campaigns/{job.campaign_id}"
            use:link
            class="badge badge-session"
          >
            📁 {job.campaign_name}
          </a>
        {/if}
        <span class="badge {getStatusClass(job.status)}">
          {job.status}
        </span>
        <span class="mode-badge">
          {getModeIcon(job.mode)}
          {job.mode}
        </span>

        {#if job.status === "running" && (job.mode === "rtsp" || job.mode === "video")}
          <button class="btn btn-sm btn-outline" on:click={handleStopRTSP}>
            ⏹️ Stop {job.mode === "rtsp" ? "Stream" : "Video"}
          </button>
        {/if}

        {#if job.status === "completed"}
          <div class="export-dropdown">
            <button class="btn btn-sm btn-primary">📥 Export Results ▼</button>
            <div class="export-menu">
              <button on:click={() => startExport("images")}>
                📦 Images (ZIP)
              </button>
              <button on:click={() => startExport("json")}>
                📄 Data (JSON)
              </button>
              <button on:click={() => startExport("csv")}>
                📊 Data (CSV)
              </button>
              <button on:click={() => startExport("pdf")}>
                📑 PDF Report
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <!-- Job Info -->
    <div class="job-info">
      <div class="info-row">
        <span class="label">Model:</span>
        <span class="value">{job.model_name || `Model #${job.model_id}`}</span>
      </div>
      <div class="info-row">
        <span class="label">Source:</span>
        <span class="value">{job.source_ref}</span>
      </div>
      <div class="info-row">
        <span class="label">Created:</span>
        <span class="value">{new Date(job.created_at).toLocaleString()}</span>
      </div>
    </div>

    {#if job.status === "failed" && job.error_message}
      <div class="error-banner">
        <span class="error-icon">❌</span>
        <div>
          <strong>Error:</strong>
          {job.error_message}
        </div>
      </div>
    {/if}

    <!-- Stats Grid -->
    <div class="stats-grid">
      <StatCard
        label="Total Detections"
        value={(job.summary_json?.total_detections || 0).toLocaleString()}
        icon="🎯"
        animate={true}
        isClickable={false}
      />
      <StatCard
        label="Avg Confidence"
        value={`${((job.summary_json?.average_confidence || 0) * 100).toFixed(1)}%`}
        icon="📈"
        animate={true}
        isClickable={false}
      />
      <StatCard
        label="Duration"
        value={formatDuration(job.created_at, job.completed_at)}
        icon="⏱️"
        animate={true}
        isClickable={false}
      />
      <StatCard
        label="Classes"
        value={availableClasses.length}
        icon="🏷️"
        animate={true}
        isClickable={false}
      />
      <StatCard
        label="Results"
        value={totalResults}
        icon="📊"
        animate={true}
        isClickable={false}
      />
      <StatCard
        label="Top Class"
        value={getTopClass()}
        icon="🥇"
        animate={true}
        isClickable={false}
      />
    </div>

    <!-- Main Content: Gallery + Viewer -->
    <div class="main-content" class:mobile={isMobile}>
      <!-- Left: Thumbnail Gallery -->
      <div class="gallery-panel">
        <div class="panel-header">
          <h3>Results ({totalResults})</h3>
        </div>

        <!-- Filters -->
        <div class="filters">
          <div class="filter-group">
            <div class="filter-label">Confidence Threshold:</div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              bind:value={confidenceThreshold}
              on:input={handleConfidenceChange}
            />
            <span class="filter-value"
              >{(confidenceThreshold * 100).toFixed(0)}%</span
            >
          </div>

          {#if availableClasses.length > 0}
            <div class="filter-group">
              <div class="filter-label">Classes:</div>
              <div class="class-filters">
                {#each availableClasses as className}
                  <button
                    class="class-filter-btn"
                    class:active={selectedClasses.has(className)}
                    on:click={() => toggleClassFilter(className)}
                  >
                    {className}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <!-- Thumbnails -->
        <div class="thumbnails" class:carousel={isMobile}>
          {#if loadingResults}
            <div class="loading-message">Loading results...</div>
          {:else if results.length === 0}
            <EmptyState
              icon="📭"
              title="No Results"
              message="No detection results available for this job."
            />
          {:else}
            {#each results as result (result.id)}
              <button
                class="thumbnail"
                class:selected={selectedResult?.id === result.id}
                on:click={() => selectResult(result)}
              >
                <div class="thumbnail-icon">🖼️</div>
                <div class="thumbnail-info">
                  <div class="thumbnail-name">{result.file_name}</div>
                  {#if result.frame_number !== null}
                    <div class="thumbnail-frame">
                      Frame {result.frame_number}
                    </div>
                  {/if}
                  <div class="thumbnail-count">
                    {result.boxes.length} detection{result.boxes.length !== 1
                      ? "s"
                      : ""}
                  </div>
                </div>
              </button>
            {/each}
          {/if}
        </div>

        <!-- Pagination -->
        {#if totalPages > 1}
          <div class="pagination">
            <button
              class="btn btn-sm"
              disabled={currentPage === 1}
              on:click={() => goToPage(currentPage - 1)}
            >
              ‹
            </button>
            <span class="page-info">
              Page {currentPage} of {totalPages}
            </span>
            <button
              class="btn btn-sm"
              disabled={currentPage === totalPages}
              on:click={() => goToPage(currentPage + 1)}
            >
              ›
            </button>
          </div>
        {/if}
      </div>

      <!-- Right: Image Viewer -->
      <div class="viewer-panel">
        {#if !selectedResult}
          <EmptyState
            icon="👈"
            title="Select a Result"
            message="Click on a thumbnail to view detection results."
          />
        {:else}
          <div class="panel-header">
            <h3>{selectedResult.file_name}</h3>
            <div class="viewer-actions">
              <div class="dropdown">
                <button class="btn btn-sm btn-outline">💾 Download ▼</button>
                <div class="dropdown-menu">
                  <button on:click={downloadImageWithBoxes}>
                    🖼️ With Boxes
                  </button>
                  <button on:click={downloadOriginalImage}>📷 Original</button>
                  <button on:click={downloadResultJSON}>📄 JSON Data</button>
                  <button on:click={downloadResultPDF}>📑 PDF Report</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Controls -->
          <div class="viewer-controls">
            <label class="control-item">
              <input
                type="checkbox"
                bind:checked={showBoxes}
                on:change={toggleShowBoxes}
              />
              Show Boxes
            </label>
            <label class="control-item">
              Zoom: {(imageZoom * 100).toFixed(0)}%
              <input
                type="range"
                min="0.5"
                max="3"
                step="0.1"
                bind:value={imageZoom}
                on:input={handleZoomChange}
              />
            </label>
          </div>

          <!-- Canvas -->
          <div class="canvas-container">
            {#if loadingImage}
              <div class="loading-overlay">
                <LoadingSpinner />
              </div>
            {:else if selectedResultImage}
              <img
                bind:this={imageElement}
                src={selectedResultImage}
                alt={selectedResult.file_name}
                style="display: none;"
                on:load={drawCanvas}
              />
              <canvas bind:this={canvasElement} class="detection-canvas"
              ></canvas>
            {/if}
          </div>

          <!-- Detection Table -->
          <div class="detection-table">
            <h4>Detections ({selectedResult.boxes.length})</h4>
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Confidence</th>
                  <th>Box Coordinates</th>
                </tr>
              </thead>
              <tbody>
                {#each selectedResult.boxes as box, idx}
                  {#if selectedResult.scores[idx] >= confidenceThreshold}
                    <tr>
                      <td>{selectedResult.class_names[idx]}</td>
                      <td>{(selectedResult.scores[idx] * 100).toFixed(1)}%</td>
                      <td>
                        [{box.map((v) => v.toFixed(0)).join(", ")}]
                      </td>
                    </tr>
                  {/if}
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- Export Modal -->
{#if showExportModal && exportJobId && exportType}
  <ExportProgressModal
    {jobId}
    {exportJobId}
    {exportType}
    onClose={closeExportModal}
  />
{/if}

<style>
  .page-container {
    padding: var(--spacing-md);
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  @media (min-width: 768px) {
    .page-container {
      padding: var(--spacing-lg);
    }
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-lg);
    flex-wrap: wrap;
    gap: var(--spacing-md);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .breadcrumb-link {
    background: none;
    border: none;
    color: var(--color-accent);
    cursor: pointer;
    font-size: var(--font-size-base);
  }

  .breadcrumb-link:hover {
    text-decoration: underline;
  }

  .breadcrumb-separator {
    color: var(--color-text-secondary);
  }

  .breadcrumb-current {
    font-weight: 600;
    color: var(--color-navy);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .mode-badge {
    padding: 4px 12px;
    background: var(--color-bg-light1);
    border-radius: 6px;
    font-size: var(--font-size-sm);
    font-weight: 500;
  }

  .job-info {
    background: var(--color-white);
    padding: var(--spacing-md);
    border-radius: 8px;
    margin-bottom: var(--spacing-lg);
    box-shadow: var(--shadow-sm);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: var(--spacing-sm) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .label {
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .value {
    color: var(--color-navy);
  }

  .error-banner {
    background: #fee;
    border: 1px solid #f88;
    border-radius: 8px;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
    display: flex;
    align-items: start;
    gap: var(--spacing-md);
    color: #c00;
  }

  .error-icon {
    font-size: var(--font-size-xl);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
  }

  @media (min-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1024px) {
    .stats-grid {
      grid-template-columns: repeat(6, 1fr);
    }
  }

  .main-content {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
    height: calc(100vh - 500px);
    min-height: 600px;
  }

  @media (min-width: 768px) {
    .main-content:not(.mobile) {
      grid-template-columns: 350px 1fr;
    }
  }

  @media (min-width: 1920px) {
    .main-content:not(.mobile) {
      grid-template-columns: 400px 1fr;
    }
  }

  .gallery-panel,
  .viewer-panel {
    background: var(--color-white);
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .panel-header {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-header h3 {
    margin: 0;
    font-size: var(--font-size-lg);
    color: var(--color-navy);
  }

  .filters {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
  }

  .filter-group {
    margin-bottom: var(--spacing-sm);
  }

  .filter-group:last-child {
    margin-bottom: 0;
  }

  .filter-label {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 600;
    margin-bottom: var(--spacing-xs);
    color: var(--color-navy);
  }

  .filter-group input[type="range"] {
    width: 100%;
  }

  .filter-value {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .class-filters {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .class-filter-btn {
    padding: 4px 12px;
    background: var(--color-bg-light1);
    border: 1px solid var(--color-border);
    border-radius: 16px;
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .class-filter-btn:hover {
    background: var(--color-bg-light2);
  }

  .class-filter-btn.active {
    background: var(--color-accent);
    color: var(--color-white);
    border-color: var(--color-accent);
  }

  .thumbnails {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-md);
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-sm);
    align-content: start;
  }

  @media (min-width: 768px) {
    .thumbnails:not(.carousel) {
      grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    }
  }

  .thumbnails.carousel {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    gap: var(--spacing-md);
  }

  .thumbnail {
    background: var(--color-bg-light1);
    border: 2px solid var(--color-border);
    border-radius: 8px;
    padding: var(--spacing-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: center;
  }

  .thumbnails.carousel .thumbnail {
    min-width: 150px;
    scroll-snap-align: start;
  }

  .thumbnail:hover {
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .thumbnail.selected {
    border-color: var(--color-accent);
    border-width: 3px;
    background: var(--color-bg-light2);
  }

  .thumbnail-icon {
    font-size: 2rem;
    margin-bottom: var(--spacing-xs);
  }

  .thumbnail-info {
    font-size: var(--font-size-xs);
  }

  .thumbnail-name {
    font-weight: 600;
    color: var(--color-navy);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .thumbnail-frame {
    color: var(--color-text-secondary);
  }

  .thumbnail-count {
    color: var(--color-accent);
    font-weight: 600;
  }

  .pagination {
    padding: var(--spacing-md);
    border-top: 1px solid var(--color-border);
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--spacing-md);
  }

  .page-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .viewer-actions {
    display: flex;
    gap: var(--spacing-sm);
  }

  .viewer-controls {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    gap: var(--spacing-lg);
    align-items: center;
    flex-wrap: wrap;
  }

  .control-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    font-size: var(--font-size-sm);
  }

  .canvas-container {
    flex: 1;
    overflow: auto;
    padding: var(--spacing-md);
    background: #f5f5f5;
    position: relative;
  }

  .detection-canvas {
    display: block;
    max-width: 100%;
    height: auto;
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.8);
  }

  .detection-table {
    padding: var(--spacing-md);
    border-top: 1px solid var(--color-border);
    max-height: 200px;
    overflow-y: auto;
  }

  .detection-table h4 {
    margin: 0 0 var(--spacing-sm) 0;
    font-size: var(--font-size-base);
    color: var(--color-navy);
  }

  .detection-table table {
    width: 100%;
    font-size: var(--font-size-sm);
  }

  .detection-table th {
    text-align: left;
    padding: var(--spacing-xs);
    background: var(--color-bg-light1);
    font-weight: 600;
  }

  .detection-table td {
    padding: var(--spacing-xs);
    border-bottom: 1px solid var(--color-border);
  }

  .dropdown,
  .export-dropdown {
    position: relative;
  }

  .dropdown-menu,
  .export-menu {
    display: none;
    position: absolute;
    top: calc(100% + 2px);
    right: 0;
    background: var(--color-white);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: var(--shadow-lg);
    z-index: 100;
    min-width: 180px;
    padding-top: 2px;
  }

  .dropdown:hover .dropdown-menu,
  .export-dropdown:hover .export-menu {
    display: block;
  }

  /* Extend hover area to cover gap */
  .dropdown::after,
  .export-dropdown::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    height: 4px;
  }

  .dropdown-menu button,
  .export-menu button {
    display: block;
    width: 100%;
    padding: var(--spacing-sm) var(--spacing-md);
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .dropdown-menu button:hover,
  .export-menu button:hover {
    background: var(--color-bg-light1);
  }

  .badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
  }

  .badge-pending {
    background: var(--color-status-warning);
    color: var(--color-white);
  }

  .badge-running {
    background: var(--color-status-running);
    color: var(--color-white);
  }

  .badge-completed {
    background: var(--color-status-completed);
    color: var(--color-white);
  }

  .badge-failed {
    background: var(--color-status-error);
    color: var(--color-white);
  }

  .badge-session {
    background: #9333ea;
    color: white;
    text-decoration: none;
    display: inline-block;
  }

  .badge-session:hover {
    background: #7e22ce;
  }

  .loading-message {
    text-align: center;
    padding: var(--spacing-xl);
    color: var(--color-text-secondary);
  }
</style>
