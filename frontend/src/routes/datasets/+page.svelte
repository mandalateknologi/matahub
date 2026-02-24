<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { datasetsAPI } from "../../lib/api/datasets";
  import { uiStore } from "../../lib/stores/uiStore";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import type { Dataset } from "@/lib/types";

  // State variables
  let datasets: Dataset[] = [];
  let loading = false;
  let searchTerm = "";
  let selectedTaskType = "all";
  let selectedStatFilter: string | null = null;
  let view: "card" | "list" = "card";
  let sortBy = "created_at";
  let sortOrder: "asc" | "desc" = "desc";
  let statsAnimated = false;

  // Modal state
  let showUploadModal = false;
  let uploading = false;
  let isEmptyDataset = false;
  let formData = {
    name: "",
    description: "",
    taskType: "classify",
    file: null as File | null,
  };

  // Load view preference from localStorage
  onMount(async () => {
    const savedView = localStorage.getItem("datasetsViewMode");
    if (savedView === "list" || savedView === "card") {
      view = savedView;
    }
    await loadDatasets();
    // Trigger stats animation after data loads
    setTimeout(() => {
      statsAnimated = true;
    }, 100);
  });

  function handleStatClick(filterType: string) {
    if (selectedStatFilter === filterType) {
      selectedStatFilter = null;
    } else {
      selectedStatFilter = filterType;
    }
  }

  function handleStatKeydown(event: KeyboardEvent, filterType: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleStatClick(filterType);
    }
  }

  async function loadDatasets() {
    loading = true;
    try {
      datasets = await datasetsAPI.list();
    } catch (error) {
      uiStore.showToast("Failed to load datasets", "error");
      console.error("Error loading datasets:", error);
    } finally {
      loading = false;
    }
  }

  function handleViewChange(newView: "card" | "list") {
    view = newView;
    localStorage.setItem("datasetsViewMode", newView);
  }

  function getTaskIcon(taskType: string): string {
    switch (taskType) {
      case "classify":
        return "📁";
      case "detect":
        return "📊";
      case "segment":
        return "✂️";
      default:
        return "📁";
    }
  }

  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function handleSort(field: string) {
    if (sortBy === field) {
      sortOrder = sortOrder === "asc" ? "desc" : "asc";
    } else {
      sortBy = field;
      sortOrder = "asc";
    }
  }

  function getSortIndicator(field: string): string {
    if (sortBy !== field) return "";
    return sortOrder === "asc" ? " ▲" : " ▼";
  }

  // Computed statistics
  $: totalDatasets = datasets.length;
  $: totalImages = datasets.reduce((sum, d) => sum + (d.images_count || 0), 0);
  $: totalClasses = datasets.reduce(
    (sum, d) => sum + Object.keys(d.classes_json || {}).length,
    0,
  );
  $: validDatasets = datasets.filter((d) => d.status === "valid").length;
  $: incompleteDatasets = datasets.filter(
    (d) => d.status === "incomplete",
  ).length;
  $: emptyDatasets = datasets.filter((d) => d.status === "empty").length;
  $: classifyDatasets = datasets.filter(
    (d) => d.task_type === "classify",
  ).length;
  $: detectDatasets = datasets.filter((d) => d.task_type === "detect").length;
  $: segmentDatasets = datasets.filter((d) => d.task_type === "segment").length;

  // Auto-reset stat filter when other filters change
  $: if (searchTerm || selectedTaskType !== "all") {
    selectedStatFilter = null;
  }

  // Computed filtered and sorted datasets
  let filteredDatasets: Dataset[] = [];

  $: filteredDatasets = datasets
    .filter((dataset: Dataset) => {
      const matchesSearch =
        dataset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (dataset.description || "")
          .toLowerCase()
          .includes(searchTerm.toLowerCase());
      const matchesTaskType =
        selectedTaskType === "all" || dataset.task_type === selectedTaskType;
      const matchesStatFilter =
        !selectedStatFilter ||
        (selectedStatFilter === "valid" && dataset.status === "valid") ||
        (selectedStatFilter === "incomplete" &&
          dataset.status === "incomplete") ||
        (selectedStatFilter === "empty" && dataset.status === "empty") ||
        (selectedStatFilter === "classify" &&
          dataset.task_type === "classify") ||
        (selectedStatFilter === "detect" && dataset.task_type === "detect");
      return matchesSearch && matchesTaskType && matchesStatFilter;
    })
    .sort((a: Dataset, b: Dataset) => {
      let aVal: any = (a as any)[sortBy];
      let bVal: any = (b as any)[sortBy];

      // Handle date sorting
      if (sortBy === "created_at") {
        aVal = new Date(aVal).getTime();
        bVal = new Date(bVal).getTime();
      }

      if (aVal < bVal) return sortOrder === "asc" ? -1 : 1;
      if (aVal > bVal) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });

  function openUploadModal() {
    showUploadModal = true;
    isEmptyDataset = false;
    formData = { name: "", description: "", taskType: "classify", file: null };
  }

  function closeUploadModal() {
    showUploadModal = false;
    isEmptyDataset = false;
    formData = { name: "", description: "", taskType: "classify", file: null };
  }

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      formData.file = target.files[0];
    }
  }

  async function handleUploadSubmit(event: Event) {
    event.preventDefault();

    if (!formData.name) {
      uiStore.showToast("Please provide a dataset name", "error");
      return;
    }

    if (!isEmptyDataset && !formData.file) {
      uiStore.showToast(
        'Please select a file or check "Create Empty Dataset"',
        "error",
      );
      return;
    }

    uploading = true;
    try {
      if (isEmptyDataset) {
        await datasetsAPI.createEmpty(
          formData.name,
          formData.description,
          formData.taskType,
        );
        uiStore.showToast("Empty dataset created successfully", "success");
      } else {
        await datasetsAPI.create(
          formData.name,
          formData.file!,
          formData.description,
          formData.taskType,
        );
        uiStore.showToast("Dataset uploaded successfully", "success");
      }
      closeUploadModal();
      await loadDatasets();
    } catch (error) {
      uiStore.showToast("Failed to create dataset", "error");
      console.error("Error creating dataset:", error);
    } finally {
      uploading = false;
    }
  }

  // Placeholder action handlers
  function handleDelete(id: number) {
    uiStore.showToast("Delete functionality coming soon", "warning");
  }

  function handleUpdate(id: number) {
    navigate(`/datasets/${id}`);
  }

  function handleTrain(id: number) {
    navigate(`/training/new?dataset_id=${id}`);
  }
