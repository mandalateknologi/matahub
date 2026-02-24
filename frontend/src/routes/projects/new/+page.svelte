<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router";
  import { projectsAPI } from "../../../lib/api/projects";
  import { datasetsAPI } from "../../../lib/api/datasets";
  import { uiStore } from "../../../lib/stores/uiStore";
  import LoadingSpinner from "../../../lib/components/shared/LoadingSpinner.svelte";
  import type { Dataset } from "@/lib/types";

  let datasets: Dataset[] = [];
  let loading = true;
  let creating = false;

  // Form fields
  let projectName = "";
  let selectedDatasetId: number | null = null;
  let taskType = "detect";
  let nameError = "";
  let datasetError = "";
  let createWithoutDataset = false;

  const taskTypes = [
    {
      value: "detect",
      label: "Object Detection",
      description: "Detect and locate objects in images",
    },
    {
      value: "segment",
      label: "Instance Segmentation",
      description: "Detect objects with precise pixel-level masks",
    },
    {
      value: "classify",
      label: "Image Classification",
      description: "Classify entire images into categories",
    },
  ];

  onMount(async () => {
    await loadDatasets();
  });

  async function loadDatasets() {
    try {
      loading = true;
      const allDatasets = await datasetsAPI.list();
      // Filter only datasets with status "valid" (ready)
      datasets = allDatasets.filter((d) => d.status === "valid");

      // Auto-select the first ready dataset if available
      if (datasets.length > 0) {
        selectedDatasetId = datasets[0].id;
      }
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to load datasets", "error");
    } finally {
      loading = false;
    }
  }

  function validateForm(): boolean {
    let isValid = true;
    nameError = "";
    datasetError = "";

    if (!projectName.trim()) {
      nameError = "Project name is required";
      isValid = false;
    } else if (projectName.length > 255) {
      nameError = "Project name must be less than 255 characters";
      isValid = false;
    }

    if (!createWithoutDataset && !selectedDatasetId) {
      datasetError =
        "Please select a dataset or check 'Create without dataset'";
      isValid = false;
    }

    return isValid;
  }

  async function handleSubmit() {
    if (!validateForm()) {
      return;
    }

    try {
      creating = true;
      const project = await projectsAPI.create(
        projectName.trim(),
        createWithoutDataset ? null : selectedDatasetId,
        taskType,
      );

      uiStore.showToast(
        `Project "${project.name}" created successfully!`,
        "success",
      );
      navigate(`/projects/${project.id}`);
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to create project", "error");
    } finally {
      creating = false;
    }
  }

  function handleCancel() {
    navigate("/projects");
  }

  $: selectedDataset = datasets.find((d) => d.id === selectedDatasetId);
</script>

