<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { trainingAPI } from "../../lib/api/training";
  import { uiStore } from "../../lib/stores/uiStore";
  import StatCard from "../../lib/components/shared/StatCard.svelte";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import EmptyState from "../../lib/components/shared/EmptyState.svelte";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import type { TrainingJob } from "@/lib/types";

  let jobs: TrainingJob[] = [];
  let loading = true;
  let error = "";
  let searchTerm = "";
  let view: "card" | "list" = "card";
  let selectedStatFilter: string | null = null;
  let statsAnimated = false;

  // Statistics calculations
  $: totalJobs = jobs.length;
  $: runningJobs = jobs.filter((j) => j.status === "running").length;
  $: completedJobs = jobs.filter((j) => j.status === "completed").length;
  $: failedJobs = jobs.filter((j) => j.status === "failed").length;
  $: avgDuration =
    jobs.filter((j) => j.started_at && j.completed_at).length > 0
      ? jobs
          .filter((j) => j.started_at && j.completed_at)
          .reduce((sum, j) => {
            const duration =
              new Date(j.completed_at!).getTime() -
              new Date(j.started_at!).getTime();
            return sum + duration;
          }, 0) /
        jobs.filter((j) => j.started_at && j.completed_at).length /
        1000 /
        60 // minutes
      : 0;
  $: successRate = totalJobs > 0 ? (completedJobs / totalJobs) * 100 : 0;

  // Filtering logic
  $: filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      searchTerm === "" ||
      `Training Job #${job.id}`
        .toLowerCase()
        .includes(searchTerm.toLowerCase()) ||
      `Project ID: ${job.project_id}`
        .toLowerCase()
        .includes(searchTerm.toLowerCase());

    const matchesStat =
      selectedStatFilter === null ||
      (selectedStatFilter === "running" && job.status === "running") ||
      (selectedStatFilter === "completed" && job.status === "completed") ||
      (selectedStatFilter === "failed" && job.status === "failed");

    return matchesSearch && matchesStat;
  });

  // Auto-reset filter when search changes
  $: if (searchTerm) {
    selectedStatFilter = null;
  }

  onMount(async () => {
    await loadTrainingJobs();
    setTimeout(() => (statsAnimated = true), 100);
  });

  async function loadTrainingJobs() {
    loading = true;
    try {
      jobs = await trainingAPI.list();
    } catch (err: any) {
      error = err.response?.data?.detail || "Failed to load training jobs";
      uiStore.showToast(error, "error");
      console.error("Error loading training jobs:", err);
    } finally {
      loading = false;
    }
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

  // Status class mapping for badges
  function getStatusClass(status: string): string {
    const statusMap: Record<string, string> = {
      pending: "badge-pending",
      running: "badge-running",
      completed: "badge-completed",
      failed: "badge-failed",
    };
    return statusMap[status] || "badge-neutral";
  }

  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleString();
  }

  function formatDuration(minutes: number): string {
    if (minutes < 60) return `${Math.round(minutes)}m`;
    return `${Math.round(minutes / 60)}h ${Math.round(minutes % 60)}m`;
  }

  function viewJob(jobId: number, projectId: number) {
    navigate(`/projects/${projectId}`);
  }
</script>

