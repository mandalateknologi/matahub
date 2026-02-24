<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { navigate, link } from "../../lib/router";
  import { InferenceAPI } from "../../lib/api/inference";
  import { datasetsAPI } from "../../lib/api/datasets";
  import { modelsAPI } from "../../lib/api/models";
  import { uiStore } from "../../lib/stores/uiStore";
  import StatCard from "../../lib/components/shared/StatCard.svelte";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import EmptyState from "../../lib/components/shared/EmptyState.svelte";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import Badge from "../../lib/components/shared/Badge.svelte";
  import {
    getDateRange,
    getPresetOptions,
    type DatePreset,
  } from "../../lib/utils/dateRanges";
  import {
    loadFilters,
    saveFilters,
    debounce,
  } from "../../lib/utils/filterStorage";
  import type {
    PredictionJob,
    PredictionSummary,
    Dataset,
    Model,
  } from "@/lib/types";

  let jobs = $state<PredictionJob[]>([]);
  let stats = $state<PredictionSummary | null>(null);
  let datasets = $state<Dataset[]>([]);
  let models = $state<Model[]>([]);
  let loading = $state(true);
  let error = $state("");
  let searchTerm = $state("");
  let view = $state<"card" | "list">("list");
  let selectedStatFilter = $state<string | null>(null);
  let sortColumn = $state<string | null>("created_at");
  let sortOrder = $state<"asc" | "desc">("desc");
  let statsAnimated = $state(false);
  let pollInterval = $state<number | null>(null);

  // Pagination
  let currentPage = $state(1);
  let pageSize = $state(20);
  let totalJobs = $state(0);

  // Filters
  let selectedDataset = $state<number | string>("");
  let selectedModel = $state<number | string>("");
  let selectedStatus = $state("");
  let selectedMode = $state("");
  let selectedTaskType = $state(""); // New task type filter
  let selectedDatePreset = $state<DatePreset>("all");
  let startDate = $state("");
  let endDate = $state("");

  let totalPages = $derived(Math.ceil(totalJobs / pageSize));

  // Check if any filters are active
  let hasActiveFilters = $derived(
    !!(
      selectedDataset ||
      selectedModel ||
      selectedStatus ||
      selectedMode ||
      selectedTaskType ||
      selectedDatePreset !== "all" ||
      searchTerm ||
      selectedStatFilter
    )
  );

  // Update dates when preset changes (except for custom)
  $effect(() => {
    if (selectedDatePreset && selectedDatePreset !== "custom") {
      const range = getDateRange(selectedDatePreset);
      const newStart = range ? range.start : "";
      const newEnd = range ? range.end : "";
      
      // Only update and reload if dates actually changed
      if (startDate !== newStart || endDate !== newEnd) {
        startDate = newStart;
        endDate = newEnd;
        handleFilterChange();
      }
    }
  });

  // Save filters to localStorage whenever they change
  $effect(() => {
    const filtersToSave = {
      selectedDataset,
      selectedModel,
      selectedStatus,
      selectedMode,
      selectedTaskType,
      selectedDatePreset,
      startDate,
      endDate,
      searchTerm,
      view,
      currentPage,
      sortColumn,
      sortOrder,
    };

    saveFilters(filtersToSave);
  });

  // Debounced search function
  const debouncedSearch = debounce((term: string) => {
    currentPage = 1;
    loadDetectionJobs();
  }, 500);

  onMount(async () => {
    // Load saved filters from localStorage
    const savedFilters = loadFilters();
    if (
      savedFilters.selectedDataset !== undefined &&
      savedFilters.selectedDataset !== null
    )
      selectedDataset = savedFilters.selectedDataset;
    if (
      savedFilters.selectedModel !== undefined &&
      savedFilters.selectedModel !== null
    )
      selectedModel = savedFilters.selectedModel;
    if (
      savedFilters.selectedStatus !== undefined &&
      savedFilters.selectedStatus !== null
    )
      selectedStatus = savedFilters.selectedStatus;
    if (
      savedFilters.selectedMode !== undefined &&
      savedFilters.selectedMode !== null
    )
      selectedMode = savedFilters.selectedMode;
    if (
      savedFilters.selectedTaskType !== undefined &&
      savedFilters.selectedTaskType !== null
    )
      selectedTaskType = savedFilters.selectedTaskType;
    if (savedFilters.selectedDatePreset !== undefined)
      selectedDatePreset = savedFilters.selectedDatePreset as DatePreset;
    if (savedFilters.startDate !== undefined)
      startDate = savedFilters.startDate;
    if (savedFilters.endDate !== undefined) endDate = savedFilters.endDate;
    if (savedFilters.searchTerm !== undefined)
      searchTerm = savedFilters.searchTerm;
    if (savedFilters.view !== undefined) view = savedFilters.view;
    if (savedFilters.currentPage !== undefined)
      currentPage = savedFilters.currentPage;
    if (savedFilters.sortColumn !== undefined)
      sortColumn = savedFilters.sortColumn;
    if (savedFilters.sortOrder !== undefined)
      sortOrder = savedFilters.sortOrder;

    await Promise.all([
      loadDetectionJobs(),
      loadStats(),
      loadDatasets(),
      loadModels(),
    ]);
    setTimeout(() => (statsAnimated = true), 100);

    // Poll every 5 seconds for updates
    pollInterval = window.setInterval(async () => {
      await Promise.all([loadDetectionJobs(), loadStats()]);
    }, 5000);
  });

  onDestroy(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  async function loadDetectionJobs() {
    try {
      // Calculate skip based on current page to avoid stale derived values
      const skip = (currentPage - 1) * pageSize;
      
      const filters: any = {};
      if (selectedDataset && selectedDataset !== "") {
        filters.datasetId =
          typeof selectedDataset === "string"
            ? parseInt(selectedDataset)
            : selectedDataset;
      }
      if (selectedModel && selectedModel !== "") {
        filters.modelId =
          typeof selectedModel === "string"
            ? parseInt(selectedModel)
            : selectedModel;
      }
      if (selectedStatus && selectedStatus !== "")
        filters.status = selectedStatus;
      if (selectedMode && selectedMode !== "") filters.mode = selectedMode;
      if (selectedTaskType && selectedTaskType !== "")
        filters.taskType = selectedTaskType;
      if (startDate) filters.startDate = startDate; // Already in ISO format (YYYY-MM-DD)
      if (endDate) filters.endDate = endDate; // Already in ISO format (YYYY-MM-DD)
      if (searchTerm) filters.search = searchTerm;
      if (sortColumn) filters.sortBy = sortColumn;
      if (sortOrder) filters.sortOrder = sortOrder;

      const response = await InferenceAPI.getJobs(skip, pageSize, filters);
      jobs = response.jobs;
      totalJobs = response.total;
    } catch (err: any) {
      error = err.response?.data?.detail || "Failed to load detection jobs";
      console.error("Error loading detection jobs:", err);
      if (loading) {
        uiStore.showToast(error, "error");
      }
    } finally {
      loading = false;
    }
  }

  async function loadStats() {
    try {
      stats = await InferenceAPI.getStats();
      // Don't overwrite totalJobs here - it's set correctly by loadDetectionJobs() based on filters
    } catch (err: any) {
      console.error("Error loading stats:", err);
    }
  }

  async function loadDatasets() {
    try {
      datasets = await datasetsAPI.listDatasets();
    } catch (err: any) {
      console.error("Error loading datasets:", err);
      uiStore.showError(
        "Failed to load datasets. Please try again later.",
        "Dataset Load Error"
      );
    }
  }

  async function loadModels() {
    try {
      models = await modelsAPI.listModels();
    } catch (err: any) {
      console.error("Error loading models:", err);
      uiStore.showError(
        "Failed to load models. Please try again later.",
        "Model Load Error"
      );
    }
  }

  async function handleFilterChange() {
    currentPage = 1; // Reset to first page
    loading = true;
    await loadDetectionJobs();
  }

  function clearFilters() {
    selectedDataset = "";
    selectedModel = "";
    selectedStatus = "";
    selectedMode = "";
    selectedTaskType = "";
    selectedDatePreset = "all";
    startDate = "";
    endDate = "";
    searchTerm = "";
    selectedStatFilter = null;
    currentPage = 1;
    handleFilterChange();
  }

  function handleSearchInput(event: Event) {
    const target = event.target as HTMLInputElement;
    searchTerm = target.value;
    selectedStatFilter = null;
    debouncedSearch(searchTerm);
  }

  function handleStatClick(filterType: string) {
    if (selectedStatFilter === filterType) {
      selectedStatFilter = null;
    } else {
      selectedStatFilter = filterType;
    }
  }

  function handleViewChange(newView: "card" | "list") {
    view = newView;
  }

  function goToPage(page: number) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
      console.log("Navigating to page:", currentPage);
      loadDetectionJobs();
    }
  }

  function handleSort(column: string) {
    if (sortColumn === column) {
      // Toggle sort order
      sortOrder = sortOrder === "asc" ? "desc" : "asc";
    } else {
      // New column, default to descending
      sortColumn = column;
      sortOrder = "desc";
    }
    currentPage = 1; // Reset to first page on sort change
    loadDetectionJobs();
  }

  async function handleStopRTSP(jobId: number) {
    try {
      await InferenceAPI.stopJob(jobId);
      uiStore.showToast("RTSP stream stopped", "success");
      await loadDetectionJobs();
    } catch (err: any) {
      uiStore.showToast(
        err.response?.data?.detail || "Failed to stop RTSP stream",
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

  function getModeClass(mode: string): string {
    const modeMap: Record<string, string> = {
      single: "badge-info",
      batch: "badge-warning",
      video: "badge-accent",
      rtsp: "badge-running",
    };
    return modeMap[mode] || "badge-neutral";
  }

  // Badge variant helpers (for Badge component)
  function getStatusVariant(
    status: string
  ):
    | "success"
    | "warning"
    | "error"
    | "info"
    | "neutral"
    | "running"
    | "pending"
    | "completed"
    | "failed" {
    const variantMap: Record<string, any> = {
      pending: "pending",
      running: "running",
      completed: "completed",
      failed: "failed",
    };
    return variantMap[status] || "neutral";
  }

  function getModeVariant(
    mode: string
  ): "info" | "warning" | "accent" | "running" | "neutral" {
    const variantMap: Record<string, any> = {
      single: "info",
      batch: "warning",
      video: "accent",
      rtsp: "running",
    };
    return variantMap[mode] || "neutral";
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

  // Task type helpers
  function getTaskTypeIcon(taskType: string | undefined): string {
    if (!taskType) return "🎯";
    const iconMap: Record<string, string> = {
      detect: "🎯",
      classify: "🏷️",
      segment: "✂️",
    };
    return iconMap[taskType] || "🎯";
  }

  function getTaskTypeVariant(
    taskType: string | undefined
  ): "info" | "warning" | "accent" | "neutral" {
    if (!taskType) return "info";
    const variantMap: Record<string, any> = {
      detect: "info",
      classify: "accent",
      segment: "warning",
    };
    return variantMap[taskType] || "neutral";
  }

  function getTaskTypeLabel(taskType: string | undefined): string {
    if (!taskType) return "Detection";
    const labelMap: Record<string, string> = {
      detect: "Detection",
      classify: "Classification",
      segment: "Segmentation",
    };
    return labelMap[taskType] || taskType;
  }

  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleString();
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

  function getTopClass(summary: Record<string, any>): string {
    if (!summary || !summary.class_counts) return "N/A";
    const counts = summary.class_counts;
    const entries = Object.entries(counts);
    if (entries.length === 0) return "N/A";

    const sorted = entries.sort((a: any, b: any) => b[1] - a[1]);
    return `${sorted[0][0]} (${sorted[0][1]})`;
  }

  function getProgressDisplay(job: PredictionJob): {
    type: string;
    value: number | string;
  } {
    if (job.status !== "running") return { type: "none", value: 0 };

    if (job.mode === "rtsp") {
      return { type: "frames", value: job.progress || 0 };
    } else {
      return { type: "percentage", value: job.progress || 0 };
    }
  }
</script>

<div class="page-container">
  <div class="page-header">
    <div>
      <h1 class="page-title">Prediction Jobs</h1>
      <p class="page-subtitle">Monitor and manage all prediction tasks</p>
    </div>
    <button
      class="btn btn-primary"
      on:click={() => navigate("/predictions/capture")}
    >
      <span class="btn-icon">➕</span>
      New Prediction Job
    </button>
  </div>

  {#if loading && jobs.length === 0}
    <LoadingSpinner />
  {:else if error && jobs.length === 0}
    <EmptyState
      icon="❌"
      title="Error Loading Prediction Jobs"
      message={`${error}. Please try again or contact support if the problem persists.`}
      actionLabel="Retry"
      onAction={loadDetectionJobs}
    />
  {:else}
    <!-- Statistics Grid -->
    {#if stats}
      <div class="stats-grid">
        <StatCard
          label="Total Jobs"
          value={stats.total_jobs ?? 0}
          icon="📊"
          animate={statsAnimated}
          isClickable={false}
        />
        <StatCard
          label="Running"
          value={stats.running_jobs ?? 0}
          icon="🔄"
          animate={statsAnimated}
          isClickable={true}
          filterType="running"
          isActive={selectedStatFilter === "running"}
          on:click={() => handleStatClick("running")}
        />
        <StatCard
          label="Completed"
          value={stats.completed_jobs ?? 0}
          icon="✅"
          animate={statsAnimated}
          isClickable={true}
          filterType="completed"
          isActive={selectedStatFilter === "completed"}
          on:click={() => handleStatClick("completed")}
        />
        <StatCard
          label="Failed"
          value={stats.failed_jobs ?? 0}
          icon="❌"
          animate={statsAnimated}
          isClickable={true}
          filterType="failed"
          isActive={selectedStatFilter === "failed"}
          on:click={() => handleStatClick("failed")}
        />
        <StatCard
          label="Total Predictions"
          value={(stats.total_predictions ?? 0).toLocaleString()}
          icon="🎯"
          animate={statsAnimated}
          isClickable={false}
        />
        <StatCard
          label="Avg Confidence"
          value={`${((stats.average_confidence ?? 0) * 100).toFixed(1)}%`}
          icon="📈"
          animate={statsAnimated}
          isClickable={false}
        />
      </div>

      <!-- Mode breakdown -->
      <div class="stats-grid mode-grid">
        <StatCard
          label="Single Image"
          value={stats.single_jobs ?? 0}
          icon="🖼️"
          animate={statsAnimated}
          isClickable={true}
          filterType="single"
          isActive={selectedStatFilter === "single"}
          on:click={() => handleStatClick("single")}
        />
        <StatCard
          label="Batch"
          value={stats.batch_jobs ?? 0}
          icon="📦"
          animate={statsAnimated}
          isClickable={true}
          filterType="batch"
          isActive={selectedStatFilter === "batch"}
          on:click={() => handleStatClick("batch")}
        />
        <StatCard
          label="Video"
          value={stats.video_jobs ?? 0}
          icon="🎬"
          animate={statsAnimated}
          isClickable={true}
          filterType="video"
          isActive={selectedStatFilter === "video"}
          on:click={() => handleStatClick("video")}
        />
        <StatCard
          label="RTSP Stream"
          value={stats.rtsp_jobs ?? 0}
          icon="📡"
          animate={statsAnimated}
          isClickable={true}
          filterType="rtsp"
          isActive={selectedStatFilter === "rtsp"}
          on:click={() => handleStatClick("rtsp")}
        />
      </div>
    {/if}

    <!-- Filters -->
    <div class="filters-section">
      <div class="search-bar">
        <input
          type="text"
          placeholder="🔍 Search by job ID or source..."
          value={searchTerm}
          on:input={handleSearchInput}
          class="search-input"
        />
      </div>

      <div class="filter-grid">
        <select
          bind:value={selectedDataset}
          on:change={handleFilterChange}
          class="filter-select"
        >
          <option value="">All Datasets</option>
          {#each datasets as dataset}
            <option value={dataset.id}>{dataset.name}</option>
          {/each}
        </select>

        <select
          bind:value={selectedModel}
          on:change={handleFilterChange}
          class="filter-select"
        >
          <option value="">All Models</option>
          {#each models as model}
            <option value={model.id}>{model.name}</option>
          {/each}
        </select>

        <select
          bind:value={selectedStatus}
          on:change={handleFilterChange}
          class="filter-select"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>

        <select
          bind:value={selectedMode}
          on:change={handleFilterChange}
          class="filter-select"
        >
          <option value="">All Modes</option>
          <option value="single">Single Image</option>
          <option value="batch">Batch</option>
          <option value="video">Video</option>
          <option value="rtsp">RTSP Stream</option>
        </select>

        <select
          bind:value={selectedTaskType}
          on:change={handleFilterChange}
          class="filter-select"
        >
          <option value="">All Task Types</option>
          <option value="detect">🎯 Detection</option>
          <option value="classify">🏷️ Classification</option>
          <option value="segment">✂️ Segmentation</option>
        </select>

        <select bind:value={selectedDatePreset} class="filter-select">
          {#each getPresetOptions() as preset}
            <option value={preset.value}>{preset.label}</option>
          {/each}
        </select>

        {#if selectedDatePreset === "custom"}
          <input
            type="date"
            bind:value={startDate}
            on:change={handleFilterChange}
            class="filter-input"
            placeholder="Start Date"
          />

          <input
            type="date"
            bind:value={endDate}
            on:change={handleFilterChange}
            class="filter-input"
            placeholder="End Date"
          />
        {/if}

        <button class="btn btn-sm btn-outline" on:click={clearFilters}>
          Clear Filters
        </button>
      </div>
    </div>

    <!-- View Toggle and Count -->
    {#if totalJobs > 0}
      <div class="toolbar">
        <div class="job-count">
          Showing {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, totalJobs)} of {totalJobs}
          jobs
          {#if selectedStatFilter}
            <span class="filter-badge">(filtered by {selectedStatFilter})</span>
          {/if}
        </div>
        <ViewToggle {view} onChange={handleViewChange} />
      </div>
    {/if}

    <!-- Jobs Display -->
    {#if jobs.length === 0}
      <EmptyState
        icon={hasActiveFilters ? "🔍" : "🎯"}
        title={hasActiveFilters
          ? "No detection jobs found"
          : "Start Your First Detection"}
        message={hasActiveFilters
          ? "No jobs match your current filters. Try adjusting your search criteria or clearing all filters to see available jobs."
          : "Run object detection on images, videos, or RTSP streams. Get started by creating a detection job from one of the options below."}
        actionLabel={hasActiveFilters
          ? "Clear All Filters"
          : "Go to Detection Tools"}
        onAction={hasActiveFilters
          ? clearFilters
          : () => navigate("/predictions/capture")}
      />
    {:else if view === "card"}
      <div class="card-grid">
        {#each jobs as job (job.id)}
          <div
            class="job-card"
            on:click={() => navigate(`/predictions/jobs/${job.id}`)}
          >
            <div class="card-header">
              <div class="card-title-row">
                <span class="job-id">Job #{job.id}</span>
                <Badge
                  variant={getTaskTypeVariant(job.task_type)}
                  icon={getTaskTypeIcon(job.task_type)}
                >
                  {getTaskTypeLabel(job.task_type)}
                </Badge>
                <Badge
                  variant={getModeVariant(job.mode)}
                  icon={getModeIcon(job.mode)}
                >
                  {job.mode}
                </Badge>
                {#if job.campaign_id}
                  <a
                    href="/campaigns/{job.campaign_id}"
                    use:link
                    on:click|stopPropagation
                    style="text-decoration: none;"
                  >
                    <Badge variant="campaign" icon="📁">
                      {job.campaign_name}
                    </Badge>
                  </a>
                {/if}
              </div>
              <Badge variant={getStatusVariant(job.status)}>
                {job.status}
              </Badge>
            </div>

            <div class="card-body">
              <div class="info-row">
                <span class="label">Source:</span>
                <span class="value truncate">{job.source_ref}</span>
              </div>
              <div class="info-row">
                <span class="label">Model:</span>
                <span class="value truncate"
                  >{job.model_name || `ID: ${job.model_id}`}</span
                >
              </div>

              {#if job.status === "failed" && job.error_message}
                <div class="error-box">
                  <strong>Error:</strong>
                  {job.error_message}
                </div>
              {/if}

              {#if job.status === "running"}
                {@const progress = getProgressDisplay(job)}
                {#if progress.type === "percentage"}
                  <div class="progress-section">
                    <div class="progress-label">
                      Progress: {progress.value}%
                    </div>
                    <div class="progress-bar">
                      <div
                        class="progress-fill"
                        style="width: {progress.value}%"
                      ></div>
                    </div>
                  </div>
                {:else if progress.type === "frames"}
                  <div class="frames-badge">
                    📊 {progress.value} frames processed
                  </div>
                {/if}
              {/if}

              {#if job.status === "completed" && job.summary_json}
                <div class="summary-section">
                  <div class="summary-item">
                    <span class="summary-label">Predictions:</span>
                    <span class="summary-value"
                      >{job.summary_json.total_detections || 0}</span
                    >
                  </div>
                  <div class="summary-item">
                    <span class="summary-label">Top Class:</span>
                    <span class="summary-value"
                      >{getTopClass(job.summary_json)}</span
                    >
                  </div>
                  <div class="summary-item">
                    <span class="summary-label">Confidence:</span>
                    <span class="summary-value">
                      {job.summary_json.average_confidence
                        ? `${(job.summary_json.average_confidence * 100).toFixed(1)}%`
                        : "N/A"}
                    </span>
                  </div>
                </div>
              {/if}

              <div class="info-row">
                <span class="label">Results:</span>
                <span class="value">{job.results_count || 0}</span>
              </div>
              <div class="info-row">
                <span class="label">Created:</span>
                <span class="value">{formatDate(job.created_at)}</span>
              </div>
              {#if job.completed_at}
                <div class="info-row">
                  <span class="label">Duration:</span>
                  <span class="value"
                    >{formatDuration(job.created_at, job.completed_at)}</span
                  >
                </div>
              {/if}
            </div>

            <div class="card-footer">
              <button
                class="btn btn-sm btn-primary"
                on:click|stopPropagation={() =>
                  navigate(`/predictions/jobs/${job.id}`)}
              >
                View Results
              </button>
              {#if job.status === "running" && job.mode === "rtsp"}
                <button
                  class="btn btn-sm btn-danger"
                  on:click|stopPropagation={() => handleStopRTSP(job.id)}
                >
                  Stop Stream
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <!-- List View -->
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th
                class="sortable"
                class:active={sortColumn === "id"}
                on:click={() => handleSort("id")}
              >
                ID<span class="sort-icon"
                  >{sortColumn === "id"
                    ? sortOrder === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}</span
                >
              </th>
              <th
                class="sortable"
                class:active={sortColumn === "mode"}
                on:click={() => handleSort("mode")}
              >
                Mode<span class="sort-icon"
                  >{sortColumn === "mode"
                    ? sortOrder === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}</span
                >
              </th>
              <th>Tasks</th>
              <th
                class="sortable"
                class:active={sortColumn === "status"}
                on:click={() => handleSort("status")}
              >
                Status<span class="sort-icon"
                  >{sortColumn === "status"
                    ? sortOrder === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}</span
                >
              </th>
              <th>Model</th>
              <th
                class="sortable"
                class:active={sortColumn === "progress"}
                on:click={() => handleSort("progress")}
              >
                Progress<span class="sort-icon"
                  >{sortColumn === "progress"
                    ? sortOrder === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}</span
                >
              </th>
              <th>Predictions</th>
              <th>Confidence (Avg.)</th>
              <th>Results</th>
              <th
                class="sortable"
                class:active={sortColumn === "created_at"}
                on:click={() => handleSort("created_at")}
              >
                Created<span class="sort-icon"
                  >{sortColumn === "created_at"
                    ? sortOrder === "asc"
                      ? " ▲"
                      : " ▼"
                    : ""}</span
                >
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each jobs as job (job.id)}
              <tr
                on:click={() => navigate(`/predictions/jobs/${job.id}`)}
                class="clickable-row"
              >
                <td>#{job.id}</td>
                <td>
                  <Badge
                    variant={getModeVariant(job.mode)}
                    icon={getModeIcon(job.mode)}
                    size="sm"
                  >
                    {job.mode}
                  </Badge>
                  {#if job.campaign_id}
                    <a
                      href="/campaigns/{job.campaign_id}"
                      use:link
                      on:click|stopPropagation
                      style="text-decoration: none; margin-left: 4px;"
                    >
                      <Badge variant="session" icon="📁" size="sm">
                        {job.campaign_name}
                      </Badge>
                    </a>
                  {/if}
                </td>
                <td>
                  <Badge
                    variant={getTaskTypeVariant(job.task_type)}
                    icon={getTaskTypeIcon(job.task_type)}
                    size="sm"
                  >
                    {getTaskTypeLabel(job.task_type)}
                  </Badge>
                </td>
                <td>
                  <Badge variant={getStatusVariant(job.status)} size="sm">
                    {job.status}
                  </Badge>
                </td>
                <td class="truncate" style="max-width: 150px;">
                  {job.model_name || `ID: ${job.model_id}`}
                </td>
                <td>
                  {#if job.status === "running"}
                    {@const progress = getProgressDisplay(job)}
                    {#if progress.type === "percentage"}
                      {progress.value}%
                    {:else if progress.type === "frames"}
                      {progress.value} frames
                    {/if}
                  {:else}
                    -
                  {/if}
                </td>
                <td>
                  {#if job.task_type === "segment"}
                    {job.summary_json?.total_masks ||
                      job.summary_json?.total_detections ||
                      0}
                  {:else}
                    {job.summary_json?.total_detections || 0}
                  {/if}
                </td>
                <td>
                  {job.summary_json?.average_confidence
                    ? `${(job.summary_json.average_confidence * 100).toFixed(1)}%`
                    : "-"}
                </td>
                <td>{job.results_count || 0}</td>
                <td>{formatDate(job.created_at)}</td>
                <td>
                  <div class="action-buttons">
                    <button
                      class="btn btn-xs btn-primary"
                      on:click|stopPropagation={() =>
                        navigate(`/predictions/jobs/${job.id}`)}
                    >
                      View
                    </button>
                    {#if job.status === "running" && job.mode === "rtsp"}
                      <button
                        class="btn btn-xs btn-danger"
                        on:click|stopPropagation={() => handleStopRTSP(job.id)}
                      >
                        Stop
                      </button>
                    {/if}
                  </div>
                </td>
              </tr>
              {#if job.status === "failed" && job.error_message}
                <tr class="error-row">
                  <td colspan="11">
                    <div class="error-box-inline">
                      <strong>Error:</strong>
                      {job.error_message}
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <!-- Pagination -->
    {#if totalPages > 1}
      <div class="pagination">
        <button
          class="btn btn-sm"
          disabled={currentPage === 1}
          on:click={() => goToPage(currentPage - 1)}
        >
          Previous
        </button>

        <div class="page-numbers">
          {#if currentPage > 2}
            <button class="btn btn-sm" on:click={() => goToPage(1)}>1</button>
            {#if currentPage > 3}
              <span class="page-ellipsis">...</span>
            {/if}
          {/if}

          {#if currentPage > 1}
            <button
              class="btn btn-sm"
              on:click={() => goToPage(currentPage - 1)}
            >
              {currentPage - 1}
            </button>
          {/if}

          <button class="btn btn-sm btn-primary" disabled>
            {currentPage}
          </button>

          {#if currentPage < totalPages}
            <button
              class="btn btn-sm"
              on:click={() => goToPage(currentPage + 1)}
            >
              {currentPage + 1}
            </button>
          {/if}

          {#if currentPage < totalPages - 1}
            {#if currentPage < totalPages - 2}
              <span class="page-ellipsis">...</span>
            {/if}
            <button class="btn btn-sm" on:click={() => goToPage(totalPages)}>
              {totalPages}
            </button>
          {/if}
        </div>

        <button
          class="btn btn-sm"
          disabled={currentPage === totalPages}
          on:click={() => goToPage(currentPage + 1)}
        >
          Next
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .page-container {
    padding: var(--spacing-md);
    width: 100%;
    max-width: 100%;
  }

  @media (min-width: 768px) {
    .page-container {
      padding: var(--spacing-lg);
    }
  }

  @media (min-width: 1920px) {
    .page-container {
      padding: var(--spacing-xl) var(--spacing-xxl);
    }
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xl);
    gap: var(--spacing-md);
  }

  .page-title {
    font-size: var(--font-size-3xl);
    color: var(--color-navy);
    margin: 0;
  }

  .btn-icon {
    margin-right: var(--spacing-xs);
  }

  .page-subtitle {
    color: var(--color-text-secondary);
    margin-top: var(--spacing-xs);
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
      grid-template-columns: repeat(4, 1fr);
    }
  }

  @media (min-width: 1400px) {
    .stats-grid {
      grid-template-columns: repeat(6, 1fr);
    }
  }

  .mode-grid {
    display: none;
    grid-template-columns: repeat(2, 1fr);
  }

  @media (min-width: 768px) {
    .mode-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (min-width: 1024px) {
    .mode-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .filters-section {
    background: var(--color-white);
    padding: var(--spacing-lg);
    border-radius: 8px;
    margin-bottom: var(--spacing-lg);
    box-shadow: var(--shadow-sm);
  }

  .search-bar {
    margin-bottom: var(--spacing-md);
  }

  .search-input {
    width: 100%;
    padding: var(--spacing-md);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: var(--font-size-base);
  }

  .filter-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-sm);
  }

  @media (min-width: 640px) {
    .filter-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-md);
    }
  }

  @media (min-width: 1024px) {
    .filter-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1440px) {
    .filter-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  @media (min-width: 1920px) {
    .filter-grid {
      grid-template-columns: repeat(5, 1fr);
    }
  }

  .filter-select,
  .filter-input {
    padding: var(--spacing-sm) var(--spacing-md);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: var(--font-size-sm);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-md);
  }

  .job-count {
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
  }

  .filter-badge {
    background: var(--color-accent);
    color: var(--color-white);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: var(--font-size-xs);
    margin-left: var(--spacing-xs);
  }

  .card-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  @media (min-width: 768px) {
    .card-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1440px) {
    .card-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 2200px) {
    .card-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .job-card {
    background: var(--color-bg-card);
    border-radius: 8px;
    padding: var(--spacing-md);
    box-shadow: var(--shadow-md);
    cursor: pointer;
    transition:
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
    overflow: hidden;
    min-width: 0;
    border: 2px solid transparent;
  }

  .job-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-sm);
    padding-bottom: var(--spacing-sm);
    border-bottom: 1px solid var(--color-border);
  }

  .card-title-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .job-id {
    font-weight: 600;
    color: var(--color-navy);
    font-size: var(--font-size-base);
  }

  .card-body {
    margin-bottom: var(--spacing-sm);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: var(--font-size-sm);
    min-width: 0;
    gap: var(--spacing-sm);
  }

  .label {
    color: var(--color-text-secondary);
    font-weight: 500;
    flex-shrink: 0;
  }

  .value {
    color: var(--color-navy);
    min-width: 0;
    flex-shrink: 1;
  }

  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .error-box {
    background: #fee;
    border: 1px solid #f88;
    border-radius: 6px;
    padding: var(--spacing-sm);
    margin: var(--spacing-sm) 0;
    color: #c00;
    font-size: var(--font-size-sm);
  }

  .error-box-inline {
    background: #fee;
    border: 1px solid #f88;
    border-radius: 6px;
    padding: var(--spacing-sm) var(--spacing-md);
    color: #c00;
    font-size: var(--font-size-sm);
  }

  .progress-section {
    margin: var(--spacing-sm) 0;
  }

  .progress-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin-bottom: 4px;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: var(--color-bg-light1);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #2196f3, #64b5f6);
    transition: width 0.3s ease;
  }

  .frames-badge {
    background: var(--color-bg-light1);
    padding: var(--spacing-sm);
    border-radius: 6px;
    font-size: var(--font-size-sm);
    color: var(--color-navy);
    text-align: center;
    margin: var(--spacing-sm) 0;
  }

  .summary-section {
    background: var(--color-bg-light1);
    padding: var(--spacing-sm);
    border-radius: 6px;
    margin: var(--spacing-sm) 0;
  }

  .summary-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: var(--font-size-sm);
  }

  .summary-item:last-child {
    margin-bottom: 0;
  }

  .summary-label {
    color: var(--color-text-secondary);
  }

  .summary-value {
    color: var(--color-navy);
    font-weight: 600;
  }

  .card-footer {
    display: flex;
    gap: var(--spacing-sm);
    padding-top: var(--spacing-sm);
    border-top: 1px solid var(--color-border);
  }

  .table-container {
    background: var(--color-white);
    border-radius: 8px;
    box-shadow: var(--shadow-md);
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table thead {
    background: var(--color-navy);
    color: var(--color-white);
  }

  .data-table th {
    padding: var(--spacing-md);
    text-align: left;
    font-weight: 600;
    font-size: var(--font-size-sm);
  }

  .data-table th.sortable {
    cursor: pointer;
    user-select: none;
    transition: all var(--transition-fast);
    position: relative;
  }

  .data-table th.sortable:hover {
    background: rgba(255, 255, 255, 0.15);
  }

  .data-table th.sortable.active {
    background: rgba(255, 255, 255, 0.2);
    font-weight: 700;
  }

  .data-table th.sortable:active {
    background: rgba(255, 255, 255, 0.25);
  }

  .data-table th .sort-icon {
    display: inline-block;
    margin-left: 0.25rem;
    font-size: 0.75rem;
    opacity: 0.9;
  }

  .data-table td {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
    font-size: var(--font-size-sm);
  }

  .clickable-row {
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .clickable-row:hover {
    background: var(--color-bg-light1);
  }

  .error-row {
    background: #fffbf0;
  }

  .error-row td {
    padding: var(--spacing-sm) var(--spacing-md);
  }

  .action-buttons {
    display: flex;
    gap: var(--spacing-xs);
  }

  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-xl);
  }

  .page-numbers {
    display: flex;
    gap: var(--spacing-xs);
  }

  .page-ellipsis {
    padding: var(--spacing-sm);
    color: var(--color-text-secondary);
  }
</style>
