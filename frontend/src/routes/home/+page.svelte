<script lang="ts">
  import { link } from "svelte-spa-router";
  import { onMount, onDestroy } from "svelte";
  import { datasetsAPI } from "../../lib/api/datasets";
  import { projectsAPI } from "../../lib/api/projects";
  import { trainingAPI } from "../../lib/api/training";
  import { modelsAPI } from "../../lib/api/models";
  import { InferenceAPI } from "../../lib/api/inference";

  import { systemAPI } from "../../lib/api/system";
  import { campaignsAPI } from "../../lib/api/campaigns";
  import { workflowsAPI } from "../../lib/api/workflows";
  import {
    authStore,
    canAccessDataManagement,
  } from "../../lib/stores/authStore";
  import StatCard from "../../lib/components/shared/StatCard.svelte";
  import type { Dataset, Project, TrainingJob, Model } from "@/lib/types";

  // State
  let recentDatasets: Dataset[] = [];
  let recentProjects: Project[] = [];
  let recentTraining: TrainingJob[] = [];
  let recentCampaigns: any[] = [];
  let loading = true;

  // Statistics
  let stats = {
    totalDatasets: 0,
    totalProjects: 0,
    totalModels: 0,
    totalDetections: 0,
    activeTrainingJobs: 0,
    activeDetectionJobs: 0,
    activeCampaigns: 0,
    activeWorkflows: 0,
  };

  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let isTabVisible = true;

  // Reactive user access
  $: user = $authStore.user;
  $: isDataManager = $canAccessDataManagement;

  async function loadStats(silent = false) {
    if (!silent) loading = true;

    try {
      const [
        datasets,
        projects,
        models,
        predictionStats,
        systemStatus,
        campaigns,
        workflows,
      ] = await Promise.all([
        datasetsAPI.list(0, 100),
        projectsAPI.list(0, 100),
        modelsAPI.list(0, 100),
        InferenceAPI.getStats(),
        systemAPI.status(),
        campaignsAPI.listCampaigns({ limit: 100 }),
        workflowsAPI.list(),
      ]);

      // Update statistics
      stats.totalDatasets = datasets.length;
      stats.totalProjects = projects.length;
      stats.totalModels = models.length;
      stats.totalDetections = predictionStats.total_predictions || 0;
      stats.activeTrainingJobs = systemStatus.active_training_jobs || 0;
      stats.activeDetectionJobs = systemStatus.active_detection_jobs || 0;
      stats.activeCampaigns = campaigns.filter(
        (c: any) => c.status === "active",
      ).length;
      stats.activeWorkflows = workflows.filter((w: any) => w.is_active).length;

      // Update recent items (3-4 items each)
      recentDatasets = datasets.slice(0, 3);
      recentProjects = projects.slice(0, 3);
      recentCampaigns = campaigns.slice(0, 3);

      // Get recent training jobs
      const trainingJobs = await trainingAPI.list(undefined, 0, 100);
      recentTraining = trainingJobs.slice(0, 3);
    } catch (error) {
      console.error("Failed to load dashboard data:", error);
    } finally {
      if (!silent) loading = false;
    }
  }

  function startPolling() {
    if (pollInterval) return;

    pollInterval = setInterval(() => {
      // Only poll if tab is visible
      if (isTabVisible) {
        loadStats(true); // Silent reload to avoid loading spinner
      }
    }, 30000); // Refresh every 30 seconds
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function handleVisibilityChange() {
    isTabVisible = document.visibilityState === "visible";

    // Refresh data when tab becomes visible again
    if (isTabVisible && pollInterval) {
      loadStats(true);
    }
  }

  onMount(async () => {
    await loadStats();
    startPolling();

    // Listen for visibility changes
    document.addEventListener("visibilitychange", handleVisibilityChange);
  });

  onDestroy(() => {
    stopPolling();
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  });
</script>

<div class="home-page">
  <div class="hero">
    <h1 class="title">Welcome to ATVISION</h1>
    <p class="subtitle">Accelerate Your Real-time Vision Intelligence</p>
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading dashboard...</p>
    </div>
  {:else}
    <!-- Statistics Overview -->
    <div class="stats-section">
      <h2>System Overview</h2>
      <div class="stats-grid">
        {#if isDataManager}
          <StatCard
            icon="📁"
            value={stats.totalDatasets}
            label="Total Datasets"
            animate={true}
          />
          <StatCard
            icon="📊"
            value={stats.totalProjects}
            label="Total Projects"
            animate={true}
          />
          <StatCard
            icon="🤖"
            value={stats.totalModels}
            label="Total Models"
            animate={true}
          />
        {/if}
        <StatCard
          icon="🎯"
          value={stats.totalDetections}
          label="Total Predictions"
          animate={true}
        />
        <StatCard
          icon="🚀"
          value={stats.activeTrainingJobs}
          label="Active Training"
          animate={true}
        />
        <StatCard
          icon="🔄"
          value={stats.activeDetectionJobs}
          label="Active Detections"
          animate={true}
        />
        <StatCard
          icon="📦"
          value={stats.activeCampaigns}
          label="Active Campaigns"
          animate={true}
        />
        {#if isDataManager}
          <StatCard
            icon="⚙️"
            value={stats.activeWorkflows}
            label="Active Workflows"
            animate={true}
          />
        {/if}
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions-section">
      <h2>Quick Actions</h2>
      <div class="actions-grid">
        {#if isDataManager}
          <a href="/datasets" use:link class="action-card">
            <div class="card-icon">📁</div>
            <h3>Upload Dataset</h3>
            <p>Upload your YOLO format dataset to begin training</p>
          </a>

          <a href="/projects" use:link class="action-card">
            <div class="card-icon">📊</div>
            <h3>Create Project</h3>
            <p>Link your dataset and configure training parameters</p>
          </a>

          <a href="/training" use:link class="action-card">
            <div class="card-icon">🚀</div>
            <h3>Train Model</h3>
            <p>Start training your custom YOLO detection model</p>
          </a>

          <a href="/workflows" use:link class="action-card">
            <div class="card-icon">🔄</div>
            <h3>Create Workflow</h3>
            <p>Build automated detection pipelines</p>
          </a>
        {/if}

        <a
          href="/predictions/capture?useNewComponents=true"
          use:link
          class="action-card"
        >
          <div class="card-icon">🎯</div>
          <h3>Run Prediction</h3>
          <p>Test your trained models on images and videos</p>
        </a>

        <a href="/campaigns" use:link class="action-card">
          <div class="card-icon">📦</div>
          <h3>New Campaign</h3>
          <p>Create Campaign with custom forms</p>
        </a>

        <a href="/files" use:link class="action-card">
          <div class="card-icon">📂</div>
          <h3>Manage Files</h3>
          <p>Organize and manage your uploaded files</p>
        </a>

        <a href="/settings" use:link class="action-card">
          <div class="card-icon">⚙️</div>
          <h3>{isDataManager ? "API Keys" : "Settings"}</h3>
          <p>
            {isDataManager
              ? "Manage API keys for authentication"
              : "Configure your preferences"}
          </p>
        </a>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="recent-activity-section">
      <h2>Recent Activity</h2>
      <div class="recent-grid">
        {#if isDataManager}
          <div class="recent-column">
            <div class="section-header">
              <h3>Recent Datasets</h3>
              <a href="/datasets" use:link class="view-all">View All →</a>
            </div>
            {#if recentDatasets.length > 0}
              <div class="recent-list">
                {#each recentDatasets as dataset}
                  <a
                    href="/datasets/{dataset.id}"
                    use:link
                    class="recent-item card"
                  >
                    <strong>{dataset.name}</strong>
                    <span class="text-muted">{dataset.images_count} images</span
                    >
                  </a>
                {/each}
              </div>
            {:else}
              <p class="text-muted">
                No datasets yet. <a href="/datasets" use:link>Create one</a>
              </p>
            {/if}
          </div>

          <div class="recent-column">
            <div class="section-header">
              <h3>Recent Projects</h3>
              <a href="/projects" use:link class="view-all">View All →</a>
            </div>
            {#if recentProjects.length > 0}
              <div class="recent-list">
                {#each recentProjects as project}
                  <a
                    href="/projects/{project.id}"
                    use:link
                    class="recent-item card"
                  >
                    <strong>{project.name}</strong>
                    <span class="badge badge-{project.status}"
                      >{project.status}</span
                    >
                  </a>
                {/each}
              </div>
            {:else}
              <p class="text-muted">
                No projects yet. <a href="/projects" use:link>Create one</a>
              </p>
            {/if}
          </div>

          <div class="recent-column">
            <div class="section-header">
              <h3>Recent Training</h3>
              <a href="/training" use:link class="view-all">View All →</a>
            </div>
            {#if recentTraining.length > 0}
              <div class="recent-list">
                {#each recentTraining as job}
                  <a
                    href="/training/{job.id}"
                    use:link
                    class="recent-item card"
                  >
                    <div class="job-info">
                      <strong
                        >Epoch {job.current_epoch}/{job.total_epochs}</strong
                      >
                      <span class="badge badge-{job.status}">{job.status}</span>
                    </div>
                    {#if job.status === "running" && job.progress !== undefined}
                      <div class="progress-bar">
                        <div
                          class="progress-fill"
                          style="width: {job.progress}%"
                        ></div>
                      </div>
                    {/if}
                  </a>
                {/each}
              </div>
            {:else}
              <p class="text-muted">
                No training jobs yet. <a href="/training" use:link>Start one</a>
              </p>
            {/if}
          </div>
        {/if}

        <div class="recent-column">
          <div class="section-header">
            <h3>Recent Campaigns</h3>
            <a href="/campaigns" use:link class="view-all">View All →</a>
          </div>
          {#if recentCampaigns.length > 0}
            <div class="recent-list">
              {#each recentCampaigns as campaign}
                <a
                  href="/campaigns/{campaign.id}"
                  use:link
                  class="recent-item card"
                >
                  <strong>Campaign #{campaign.id}</strong>
                  <span class="badge badge-{campaign.status}"
                    >{campaign.status}</span
                  >
                </a>
              {/each}
            </div>
          {:else}
            <p class="text-muted">
              No sessions yet. <a href="/sessions" use:link>Create one</a>
            </p>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .home-page {
    width: 100%;
    padding: 0;
  }

  .hero {
    text-align: center;
    padding: var(--spacing-xl) var(--spacing-lg);
    margin-bottom: var(--spacing-xl);
    background: linear-gradient(135deg, var(--color-navy) 0%, #2a4158 100%);
    color: white;
    border-radius: var(--radius-lg);
  }

  .title {
    font-size: var(--font-size-3xl);
    margin-bottom: var(--spacing-sm);
  }

  .subtitle {
    font-size: var(--font-size-lg);
    opacity: 0.9;
  }

  /* Loading State */
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xxl);
    gap: var(--spacing-md);
  }

  .spinner {
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-left-color: var(--color-accent);
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Statistics Section */
  .stats-section {
    margin-bottom: var(--spacing-xl);
  }

  .stats-section h2 {
    margin-bottom: var(--spacing-lg);
    color: var(--color-navy);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-lg);
  }

  /* Quick Actions Section */
  .quick-actions-section {
    margin-bottom: var(--spacing-xl);
  }

  .quick-actions-section h2 {
    margin-bottom: var(--spacing-lg);
    color: var(--color-navy);
  }

  .actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: var(--spacing-lg);
  }

  :global(.action-card) {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-xl);
    text-align: center;
    text-decoration: none;
    color: var(--color-navy);
    transition: all var(--transition-base);
    border: 2px solid transparent;
    box-shadow: var(--shadow-sm);
  }

  :global(.action-card:hover) {
    transform: translateY(-4px);
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }

  .card-icon {
    font-size: 48px;
    margin-bottom: var(--spacing-md);
  }

  :global(.action-card h3) {
    margin-bottom: var(--spacing-sm);
    color: var(--color-navy);
  }

  :global(.action-card p) {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
  }

  /* Recent Activity Section */
  .recent-activity-section {
    margin-top: var(--spacing-xl);
  }

  .recent-activity-section h2 {
    margin-bottom: var(--spacing-lg);
    color: var(--color-navy);
  }

  .recent-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--spacing-lg);
  }

  .recent-column {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-sm);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-md);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-bg-light1);
  }

  .section-header h3 {
    margin: 0;
    color: var(--color-navy);
    font-size: var(--font-size-lg);
  }

  .view-all {
    color: var(--color-accent);
    text-decoration: none;
    font-size: var(--font-size-sm);
    font-weight: 600;
    transition: color var(--transition-fast);
  }

  .view-all:hover {
    color: var(--color-navy);
  }

  .recent-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  :global(.recent-item) {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-md);
    text-decoration: none;
    color: var(--color-navy);
    transition: background-color var(--transition-fast);
    border-radius: var(--radius-sm);
  }

  :global(.recent-item:hover) {
    background-color: var(--color-bg-light1);
  }

  .job-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
    flex: 1;
  }

  .progress-bar {
    width: 100%;
    height: 4px;
    background-color: var(--color-bg-light1);
    border-radius: 2px;
    overflow: hidden;
    margin-top: var(--spacing-xs);
  }

  .progress-fill {
    height: 100%;
    background-color: var(--color-accent);
    transition: width 0.3s ease;
  }

  .badge {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .badge-created {
    background-color: #e0e7ff;
    color: #4338ca;
  }

  .badge-training {
    background-color: #fef3c7;
    color: #b45309;
  }

  .badge-running {
    background-color: #fef3c7;
    color: #b45309;
  }

  .badge-trained {
    background-color: #d1fae5;
    color: #065f46;
  }

  .badge-completed {
    background-color: #d1fae5;
    color: #065f46;
  }

  .badge-failed {
    background-color: #fee2e2;
    color: #991b1b;
  }

  .badge-active {
    background-color: #d1fae5;
    color: #065f46;
  }

  .badge-ended {
    background-color: #e5e7eb;
    color: #4b5563;
  }

  .text-muted {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
  }

  /* Responsive Design */
  @media (max-width: 1400px) {
    .stats-grid {
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
  }

  @media (max-width: 1024px) {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .actions-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .recent-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 768px) {
    .hero {
      padding: var(--spacing-lg) var(--spacing-md);
    }

    .title {
      font-size: var(--font-size-2xl);
    }

    .subtitle {
      font-size: var(--font-size-base);
    }

    .stats-grid {
      grid-template-columns: 1fr;
      gap: var(--spacing-sm);
    }

    .actions-grid {
      grid-template-columns: 1fr;
      gap: var(--spacing-md);
    }

    .recent-grid {
      grid-template-columns: 1fr;
      gap: var(--spacing-md);
    }

    :global(.action-card) {
      padding: var(--spacing-lg);
    }

    .card-icon {
      font-size: 36px;
    }
  }

  @media (max-width: 480px) {
    .home-page {
      padding: 0;
    }

    .hero {
      border-radius: 0;
    }

    .recent-column {
      padding: var(--spacing-md);
    }

    :global(.recent-item) {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--spacing-xs);
    }

    .section-header {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--spacing-xs);
    }
  }
</style>