</script>

<div class="page">
  <!-- Page Header -->
  <div class="page-header">
    <div class="header-left">
      <h1>Datasets</h1>
      <p class="subtitle">
        Upload and manage YOLO format datasets for training
      </p>
    </div>
    <button class="btn btn-primary" on:click={openUploadModal}>
      ➕ New Dataset
    </button>
  </div>

  <!-- Statistics Cards -->
  <div class="stats-grid">
    <div
      class="stat-card"
      class:animate={statsAnimated}
      role="status"
      aria-live="polite"
    >
      <div class="stat-icon">📊</div>
      <div class="stat-content">
        <div class="stat-value">{totalDatasets}</div>
        <div class="stat-label">Total Datasets</div>
      </div>
    </div>

    <div
      class="stat-card"
      class:animate={statsAnimated}
      role="status"
      aria-live="polite"
    >
      <div class="stat-icon">🖼️</div>
      <div class="stat-content">
        <div class="stat-value">{totalImages.toLocaleString()}</div>
        <div class="stat-label">Total Images</div>
      </div>
    </div>

    <div
      class="stat-card"
      class:animate={statsAnimated}
      role="status"
      aria-live="polite"
    >
      <div class="stat-icon">🏷️</div>
      <div class="stat-content">
        <div class="stat-value">{totalClasses}</div>
        <div class="stat-label">Total Classes</div>
      </div>
    </div>

    <button
      class="stat-card clickable"
      class:animate={statsAnimated}
      class:active={selectedStatFilter === "valid"}
      on:click={() => handleStatClick("valid")}
      on:keydown={(e) => handleStatKeydown(e, "valid")}
      tabindex="0"
      aria-pressed={selectedStatFilter === "valid"}
      aria-label="Filter by valid datasets"
      title="Click to filter by valid datasets"
    >
      <div class="stat-icon">✅</div>
      <div class="stat-content">
        <div class="stat-value">{validDatasets}</div>
        <div class="stat-label">Valid</div>
        <div class="stat-breakdown">
          {incompleteDatasets} incomplete · {emptyDatasets} empty
        </div>
      </div>
    </button>

    <button
      class="stat-card clickable"
      class:animate={statsAnimated}
      class:active={selectedStatFilter === "classify"}
      on:click={() => handleStatClick("classify")}
      on:keydown={(e) => handleStatKeydown(e, "classify")}
      tabindex="0"
      aria-pressed={selectedStatFilter === "classify"}
      aria-label="Filter by classification datasets"
      title="Click to filter by classification datasets"
    >
      <div class="stat-icon">📁</div>
      <div class="stat-content">
        <div class="stat-value">{classifyDatasets}</div>
        <div class="stat-label">Classification</div>
      </div>
    </button>

    <button
      class="stat-card clickable"
      class:animate={statsAnimated}
      class:active={selectedStatFilter === "detect"}
      on:click={() => handleStatClick("detect")}
      on:keydown={(e) => handleStatKeydown(e, "detect")}
      tabindex="0"
      aria-pressed={selectedStatFilter === "detect"}
      aria-label="Filter by detection datasets"
      title="Click to filter by detection datasets"
    >
      <div class="stat-icon">🎯</div>
      <div class="stat-content">
        <div class="stat-value">{detectDatasets}</div>
        <div class="stat-label">Detection</div>
      </div>
    </button>

    <button
      class="stat-card clickable"
      class:animate={statsAnimated}
      class:active={selectedStatFilter === "segment"}
      on:click={() => handleStatClick("segment")}
      on:keydown={(e) => handleStatKeydown(e, "segment")}
      tabindex="0"
      aria-pressed={selectedStatFilter === "segment"}
      aria-label="Filter by segmentation datasets"
      title="Click to filter by segmentation datasets"
    >
      <div class="stat-icon">✂️</div>
      <div class="stat-content">
        <div class="stat-value">{segmentDatasets}</div>
        <div class="stat-label">Segmentation</div>
      </div>
    </button>
  </div>

  <!-- Search and Controls -->
  <div class="controls-bar">
    <div class="search-and-filters">
      <input
        type="text"
        class="search-input"
        placeholder="Search datasets..."
        bind:value={searchTerm}
      />

      <div class="task-filters">
        <button
          class="filter-btn"
          class:active={selectedTaskType === "all"}
          on:click={() => (selectedTaskType = "all")}
        >
          All
        </button>
        <button
          class="filter-btn"
          class:active={selectedTaskType === "classify"}
          on:click={() => (selectedTaskType = "classify")}
        >
          Classify
        </button>
        <button
          class="filter-btn"
          class:active={selectedTaskType === "detect"}
          on:click={() => (selectedTaskType = "detect")}
        >
          Detect
        </button>
        <button
          class="filter-btn"
          class:active={selectedTaskType === "segment"}
          on:click={() => (selectedTaskType = "segment")}
        >
          Segment
        </button>
      </div>
    </div>

    <ViewToggle {view} onChange={handleViewChange} />
  </div>

  <!-- Loading State -->
  {#if loading}
    <div class="spinner-container">
      <div class="spinner"></div>
      <div class="spinner-text">Loading datasets...</div>
    </div>

    <!-- Empty State -->
  {:else if filteredDatasets.length === 0}
    <div class="empty-state">
      <div class="empty-icon">📁</div>
      <h3>No datasets yet</h3>
      <p>Create your first dataset to get started with training</p>
      <button class="btn btn-primary" on:click={openUploadModal}>
        New Dataset
      </button>
    </div>

    <!-- Card View -->
  {:else if view === "card"}
    <div class="dataset-grid">
      {#each filteredDatasets as dataset (dataset.id)}
        <div class="dataset-card">
          <div class="card-header">
            <div class="card-icon-large">{getTaskIcon(dataset.task_type)}</div>
            <span
              class="task-badge"
              class:classify={dataset.task_type === "classify"}
            >
              {dataset.task_type === "classify"
                ? "Classify"
                : dataset.task_type}
            </span>
          </div>

          <div class="card-body">
            <h3 class="dataset-name">{dataset.name}</h3>
            <p class="dataset-description">
              {dataset.description || "No description provided"}
            </p>

            <div class="dataset-stats">
              <div class="stat-item">
                <span class="stat-label"
                  >{Object.keys(dataset.classes_json || {}).length} classes</span
                >
              </div>
              <div class="stat-item">
                <span class="stat-label">{dataset.images_count} images</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">-- MB</span>
              </div>
            </div>

            {#if dataset.status === "empty"}
              <div class="status-badge empty">Empty</div>
            {:else if dataset.status === "incomplete"}
              <div class="status-badge incomplete">Incomplete</div>
            {/if}
          </div>

          <div class="card-actions">
            <button
              class="action-btn"
              on:click={() => handleUpdate(dataset.id)}
              title="View / Update"
            >
              <span class="action-icon">✏️</span>
              <span class="action-label">View / Update</span>
            </button>
            <button
              class="action-btn"
              on:click={() => handleTrain(dataset.id)}
              disabled={dataset.status !== "valid"}
              title={dataset.status === "valid"
                ? "Train"
                : "Dataset must be valid to train"}
            >
              <span class="action-icon">▶️</span>
              <span class="action-label">Train</span>
            </button>
            <button
              class="action-btn"
              on:click={() => handleDelete(dataset.id)}
              title="Delete"
            >
              <span class="action-icon">🗑️</span>
              <span class="action-label">Delete</span>
            </button>
          </div>
        </div>
      {/each}
    </div>

    <!-- Table View -->
  {:else}
    <div class="table-container">
      <table class="datasets-table">
        <thead>
          <tr>
            <th>Icon</th>
            <th on:click={() => handleSort("name")} class="sortable">
              Name{getSortIndicator("name")}
            </th>
            <th on:click={() => handleSort("task_type")} class="sortable">
              Task Type{getSortIndicator("task_type")}
            </th>
            <th on:click={() => handleSort("status")} class="sortable">
              Status{getSortIndicator("status")}
            </th>
            <th on:click={() => handleSort("images_count")} class="sortable">
              Images{getSortIndicator("images_count")}
            </th>
            <th>Classes</th>
            <th>Size</th>
            <th on:click={() => handleSort("created_at")} class="sortable">
              Created{getSortIndicator("created_at")}
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredDatasets as dataset (dataset.id)}
            <tr>
              <td class="icon-cell">{getTaskIcon(dataset.task_type)}</td>
              <td class="name-cell">{dataset.name}</td>
              <td>
                <span
                  class="task-badge"
                  class:classify={dataset.task_type === "classify"}
                >
                  {dataset.task_type === "classify"
                    ? "Classify"
                    : dataset.task_type}
                </span>
              </td>
              <td>
                <span
                  class="status-badge"
                  class:valid={dataset.status === "valid"}
                  class:empty={dataset.status === "empty"}
                  class:incomplete={dataset.status === "incomplete"}
                >
                  {dataset.status === "valid" ? "Ready" : dataset.status}
                </span>
              </td>
              <td>{dataset.images_count}</td>
              <td>{Object.keys(dataset.classes_json || {}).length}</td>
              <td class="text-muted">-- MB</td>
              <td>{formatDate(dataset.created_at)}</td>
              <td class="actions-cell">
                <button
                  class="action-btn-small"
                  on:click={() => handleUpdate(dataset.id)}
                  title="View / Update"
                >
                  <span class="action-icon">✏️</span>
                  <span class="action-label">View / Update</span>
                </button>
                <button
                  class="action-btn-small"
                  on:click={() => handleTrain(dataset.id)}
                  disabled={dataset.status !== "valid"}
                  title={dataset.status === "valid"
                    ? "Train"
                    : "Dataset must be valid to train"}
                >
                  <span class="action-icon">▶️</span>
                  <span class="action-label">Train</span>
                </button>
                <button
                  class="action-btn-small"
                  on:click={() => handleDelete(dataset.id)}
                  title="Delete"
                >
                  <span class="action-icon">🗑️</span>
                  <span class="action-label">Delete</span>
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Upload Modal -->
{#if showUploadModal}
  <div class="modal-overlay" on:click={closeUploadModal}>
    <div class="modal-content" on:click|stopPropagation>
      {#if uploading}
        <div class="spinner-container">
          <div class="spinner"></div>
          <div class="spinner-text">Uploading...</div>
        </div>
      {:else}
        <div class="modal-header">
          <h2>New Dataset</h2>
          <button class="close-btn" on:click={closeUploadModal}>&times;</button>
        </div>

        <form on:submit={handleUploadSubmit}>
          <div class="modal-body">
            <div class="form-group">
              <label for="dataset-name">Name *</label>
              <input
                id="dataset-name"
                type="text"
                bind:value={formData.name}
                required
                placeholder="Enter dataset name"
              />
            </div>

            <div class="form-group">
              <label for="dataset-description">Description</label>
              <textarea
                id="dataset-description"
                bind:value={formData.description}
                rows="3"
                placeholder="Enter dataset description (optional)"
              ></textarea>
            </div>

            <div class="form-group">
              <label for="task-type">Task Type</label>
              <select id="task-type" bind:value={formData.taskType}>
                <option value="classify">Classification</option>
                <option value="detect">Object Detection</option>
                <option value="segment">Instance Segmentation</option>
              </select>
            </div>

            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" bind:checked={isEmptyDataset} />
                Create Empty Dataset (without files)
              </label>
              <small class="form-hint">
                Create a dataset with empty directory structure. You can add
                files later.
              </small>
            </div>

            {#if !isEmptyDataset}
              <div class="form-group">
                <label for="dataset-file">Dataset File (ZIP) *</label>
                <input
                  id="dataset-file"
                  type="file"
                  accept=".zip"
                  required
                  on:change={handleFileSelect}
                />
                <small class="form-hint">
                  Upload a ZIP file containing images/ and labels/ folders in
                  YOLO format
                </small>
              </div>
            {/if}
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-outline"
              on:click={closeUploadModal}
            >
              Cancel
            </button>
            <button type="submit" class="btn btn-primary"> Upload </button>
          </div>
        </form>
      {/if}
    </div>
  </div>
{/if}

<style>
  .page {
    padding: var(--spacing-lg);
    min-height: 100vh;
  }

  /* Keyframe Animations */
  @keyframes fadeInCard {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes countUp {
    from {
      opacity: 0;
      transform: scale(0.8);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  /* Statistics Cards */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--spacing-lg);
    margin-bottom: var(--spacing-xl);
  }

  .stat-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    transition:
      transform var(--transition-fast),
      box-shadow var(--transition-fast),
      border-color var(--transition-fast),
      background-color var(--transition-fast);
    opacity: 0;
    border: 3px solid transparent;
    text-align: left;
    width: 100%;
  }

  .stat-card.animate {
    animation: fadeInCard 0.6s ease-out forwards;
  }

  .stat-card:nth-child(1) {
    animation-delay: 0s;
  }

  .stat-card:nth-child(2) {
    animation-delay: 0.15s;
  }

  .stat-card:nth-child(3) {
    animation-delay: 0.3s;
  }

  .stat-card:nth-child(4) {
    animation-delay: 0.45s;
  }

  .stat-card:nth-child(5) {
    animation-delay: 0.6s;
  }

  .stat-card:nth-child(6) {
    animation-delay: 0.75s;
  }

  .stat-card.clickable {
    cursor: pointer;
  }

  .stat-card.clickable:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  .stat-card.clickable:active {
    transform: translateY(0);
  }

  .stat-card.active {
    border-color: var(--color-accent);
    background-color: rgba(225, 96, 76, 0.05);
  }

  .stat-icon {
    font-size: 2.5rem;
    flex-shrink: 0;
  }

  .stat-content {
    flex: 1;
  }

  .stat-value {
    font-size: var(--font-size-xxl);
    font-weight: 700;
    color: var(--color-navy);
    line-height: 1;
    margin-bottom: var(--spacing-xs);
  }

  .stat-card.animate .stat-value {
    animation: countUp 0.4s ease-out forwards;
    animation-delay: inherit;
  }

  .stat-label {
    font-size: var(--font-size-sm);
    color: var(--color-grey);
    font-weight: 500;
    margin-bottom: var(--spacing-xs);
  }

  .stat-breakdown {
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
  }

  /* Page Header */
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-xl);
  }

  .header-left h1 {
    margin-bottom: var(--spacing-xs);
  }

  .subtitle {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  /* Controls Bar */
  .controls-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--spacing-lg);
    margin-bottom: var(--spacing-xl);
    flex-wrap: wrap;
  }

  .search-and-filters {
    display: flex;
    gap: var(--spacing-md);
    flex: 1;
    align-items: center;
    flex-wrap: wrap;
  }

  .search-input {
    min-width: 250px;
    flex: 1;
    max-width: 400px;
  }

  .task-filters {
    display: flex;
    gap: var(--spacing-sm);
  }

  .filter-btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    border-radius: var(--radius-md);
    font-weight: 500;
    font-size: var(--font-size-sm);
    background-color: var(--color-white);
    color: var(--color-navy);
    border: 2px solid var(--color-bg-light1);
    transition: all var(--transition-fast);
  }

  .filter-btn.active {
    background-color: var(--color-accent);
    color: var(--color-white);
    border-color: var(--color-accent);
  }

  .filter-btn.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .filter-btn.disabled:hover {
    transform: none;
  }

  /* Empty State */
  .empty-state {
    text-align: center;
    padding: var(--spacing-xl) var(--spacing-lg);
    margin-top: var(--spacing-xl);
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-lg);
  }

  .empty-state h3 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
  }

  .empty-state p {
    color: var(--color-grey);
    margin-bottom: var(--spacing-lg);
  }

  /* Cards Grid */
  .dataset-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  @media (min-width: 768px) {
    .dataset-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1200px) {
    .dataset-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1600px) {
    .dataset-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .dataset-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    transition: box-shadow var(--transition-base);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    border: 2px solid transparent;
  }

  .dataset-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .card-header {
    padding: var(--spacing-lg);
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--color-bg-light1);
  }

  .card-icon-large {
    font-size: 3rem;
  }

  .task-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    background-color: var(--color-bg-light1);
    color: var(--color-navy);
  }

  .task-badge.classify {
    background-color: var(--color-warning-alpha-10);
    color: var(--color-warning-dark);
  }

  .task-badge.detect {
    background-color: var(--color-info-alpha-10);
    color: var(--color-info-dark);
  }

  .task-badge.segment {
    background-color: var(--color-accent-alpha-10);
    color: var(--color-accent);
  }

  .card-body {
    padding: var(--spacing-lg);
    flex: 1;
  }

  .dataset-name {
    font-size: var(--font-size-lg);
    font-weight: 600;
    margin-bottom: var(--spacing-sm);
    color: var(--color-navy);
  }

  .dataset-description {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-lg);
    line-height: 1.5;
  }

  .dataset-stats {
    display: flex;
    gap: var(--spacing-lg);
    flex-wrap: wrap;
  }

  .stat-item {
    display: flex;
    flex-direction: column;
  }

  .stat-label {
    font-size: var(--font-size-sm);
    color: var(--color-grey);
    font-weight: 500;
  }

  .card-actions {
    padding: var(--spacing-md) var(--spacing-lg);
    border-top: 1px solid var(--color-bg-light1);
    display: flex;
    gap: var(--spacing-sm);
    flex-wrap: wrap;
  }

  .action-btn {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    background-color: transparent;
    color: var(--color-navy);
    border: 1px solid var(--color-bg-light1);
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    transition: all var(--transition-fast);
  }

  .action-btn:hover:not(:disabled) {
    background-color: var(--color-bg-light1);
  }

  .action-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .action-icon {
    font-size: var(--font-size-base);
  }

  /* Table View */
  .table-container {
    background: var(--color-white);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    overflow-x: auto;
  }

  .datasets-table {
    width: 100%;
    border-collapse: collapse;
  }

  .datasets-table thead {
    background-color: var(--color-bg-light1);
  }

  .datasets-table th {
    padding: var(--spacing-md) var(--spacing-lg);
    text-align: left;
    font-weight: 600;
    font-size: var(--font-size-sm);
    color: var(--color-navy);
    white-space: nowrap;
  }

  .datasets-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .datasets-table th.sortable:hover {
    background-color: var(--color-bg-light2);
  }

  .datasets-table tbody tr {
    border-bottom: 1px solid var(--color-bg-light1);
    transition: background-color var(--transition-fast);
  }

  .datasets-table tbody tr:hover {
    background-color: var(--color-bg-light1);
  }

  .datasets-table td {
    padding: var(--spacing-md) var(--spacing-lg);
    font-size: var(--font-size-sm);
  }

  .icon-cell {
    font-size: var(--font-size-xl);
  }

  .name-cell {
    font-weight: 600;
    color: var(--color-navy);
  }

  .actions-cell {
    display: flex;
    gap: var(--spacing-xs);
    flex-wrap: wrap;
  }

  .action-btn-small {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    background-color: transparent;
    color: var(--color-navy);
    border: 1px solid var(--color-bg-light1);
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all var(--transition-fast);
  }

  .action-btn-small:hover:not(:disabled) {
    background-color: var(--color-bg-light1);
  }

  .action-btn-small:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .action-btn-small .action-icon {
    font-size: var(--font-size-sm);
  }

  /* Modal Specific */
  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    color: var(--color-grey);
    cursor: pointer;
    padding: 0;
    line-height: 1;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    color: var(--color-navy);
    transform: none;
  }

  .form-group {
    margin-bottom: var(--spacing-lg);
  }

  .form-group label {
    display: block;
    margin-bottom: var(--spacing-sm);
    font-weight: 500;
    color: var(--color-navy);
  }

  .form-group input,
  .form-group textarea,
  .form-group select {
    width: 100%;
  }

  .form-hint {
    display: block;
    margin-top: var(--spacing-xs);
    color: var(--color-grey);
    font-size: var(--font-size-xs);
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    cursor: pointer;
    font-weight: 500;
  }

  .checkbox-label input[type="checkbox"] {
    width: auto;
    cursor: pointer;
  }

  /* Status Badges */
  .status-badge {
    display: inline-block;
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    margin-top: var(--spacing-sm);
  }

  .status-badge.valid {
    background-color: var(--color-success-alpha-10);
    color: var(--color-success-dark);
  }

  .status-badge.empty {
    background-color: var(--color-info-alpha-10);
    color: var(--color-info-dark);
  }

  .status-badge.incomplete {
    background-color: var(--color-warning-alpha-10);
    color: var(--color-warning-dark);
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

  /* Responsive Design */
  @media (max-width: 768px) {
    .stats-grid {
      display: none;
    }

    .page-header {
      flex-direction: column;
      gap: var(--spacing-md);
    }

    .controls-bar {
      flex-direction: column;
      align-items: stretch;
    }

    .search-and-filters {
      flex-direction: column;
      align-items: stretch;
    }

    .search-input {
      max-width: 100%;
    }

    .dataset-grid {
      grid-template-columns: 1fr;
    }

    .action-label {
      display: none;
    }

    .action-btn,
    .action-btn-small {
      padding: var(--spacing-xs);
    }

    .card-actions {
      justify-content: space-around;
    }

    .actions-cell {
      justify-content: flex-start;
    }

    .datasets-table {
      font-size: var(--font-size-xs);
    }

    .datasets-table th,
    .datasets-table td {
      padding: var(--spacing-sm);
    }
  }

  @media (min-width: 769px) {
    .action-label {
      display: inline;
    }
  }
</style>