<div class="page">
  <div class="page-header">
    <div class="header-left">
      <h1>Training Jobs</h1>
      <p class="subtitle">Manage and monitor your model training</p>
    </div>
    <div class="header-actions">
      <button
        class="btn btn-primary"
        on:click={() => navigate("/training/new")}
      >
        ➕ New Training
      </button>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner message="Loading training jobs..." />
  {:else}
    <!-- Statistics Grid -->
    {#if jobs.length > 0}
      <div class="stats-grid">
        <StatCard
          icon="📊"
          value={totalJobs}
          label="Total Jobs"
          animate={statsAnimated}
          ariaLabel="Total training jobs"
        />
        <StatCard
          icon="🔄"
          value={runningJobs}
          label="Running"
          isClickable={true}
          filterType="running"
          isActive={selectedStatFilter === "running"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="✅"
          value={completedJobs}
          label="Completed"
          isClickable={true}
          filterType="completed"
          isActive={selectedStatFilter === "completed"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="❌"
          value={failedJobs}
          label="Failed"
          isClickable={true}
          filterType="failed"
          isActive={selectedStatFilter === "failed"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="⏱️"
          value={avgDuration > 0 ? formatDuration(avgDuration) : "0m"}
          label="Avg Duration"
          animate={statsAnimated}
          ariaLabel="Average training duration"
        />
        <StatCard
          icon="🎯"
          value={successRate > 0 ? `${successRate.toFixed(0)}%` : "0%"}
          label="Success Rate"
          animate={statsAnimated}
          ariaLabel="Training success rate"
        />
      </div>
    {/if}

    <!-- Controls -->
    {#if jobs.length > 0}
      <div class="controls">
        <input
          type="text"
          class="search-input"
          placeholder="🔍 Search training jobs..."
          bind:value={searchTerm}
        />
        <ViewToggle {view} onChange={handleViewChange} />
      </div>
    {/if}

    {#if filteredJobs.length === 0}
      <EmptyState
        icon={searchTerm || selectedStatFilter ? "🔍" : "🚀"}
        title={searchTerm || selectedStatFilter
          ? "No Training Jobs Found"
          : "Start Your First Training Session"}
        message={searchTerm || selectedStatFilter
          ? "No training jobs match your current filters. Try adjusting your search criteria or clearing filters to see all jobs."
          : "Train your first YOLO model to detect objects in images and videos. Create a project and start training to see your jobs here."}
        actionLabel={searchTerm || selectedStatFilter
          ? "Clear Filters"
          : "Start Training"}
        onAction={searchTerm || selectedStatFilter
          ? () => {
              searchTerm = "";
              selectedStatFilter = null;
            }
          : () => navigate("/training/new")}
      />
    {:else if view === "card"}
      <div class="jobs-grid">
        {#each filteredJobs as job}
          <div
            class="job-card"
            on:click={() => viewJob(job.id, job.project_id)}
            on:keydown={(e) =>
              e.key === "Enter" && viewJob(job.id, job.project_id)}
            role="button"
            tabindex="0"
          >
            <div class="job-header">
              <div class="job-info">
                <h3>Training Job #{job.id}</h3>
                <span class="job-project">Project ID: {job.project_id}</span>
              </div>
              <span class="status-badge {getStatusClass(job.status)}">
                {job.status.toUpperCase()}
              </span>
            </div>

            <div class="job-body">
              {#if job.status === "running" || job.status === "completed"}
                <div class="progress-section">
                  <div class="progress-info">
                    <span>Progress</span>
                    <span>{Math.round(job.progress)}%</span>
                  </div>
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      style="width: {job.progress}%"
                    ></div>
                  </div>
                  <div class="epoch-info">
                    Epoch {job.current_epoch} / {job.total_epochs}
                  </div>
                </div>
              {/if}

              {#if job.error_message}
                <div class="error-message">
                  <span class="error-icon">⚠️</span>
                  {job.error_message}
                </div>
              {/if}

              {#if job.metrics_json && Object.keys(job.metrics_json).length > 0}
                <div class="metrics-section">
                  <div class="metrics-header">
                    <span class="metrics-title">📊 Training Metrics</span>
                  </div>
                  <div class="metrics-grid">
                    <!-- Classification Metrics -->
                    {#if job.metrics_json["top1_accuracy"] !== undefined || job.metrics_json["metrics/accuracy_top1"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">Top-1 Acc</span>
                        <span class="metric-value"
                          >{(
                            (job.metrics_json["top1_accuracy"] ||
                              job.metrics_json["metrics/accuracy_top1"]) * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                    {#if job.metrics_json["top5_accuracy"] !== undefined || job.metrics_json["metrics/accuracy_top5"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">Top-5 Acc</span>
                        <span class="metric-value"
                          >{(
                            (job.metrics_json["top5_accuracy"] ||
                              job.metrics_json["metrics/accuracy_top5"]) * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                    <!-- Detection Metrics -->
                    {#if job.metrics_json["metrics/mAP50-95(B)"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">mAP50-95</span>
                        <span class="metric-value"
                          >{(
                            job.metrics_json["metrics/mAP50-95(B)"] * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                    {#if job.metrics_json["metrics/precision(B)"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">Precision</span>
                        <span class="metric-value"
                          >{(
                            job.metrics_json["metrics/precision(B)"] * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                    {#if job.metrics_json["metrics/recall(B)"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">Recall</span>
                        <span class="metric-value"
                          >{(
                            job.metrics_json["metrics/recall(B)"] * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                    {#if job.metrics_json["metrics/mAP50(B)"] !== undefined}
                      <div class="metric">
                        <span class="metric-label">mAP50</span>
                        <span class="metric-value"
                          >{(
                            job.metrics_json["metrics/mAP50(B)"] * 100
                          ).toFixed(2)}%</span
                        >
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>

            <div class="job-footer">
              <div class="time-info">
                <span class="time-label">Started:</span>
                <span class="time-value">
                  {job.started_at ? formatDate(job.started_at) : "Not started"}
                </span>
              </div>
              {#if job.completed_at}
                <div class="time-info">
                  <span class="time-label">Completed:</span>
                  <span class="time-value">{formatDate(job.completed_at)}</span>
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <!-- Table View -->
      <div class="jobs-table">
        <table>
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Epochs</th>
              <th>Metric</th>
              <th>Started</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredJobs as job (job.id)}
              <tr
                on:click={() => viewJob(job.id, job.project_id)}
                class="clickable-row"
              >
                <td>
                  <div class="table-name">
                    <strong>Job #{job.id}</strong>
                    <span class="table-desc">Project {job.project_id}</span>
                  </div>
                </td>
                <td>
                  <span class="status-badge {getStatusClass(job.status)}">
                    {job.status}
                  </span>
                </td>
                <td>
                  {#if job.status === "running" || job.status === "completed"}
                    <div class="table-progress">
                      <div class="progress-bar-small">
                        <div
                          class="progress-fill"
                          style="width: {job.progress}%"
                        ></div>
                      </div>
                      <span class="progress-text"
                        >{Math.round(job.progress)}%</span
                      >
                    </div>
                  {:else}
                    -
                  {/if}
                </td>
                <td>
                  {#if job.current_epoch && job.total_epochs}
                    {job.current_epoch}/{job.total_epochs}
                  {:else}
                    -
                  {/if}
                </td>
                <td>
                  {job.metrics_json?.["metrics/mAP50-95(B)"] !== undefined
                    ? (job.metrics_json["metrics/mAP50-95(B)"] * 100).toFixed(
                        2,
                      ) + "%"
                    : job.metrics_json?.["top1_accuracy"] !== undefined
                      ? (job.metrics_json["top1_accuracy"] * 100).toFixed(2) +
                        "%"
                      : job.metrics_json?.["metrics/accuracy_top1"] !==
                          undefined
                        ? (
                            job.metrics_json["metrics/accuracy_top1"] * 100
                          ).toFixed(2) + "%"
                        : "-"}
                </td>
                <td>
                  {job.started_at
                    ? new Date(job.started_at).toLocaleDateString()
                    : "-"}
                </td>
                <td>
                  {#if job.started_at && job.completed_at}
                    {formatDuration(
                      (new Date(job.completed_at).getTime() -
                        new Date(job.started_at).getTime()) /
                        1000 /
                        60,
                    )}
                  {:else if job.started_at}
                    In progress
                  {:else}
                    -
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>

<style>
  .page {
    padding: var(--spacing-md);
    width: 100%;
    max-width: 100%;
  }

  @media (min-width: 768px) {
    .page {
      padding: var(--spacing-lg);
    }
  }

  @media (min-width: 1920px) {
    .page {
      padding: var(--spacing-xl) var(--spacing-xxl);
    }
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-xl);
  }

  .header-left h1 {
    margin: 0 0 var(--spacing-xs) 0;
    color: var(--color-navy);
  }

  .subtitle {
    color: var(--color-text-light);
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: var(--spacing-md);
  }

  /* Statistics Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-xl);
  }

  @media (min-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1200px) {
    .stats-grid {
      grid-template-columns: repeat(6, 1fr);
    }
  }

  .stats-grid :global(.stat-card:nth-child(1)) {
    animation-delay: 0s;
  }
  .stats-grid :global(.stat-card:nth-child(2)) {
    animation-delay: 0.15s;
  }
  .stats-grid :global(.stat-card:nth-child(3)) {
    animation-delay: 0.3s;
  }
  .stats-grid :global(.stat-card:nth-child(4)) {
    animation-delay: 0.45s;
  }
  .stats-grid :global(.stat-card:nth-child(5)) {
    animation-delay: 0.6s;
  }
  .stats-grid :global(.stat-card:nth-child(6)) {
    animation-delay: 0.75s;
  }

  /* Controls */
  .controls {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
    align-items: stretch;
  }

  @media (min-width: 640px) {
    .controls {
      flex-direction: row;
      align-items: center;
    }
  }

  .search-input {
    flex: 1;
    padding: var(--spacing-md);
    border: 2px solid var(--color-light-grey);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    transition: border-color var(--transition-fast);
  }

  .search-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .jobs-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  @media (min-width: 768px) {
    .jobs-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1200px) {
    .jobs-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1600px) {
    .jobs-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .job-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-sm);
    cursor: pointer;
    transition: all var(--transition-base);
    border: 2px solid transparent;
  }

  .job-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-lg);
    padding-bottom: var(--spacing-md);
    border-bottom: 1px solid var(--color-bg-light2);
  }

  .job-info h3 {
    margin: 0 0 var(--spacing-xs) 0;
    color: var(--color-navy);
    font-size: var(--font-size-lg);
  }

  .job-project {
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .status-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-full);
    color: white;
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .job-body {
    margin-bottom: var(--spacing-lg);
  }

  .progress-section {
    margin-bottom: var(--spacing-md);
  }

  .progress-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: var(--spacing-xs);
    font-size: var(--font-size-sm);
    color: var(--color-text-light);
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background-color: var(--color-bg-light2);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(
      90deg,
      var(--color-accent),
      var(--color-accent-dark)
    );
    border-radius: var(--radius-full);
    transition: width var(--transition-base);
  }

  .epoch-info {
    margin-top: var(--spacing-xs);
    font-size: var(--font-size-sm);
    color: var(--color-text-light);
    text-align: center;
  }

  .error-message {
    background-color: var(--color-danger-alpha-10);
    border-left: 4px solid var(--color-danger);
    padding: var(--spacing-sm) var(--spacing-md);
    border-radius: var(--radius-md);
    color: var(--color-danger-dark);
    font-size: var(--font-size-sm);
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .error-icon {
    font-size: var(--font-size-lg);
  }

  .metrics-section {
    margin-top: var(--spacing-md);
  }

  .metrics-header {
    margin-bottom: var(--spacing-xs);
  }

  .metrics-title {
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--color-navy);
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-md);
    border: 2px solid var(--color-border);
  }

  .metric {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .metric-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-light);
    margin-bottom: var(--spacing-xs);
  }

  .metric-value {
    font-size: var(--font-size-lg);
    font-weight: 600;
    color: var(--color-navy);
  }

  .job-footer {
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-bg-light2);
  }

  .time-info {
    display: flex;
    justify-content: space-between;
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-xs);
  }

  .time-label {
    color: var(--color-text-light);
  }

  .time-value {
    color: var(--color-navy);
    font-weight: 500;
  }

  /* Button styles */
  .btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
  }

  .btn-primary {
    background-color: var(--color-accent);
    color: white;
  }

  .btn-primary:hover {
    background-color: var(--color-accent-dark);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  .btn-primary:active {
    transform: translateY(0);
  }

  /* Table View */
  .jobs-table {
    background: var(--color-white);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background-color: var(--color-navy);
    color: var(--color-white);
  }

  th {
    text-align: left;
    padding: var(--spacing-md);
    font-weight: 600;
    font-size: var(--font-size-sm);
  }

  tbody tr {
    border-bottom: 1px solid var(--color-light-grey);
  }

  tbody tr:last-child {
    border-bottom: none;
  }

  .clickable-row {
    cursor: pointer;
    transition: background-color var(--transition-fast);
  }

  .clickable-row:hover {
    background-color: var(--color-accent-alpha-5);
  }

  td {
    padding: var(--spacing-md);
    font-size: var(--font-size-sm);
  }

  .table-name {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .table-desc {
    font-size: var(--font-size-xs);
    color: var(--color-grey);
  }

  .table-progress {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .progress-bar-small {
    flex: 1;
    height: 8px;
    background-color: var(--color-light-grey);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-text {
    min-width: 40px;
    text-align: right;
    font-size: var(--font-size-xs);
    color: var(--color-grey);
  }

  /* Mobile Responsive */
  @media (max-width: 768px) {
    .stats-grid {
      display: none;
    }

    .page-header {
      flex-direction: column;
      gap: var(--spacing-md);
    }

    .controls {
      flex-direction: column;
    }

    .jobs-grid {
      grid-template-columns: 1fr;
    }

    .jobs-table {
      overflow-x: auto;
    }

    table {
      min-width: 800px;
    }
  }
</style>