<div class="page">
  <div class="page-header">
    <div class="header-content">
      <h1>Create New Project</h1>
      <p class="subtitle">Set up a new training project with a ready dataset</p>
    </div>
  </div>

  {#if loading}
    <LoadingSpinner message="Loading datasets..." />
  {:else if datasets.length === 0}
    <div class="empty-state">
      <div class="empty-icon">📦</div>
      <h3>No Ready Datasets Available</h3>
      <p>You need at least one validated dataset to create a project.</p>
      <button class="btn btn-primary" on:click={() => navigate("/datasets")}>
        Go to Datasets
      </button>
    </div>
  {:else}
    <div class="form-container">
      <form on:submit|preventDefault={handleSubmit}>
        <!-- Project Name -->
        <div class="form-group">
          <label for="projectName" class="form-label">
            Project Name <span class="required">*</span>
          </label>
          <input
            type="text"
            id="projectName"
            class="form-input"
            class:error={nameError}
            bind:value={projectName}
            placeholder="Enter project name (e.g., Construction PPE Detection)"
            disabled={creating}
            maxlength="255"
          />
          {#if nameError}
            <span class="error-message">{nameError}</span>
          {/if}
          <p class="form-hint">
            Choose a descriptive name for your training project
          </p>
        </div>

        <!-- Generic Project Checkbox -->
        <div class="form-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={createWithoutDataset}
              disabled={creating}
            />
            <span>Create without dataset (Generic project)</span>
          </label>
          <p class="form-hint">
            Generic projects can be used to host pre-trained models without a
            dataset
          </p>
        </div>

        <!-- Dataset Selection -->
        {#if !createWithoutDataset}
          <div class="form-group">
            <label for="dataset" class="form-label">
              Dataset <span class="required">*</span>
            </label>
            <select
              id="dataset"
              class="form-select"
              class:error={datasetError}
              bind:value={selectedDatasetId}
              disabled={creating}
            >
              {#each datasets as dataset}
                <option value={dataset.id}>
                  {dataset.name} ({dataset.images_count} images, {Object.keys(
                    dataset.classes_json || {},
                  ).length} classes)
                </option>
              {/each}
            </select>
            {#if datasetError}
              <span class="error-message">{datasetError}</span>
            {/if}
            {#if selectedDataset}
              <div class="dataset-info">
                <div class="info-row">
                  <span class="info-label">Status:</span>
                  <span class="badge badge-completed">Ready</span>
                </div>
                <div class="info-row">
                  <span class="info-label">Images:</span>
                  <span>{selectedDataset.images_count}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">Classes:</span>
                  <span
                    >{Object.keys(selectedDataset.classes_json || {})
                      .length}</span
                  >
                </div>
                {#if selectedDataset.description}
                  <div class="info-row">
                    <span class="info-label">Description:</span>
                    <span>{selectedDataset.description}</span>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        <!-- Task Type -->
        <div class="form-group">
          <label class="form-label">
            Task Type <span class="required">*</span>
          </label>
          <div class="task-type-grid">
            {#each taskTypes as task}
              <label
                class="task-type-card"
                class:selected={taskType === task.value}
              >
                <input
                  type="radio"
                  name="taskType"
                  value={task.value}
                  bind:group={taskType}
                  disabled={creating}
                />
                <div class="task-type-content">
                  <span class="task-type-label">{task.label}</span>
                  <span class="task-type-description">{task.description}</span>
                </div>
              </label>
            {/each}
          </div>
        </div>

        <!-- Form Actions -->
        <div class="form-actions">
          <button
            type="button"
            class="btn btn-secondary"
            on:click={handleCancel}
            disabled={creating}
          >
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" disabled={creating}>
            {creating ? "Creating..." : "Create Project"}
          </button>
        </div>
      </form>
    </div>
  {/if}
</div>

<style>
  .page {
    padding: 2rem;
    max-width: 800px;
    margin: 0 auto;
  }

  .page-header {
    margin-bottom: 2rem;
  }

  .header-content h1 {
    font-size: 2rem;
    color: var(--color-navy);
    margin-bottom: 0.5rem;
  }

  .subtitle {
    color: var(--color-text-secondary);
    font-size: 1rem;
  }

  .form-container {
    background: white;
    border-radius: 12px;
    padding: 2rem;
    box-shadow: var(--shadow-md);
  }

  .form-group {
    margin-bottom: 2rem;
  }

  .form-label {
    display: block;
    font-weight: 600;
    color: var(--color-navy);
    margin-bottom: 0.5rem;
    font-size: 0.95rem;
  }

  .required {
    color: var(--color-accent);
  }

  .form-input,
  .form-select {
    width: 100%;
    padding: 0.75rem;
    border: 2px solid var(--color-border);
    border-radius: 8px;
    font-size: 1rem;
    transition: border-color var(--transition-fast);
  }

  .form-input:focus,
  .form-select:focus {
    outline: none;
    border-color: var(--color-navy);
  }

  .form-input.error,
  .form-select.error {
    border-color: var(--color-accent);
  }

  .form-input:disabled,
  .form-select:disabled {
    background-color: var(--color-background);
    cursor: not-allowed;
    opacity: 0.6;
  }

  .error-message {
    display: block;
    color: var(--color-accent);
    font-size: 0.85rem;
    margin-top: 0.25rem;
  }

  .form-hint {
    color: var(--color-text-secondary);
    font-size: 0.85rem;
    margin-top: 0.25rem;
  }

  .dataset-info {
    margin-top: 1rem;
    padding: 1rem;
    background: var(--color-background);
    border-radius: 8px;
    border: 1px solid var(--color-border);
  }

  .info-row {
    display: flex;
    align-items: center;
    padding: 0.5rem 0;
    gap: 0.5rem;
  }

  .info-row:not(:last-child) {
    border-bottom: 1px solid var(--color-border);
  }

  .info-label {
    font-weight: 600;
    color: var(--color-text-secondary);
    min-width: 100px;
  }

  .task-type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .task-type-card {
    position: relative;
    padding: 1.25rem;
    border: 2px solid var(--color-border);
    border-radius: 8px;
    cursor: pointer;
    transition: all var(--transition-fast);
    background: white;
  }

  .task-type-card:hover {
    border-color: var(--color-navy);
    box-shadow: var(--shadow-md);
  }

  .task-type-card.selected {
    border-color: var(--color-navy);
    background: var(--color-navy-alpha-5);
  }

  .task-type-card input[type="radio"] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .task-type-content {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .task-type-label {
    font-weight: 600;
    color: var(--color-navy);
    font-size: 1rem;
  }

  .task-type-description {
    color: var(--color-text-secondary);
    font-size: 0.85rem;
    line-height: 1.4;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 1px solid var(--color-border);
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: all var(--transition-fast);
    border: none;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--color-navy);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-navy-dark);
    transform: translateY(-1px);
    box-shadow: var(--shadow-lg);
  }

  .btn-secondary {
    background: white;
    color: var(--color-navy);
    border: 2px solid var(--color-border);
  }

  .btn-secondary:hover:not(:disabled) {
    border-color: var(--color-navy);
    background: var(--color-background);
  }

  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
    background: white;
    border-radius: 12px;
    box-shadow: var(--shadow-md);
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
  }

  .empty-state h3 {
    color: var(--color-navy);
    margin-bottom: 0.5rem;
  }

  .empty-state p {
    color: var(--color-text-secondary);
    margin-bottom: 1.5rem;
  }

  .badge {
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .badge-completed {
    background: var(--color-success-alpha-10);
    color: var(--color-success-dark);
  }
</style>
