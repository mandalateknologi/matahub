<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { modelsAPI } from "../../lib/api/models";
  import { projectsAPI } from "../../lib/api/projects";
  import StatCard from "../../lib/components/shared/StatCard.svelte";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import EmptyState from "../../lib/components/shared/EmptyState.svelte";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import { uiStore } from "../../lib/stores/uiStore";
  import type { Model } from "@/lib/types";

  let models: Model[] = [];
  let loading = true;
  let basedProjectId: number | null = null;
  let systemProjectIds: Set<number> = new Set();
  let searchTerm = "";
  let view: "card" | "list" = "card";
  let selectedStatFilter: string | null = null;
  let statsAnimated = false;
  let modelTypeFilter: "all" | "trained" | "system" = "trained";

  // Statistics calculations
  $: totalModels = models.length;
  $: readyModels = models.filter((m) => m.status === "ready").length;
  $: trainingModels = models.filter((m) => m.status === "training").length;
  $: validatingModels = models.filter((m) => m.status === "validating").length;
  $: uniqueArchitectures = [...new Set(models.map((m) => m.base_type))].length;
  $: avgMAP =
    models.filter((m) => m.metrics_json?.mAP).length > 0
      ? models
          .filter((m) => m.metrics_json?.mAP)
          .reduce((sum, m) => sum + (m.metrics_json.mAP || 0), 0) /
        models.filter((m) => m.metrics_json?.mAP).length
      : 0;
  $: bestModel =
    models.length > 0
      ? models
          .filter((m) => m.metrics_json?.mAP)
          .sort(
            (a, b) => (b.metrics_json.mAP || 0) - (a.metrics_json.mAP || 0),
          )[0]
      : null;
  $: recentModels = models.filter((m) => {
    const daysSinceCreation =
      (Date.now() - new Date(m.created_at).getTime()) / (1000 * 60 * 60 * 24);
    return daysSinceCreation <= 7;
  }).length;

  // Filtering logic
  $: filteredModels = models.filter((model) => {
    const matchesSearch =
      searchTerm === "" ||
      model.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      model.base_type.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStat =
      selectedStatFilter === null ||
      (selectedStatFilter === "ready" && model.status === "ready") ||
      (selectedStatFilter === "training" && model.status === "training") ||
      (selectedStatFilter === "recent" &&
        (Date.now() - new Date(model.created_at).getTime()) /
          (1000 * 60 * 60 * 24) <=
          7);

    const matchesType =
      modelTypeFilter === "all" ||
      (modelTypeFilter === "trained" &&
        !systemProjectIds.has(model.project_id)) ||
      (modelTypeFilter === "system" && systemProjectIds.has(model.project_id));

    return matchesSearch && matchesStat && matchesType;
  });

  // Auto-reset filter when search changes
  $: if (searchTerm) {
    selectedStatFilter = null;
  }

  // Helper to check if model is from Base Project
  $: isBaseModel = (model: Model) =>
    basedProjectId !== null && model.project_id === basedProjectId;

  // Helper to check if model is from any system project (no dataset)
  $: isSystemProjectModel = (model: Model) =>
    systemProjectIds.has(model.project_id);

  onMount(async () => {
    await loadModels();
    await loadBaseProject();
    setTimeout(() => (statsAnimated = true), 100);
  });

  async function loadModels() {
    try {
      loading = true;
      models = await modelsAPI.list();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to load models", "error");
    } finally {
      loading = false;
    }
  }

  async function loadBaseProject() {
    try {
      const allProjects = await projectsAPI.list();
      const basedProject = allProjects.find(
        (p) => p.is_system && p.name === "Based",
      );
      if (basedProject) {
        basedProjectId = basedProject.id;
      }
      // Track all system project IDs (they don't have datasets)
      systemProjectIds = new Set(
        allProjects.filter((p) => p.is_system).map((p) => p.id),
      );
    } catch (error: any) {
      // Silently fail - badges simply won't show if Base Project not found
      console.warn("Could not load Base Project:", error);
    }
  }

  function handleStatClick(filterType: string) {
    if (selectedStatFilter === filterType) {
      selectedStatFilter = null;
    } else {
      selectedStatFilter = filterType;
    }
  }

  function handleModelClick(modelId: number) {
    navigate(`/models/${modelId}`);
  }

  function handleViewChange(newView: "card" | "list") {
    view = newView;
  }

  function getStatusClass(status: string): string {
    const statusMap: Record<string, string> = {
      ready: "badge-completed",
      training: "badge-running",
      validating: "badge-validating",
      pending: "badge-pending",
      failed: "badge-failed",
    };
    return statusMap[status] || "badge-neutral";
  }

  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString();
  }

  async function handleValidateModel(modelId: number, event: Event) {
    event.stopPropagation();
    try {
      await modelsAPI.validate(modelId);
      uiStore.showToast("Model validation started", "success");
      await loadModels();
    } catch (error: any) {
      // Extract detailed error message from API response
      const errorMsg =
        error.response?.data?.detail ||
        error.message ||
        "Failed to start validation";
      uiStore.showToast(errorMsg, "error");
    }
  }

  function getModelIcon(baseType: string): string {
    // Return emoji based on model size/type
    if (baseType.includes("n")) return "⚡"; // nano - fast
    if (baseType.includes("s")) return "🚀"; // small
    if (baseType.includes("m")) return "🎯"; // medium
    if (baseType.includes("l")) return "🔥"; // large
    if (baseType.includes("x")) return "💪"; // xlarge
    return "🤖"; // default
  }
</script>

<div class="page">
  <div class="page-header">
    <div class="header-content">
      <h1>Models</h1>
      <p class="subtitle">Browse and manage your trained models</p>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner message="Loading models..." />
  {:else}
    <!-- Statistics Grid -->
    {#if models.length > 0}
      <div class="stats-grid">
        <StatCard
          icon="🤖"
          value={totalModels}
          label="Total Models"
          animate={statsAnimated}
          ariaLabel="Total number of models"
        />
        <StatCard
          icon="✅"
          value={readyModels}
          label="Ready"
          breakdown="{trainingModels} training"
          isClickable={true}
          filterType="ready"
          isActive={selectedStatFilter === "ready"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="🔄"
          value={trainingModels}
          label="Training"
          isClickable={true}
          filterType="training"
          isActive={selectedStatFilter === "training"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="🏗️"
          value={uniqueArchitectures}
          label="Architectures"
          animate={statsAnimated}
          ariaLabel="Unique model architectures"
        />
        <StatCard
          icon="🎯"
          value={avgMAP > 0 ? `${(avgMAP * 100).toFixed(1)}%` : "0%"}
          label="Avg mAP"
          breakdown={bestModel
            ? `Best: ${(bestModel.metrics_json.mAP * 100).toFixed(1)}%`
            : ""}
          animate={statsAnimated}
          ariaLabel="Average mean average precision"
        />
        <StatCard
          icon="⭐"
          value={recentModels}
          label="Recent"
          breakdown="Last 7 days"
          isClickable={true}
          filterType="recent"
          isActive={selectedStatFilter === "recent"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
      </div>
    {/if}

    <!-- Controls -->
    {#if models.length > 0}
      <div class="controls">
        <input
          type="text"
          class="search-input"
          placeholder="🔍 Search models..."
          bind:value={searchTerm}
        />
        <div class="filter-buttons">
          <button
            class="filter-btn {modelTypeFilter === 'trained' ? 'active' : ''}"
            on:click={() => (modelTypeFilter = "trained")}
          >
            🎯 Trained
          </button>
          <button
            class="filter-btn {modelTypeFilter === 'system' ? 'active' : ''}"
            on:click={() => (modelTypeFilter = "system")}
          >
            🔒 System
          </button>
          <button
            class="filter-btn {modelTypeFilter === 'all' ? 'active' : ''}"
            on:click={() => (modelTypeFilter = "all")}
          >
            📦 All
          </button>
        </div>
        <ViewToggle {view} onChange={handleViewChange} />
      </div>
    {/if}

    <!-- Models List -->
    {#if filteredModels.length === 0}
      <EmptyState
        icon={searchTerm || selectedStatFilter ? "🔍" : "🤖"}
        title={searchTerm || selectedStatFilter
          ? "No Models Found"
          : "Train Your First Model"}
        message={searchTerm || selectedStatFilter
          ? "No models match your current filters or search. Adjust your criteria or clear filters to view all available models."
          : "Models are created through the training process. Start a training job to generate your first YOLO object detection model. Once trained, your models will appear here."}
        actionLabel={searchTerm || selectedStatFilter
          ? "Clear Filters"
          : "Go to Training"}
        onAction={searchTerm || selectedStatFilter
          ? () => {
              searchTerm = "";
              selectedStatFilter = null;
            }
          : () => navigate("/training")}
      />
    {:else if view === "card"}
      <div class="models-grid">
        {#each filteredModels as model (model.id)}
          <div
            class="model-card"
            on:click={() => handleModelClick(model.id)}
            on:keydown={(e) => e.key === "Enter" && handleModelClick(model.id)}
            role="button"
            tabindex="0"
          >
            <div class="card-header">
              <div class="model-icon">{getModelIcon(model.base_type)}</div>
              <div class="model-title">
                <h3>{model.name}</h3>
                <div class="model-meta">
                  <span class="model-architecture">{model.base_type}</span>
                  <span
                    class="task-type-badge task-type-{model.task_type}"
                    title="Task Type"
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
                </div>
                {#if isBaseModel(model)}
                  <span class="base-badge" title="Base Project Model"
                    >🔒 BASE</span
                  >
                {/if}
              </div>
              <span class="status-badge {getStatusClass(model.status)}">
                {model.status}
              </span>
            </div>

            {#if model.status === "validating"}
              <div class="validation-section">
                <div class="validation-info">
                  <span class="spinner">⏳</span>
                  <span>Validating model on dataset...</span>
                </div>
              </div>
            {:else if model.status === "failed" && model.validation_error}
              <div class="validation-section error">
                <div class="validation-error">
                  <span>❌ Validation Failed:</span>
                  <p>{model.validation_error}</p>
                  {#if !isSystemProjectModel(model)}
                    <button
                      class="btn-validate"
                      on:click={(e) => handleValidateModel(model.id, e)}
                    >
                      🔄 Retry Validation
                    </button>
                  {/if}
                </div>
              </div>
            {:else if model.metrics_json && Object.keys(model.metrics_json).length > 0}
              <div class="metrics-section">
                <div class="metrics-grid">
                  {#if model.task_type === "classify"}
                    <!-- Classification Metrics -->
                    {#if model.metrics_json.top1_accuracy !== undefined || model.metrics_json["metrics/accuracy_top1"] !== undefined}
                      <div class="metric-item">
                        <span class="metric-label">Top-1</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json.top1_accuracy ||
                              model.metrics_json["metrics/accuracy_top1"] ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                    {#if model.metrics_json.top5_accuracy !== undefined || model.metrics_json["metrics/accuracy_top5"] !== undefined}
                      <div class="metric-item">
                        <span class="metric-label">Top-5</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json.top5_accuracy ||
                              model.metrics_json["metrics/accuracy_top5"] ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                    {#if model.metrics_json["train/loss"] !== undefined}
                      <div class="metric-item">
                        <span class="metric-label">Loss</span>
                        <span class="metric-value"
                          >{model.metrics_json["train/loss"].toFixed(3)}</span
                        >
                      </div>
                    {/if}
                  {:else}
                    <!-- Detection/Segmentation Metrics -->
                    {#if model.metrics_json["metrics/mAP50-95(B)"] || model.metrics_json["mAP50-95"] || model.metrics_json.mAP}
                      <div class="metric-item">
                        <span class="metric-label">mAP</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json["metrics/mAP50-95(B)"] ||
                              model.metrics_json["mAP50-95"] ||
                              model.metrics_json.mAP ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                    {#if model.metrics_json["metrics/mAP50(B)"] || model.metrics_json.mAP50}
                      <div class="metric-item">
                        <span class="metric-label">mAP@50</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json["metrics/mAP50(B)"] ||
                              model.metrics_json.mAP50 ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                    {#if model.metrics_json["metrics/precision(B)"] || model.metrics_json.precision}
                      <div class="metric-item">
                        <span class="metric-label">Precision</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json["metrics/precision(B)"] ||
                              model.metrics_json.precision ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                    {#if model.metrics_json["metrics/recall(B)"] || model.metrics_json.recall}
                      <div class="metric-item">
                        <span class="metric-label">Recall</span>
                        <span class="metric-value"
                          >{(
                            (model.metrics_json["metrics/recall(B)"] ||
                              model.metrics_json.recall ||
                              0) * 100
                          ).toFixed(1)}%</span
                        >
                      </div>
                    {/if}
                  {/if}
                </div>
              </div>
            {:else if model.status === "ready" && (!model.metrics_json || Object.keys(model.metrics_json).length === 0)}
              <div class="validation-section">
                <div class="no-metrics-info">
                  <span>📊 No metrics available</span>
                  {#if !isSystemProjectModel(model)}
                    <button
                      class="btn-validate"
                      on:click={(e) => handleValidateModel(model.id, e)}
                    >
                      🔄 Validate Model
                    </button>
                  {:else}
                    <span class="hint-text">System project - no dataset</span>
                  {/if}
                </div>
              </div>
            {/if}

            <div class="card-footer">
              {#if isBaseModel(model)}
                <span class="project-ref base-project" title="Base Project"
                  >🔒 Base Project</span
                >
              {:else}
                <span class="project-ref">Project #{model.project_id}</span>
              {/if}
              <span class="date-text">{formatDate(model.created_at)}</span>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div class="models-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Architecture</th>
              <th>Task Type</th>
              <th>Status</th>
              <th>mAP</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>Project</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredModels as model (model.id)}
              <tr
                on:click={() => handleModelClick(model.id)}
                class="clickable-row"
              >
                <td>
                  <div class="table-name">
                    <strong>{model.name}</strong>
                  </div>
                </td>
                <td>
                  <span class="architecture-badge"
                    >{getModelIcon(model.base_type)} {model.base_type}</span
                  >
                </td>
                <td>
                  <span
                    class="task-type-badge-small task-type-{model.task_type}"
                  >
                    {#if model.task_type === "detect"}
                      🎯 Detect
                    {:else if model.task_type === "classify"}
                      📊 Classify
                    {:else if model.task_type === "segment"}
                      ✂️ Segment
                    {:else}
                      {model.task_type}
                    {/if}
                  </span>
                </td>
                <td>
                  <span class="status-badge {getStatusClass(model.status)}">
                    {model.status}
                  </span>
                </td>
                <td
                  >{model.metrics_json?.mAP
                    ? `${(model.metrics_json.mAP * 100).toFixed(1)}%`
                    : "-"}</td
                >
                <td
                  >{model.metrics_json?.precision
                    ? `${(model.metrics_json.precision * 100).toFixed(1)}%`
                    : "-"}</td
                >
                <td
                  >{model.metrics_json?.recall
                    ? `${(model.metrics_json.recall * 100).toFixed(1)}%`
                    : "-"}</td
                >
                <td>
                  {#if isBaseModel(model)}
                    <span class="base-badge-small" title="Base Project"
                      >🔒 Base</span
                    >
                  {:else}
                    #{model.project_id}
                  {/if}
                </td>
                <td>{formatDate(model.created_at)}</td>
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

  .header-content h1 {
    font-size: var(--font-size-3xl);
    margin-bottom: var(--spacing-xs);
  }

  .subtitle {
    color: var(--color-grey);
    font-size: var(--font-size-base);
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

  .filter-buttons {
    display: flex;
    gap: var(--spacing-xs);
    background: var(--color-bg-secondary);
    padding: 4px;
    border-radius: var(--radius-md);
    border: 2px solid var(--color-border);
  }

  .filter-btn {
    padding: var(--spacing-sm) var(--spacing-md);
    background: transparent;
    border: 2px solid transparent;
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .filter-btn:hover {
    background: var(--color-bg-primary);
    color: var(--color-accent);
  }

  .filter-btn.active {
    background: var(--color-bg-secondary);
    color: var(--color-accent);
    border-color: var(--color-accent);
    box-shadow: 0 2px 8px var(--color-accent-alpha-20);
  }

  /* Card Grid */
  .models-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  @media (min-width: 768px) {
    .models-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1200px) {
    .models-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1600px) {
    .models-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .model-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    border: 2px solid transparent;
  }

  .model-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-md);
    max-width: 315px;
  }

  .model-icon {
    font-size: 2rem;
    flex-shrink: 0;
  }

  .model-title {
    flex: 1;
    min-width: 0;
  }

  .model-title h3 {
    font-size: var(--font-size-lg);
    margin: 0 0 var(--spacing-xs) 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .model-architecture {
    font-size: var(--font-size-xs);
    color: var(--color-grey);
    font-weight: 600;
    text-transform: uppercase;
  }

  .status-badge {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    flex-shrink: 0;
  }

  .metrics-section {
    padding: var(--spacing-md);
    background: linear-gradient(
      135deg,
      var(--color-bg-light1) 0%,
      var(--color-accent-alpha-5) 100%
    );
    border-radius: var(--radius-sm);
    margin: var(--spacing-sm) 0;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
    gap: var(--spacing-sm);
  }

  .metric-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: var(--spacing-sm);
    background: var(--color-bg-secondary);
    border-radius: var(--radius-sm);
    transition: all 0.2s ease;
    border: 2px solid transparent;
  }

  .metric-item:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--color-accent);
  }

  .metric-label {
    font-size: 0.7rem;
    color: var(--color-grey);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .metric-value {
    font-size: 1.25rem;
    font-weight: 700;
    background: linear-gradient(
      135deg,
      var(--color-accent) 0%,
      var(--color-warning) 100%
    );
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: var(--font-size-xs);
  }

  .project-ref {
    color: var(--color-grey);
  }

  .date-text {
    color: var(--color-text-light);
  }

  /* Table View */
  .models-table {
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

  .architecture-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background-color: var(--color-light-grey);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
  }

  /* Validation Status */
  .validation-section {
    padding: var(--spacing-md);
    background: var(--color-light-grey);
    border-radius: var(--radius-sm);
    margin-top: var(--spacing-sm);
  }

  .validation-section.error {
    background: var(--color-danger-alpha-10);
    border: 1px solid var(--color-danger-alpha-30);
  }

  .validation-info {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    color: var(--color-grey);
    font-size: var(--font-size-sm);
  }

  .validation-error {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }

  .validation-error p {
    margin: 0;
    font-size: var(--font-size-xs);
    color: var(--color-grey);
  }

  .no-metrics-info {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
    color: var(--color-grey);
    font-size: var(--font-size-sm);
  }

  .btn-validate {
    margin-top: var(--spacing-xs);
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .btn-validate:hover {
    background: var(--color-accent-dark);
    transform: translateY(-1px);
  }

  .hint-text {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .badge-validating {
    background: linear-gradient(
      135deg,
      var(--color-status-info) 0%,
      var(--color-status-info-dark) 100%
    );
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }

  /* Base Project Badges */
  .base-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    margin-top: 0.25rem;
    background: var(--color-warning-alpha-15);
    border: 1px solid var(--color-warning-alpha-40);
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--color-warning);
    text-transform: uppercase;
    transition: all var(--transition-fast);
  }

  .base-badge:hover {
    background: var(--color-warning-alpha-25);
    border-color: var(--color-warning-alpha-60);
  }

  .base-badge-small {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    background: var(--color-warning-alpha-15);
    border: 1px solid var(--color-warning-alpha-40);
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-warning);
  }

  .project-ref.base-project {
    color: var(--color-warning);
    font-weight: 600;
  }

  /* Task Type Badges */
  .model-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .task-type-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    transition: all var(--transition-fast);
  }

  .task-type-detect {
    background: var(--color-status-success-alpha-15);
    border: 1px solid var(--color-status-success-alpha-40);
    color: var(--color-status-success-dark);
  }

  .task-type-classify {
    background: var(--color-status-info-alpha-15);
    border: 1px solid var(--color-status-info-alpha-40);
    color: var(--color-status-info);
  }

  .task-type-segment {
    background: var(--color-status-info-alpha-15);
    border: 1px solid var(--color-status-info-alpha-40);
    color: var(--color-status-info-dark);
  }

  .task-type-badge-small {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
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

    .models-grid {
      grid-template-columns: 1fr;
    }

    .models-table {
      overflow-x: auto;
    }

    table {
      min-width: 900px;
    }
  }
</style>
