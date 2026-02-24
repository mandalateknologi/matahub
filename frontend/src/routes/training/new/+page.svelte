<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router";
  import { datasetsAPI } from "../../../lib/api/datasets";
  import { projectsAPI } from "../../../lib/api/projects";
  import { modelsAPI } from "../../../lib/api/models";
  import { trainingAPI } from "../../../lib/api/training";
  import { uiStore } from "../../../lib/stores/uiStore";
  import type { Dataset, BaseModelInfo, TrainingStart } from "@/lib/types";

  // URL params
  let urlParams: URLSearchParams;
  let preselectedDatasetId: number | null = null;

  // Wizard state
  let currentStep = 1;
  let totalSteps = 4; // Changed from 3 to 4 steps

  // Step 1: Dataset selection
  let datasets: Dataset[] = [];
  let selectedDataset: Dataset | null = null;
  let datasetsLoading = true;

  // Step 1.5: Project selection (new step after dataset selection)
  let existingProjects: any[] = [];
  let selectedProject: any | null = null;
  let projectsLoading = false;
  let projectsLoaded = false; // Flag to prevent infinite loop
  let createNewProject = false;
  let showOverrideModal = false;
  let overrideConsent = {
    understood: false,
    acceptNewModel: false,
    confirmRetraining: false,
  };

  // Reactive declaration for "Check All" state
  $: allChecked =
    overrideConsent.understood &&
    overrideConsent.acceptNewModel &&
    overrideConsent.confirmRetraining;

  // Reactive statement to load projects when reaching step 2
  $: if (
    currentStep === 2 &&
    selectedDataset &&
    !projectsLoading &&
    !projectsLoaded
  ) {
    loadProjectsForDataset(selectedDataset.id);
  }

  // Reactive statement to load models when reaching step 3
  $: if (
    currentStep === 3 &&
    selectedDataset &&
    !modelsLoading &&
    !modelsLoaded
  ) {
    loadAvailableModels();
  }

  function toggleCheckAll() {
    const newState = !allChecked;
    overrideConsent.understood = newState;
    overrideConsent.acceptNewModel = newState;
    overrideConsent.confirmRetraining = newState;
  }

  // Step 2: Model selection
  let basedProjectModels: any[] = []; // Models from "Based" system project
  let checkpointModels: any[] = []; // Models from projects using same dataset
  let selectedBaseModel: number | null = null; // Model ID
  let modelsLoading = false;
  let modelsLoaded = false; // Flag to prevent infinite loop

  // Step 3: Configuration
  let projectName = "";
  let modelName = "";
  let epochs = 100;
  let batchSize = 16;
  let imageSize = 640;
  let learningRate = 0.01;

  // Submission
  let submitting = false;

  onMount(async () => {
    // Parse URL parameters FIRST (handle hash routing)
    const hash = window.location.hash;
    const queryStringStart = hash.indexOf("?");
    if (queryStringStart !== -1) {
      const queryString = hash.substring(queryStringStart + 1);
      urlParams = new URLSearchParams(queryString);
      const datasetIdParam = urlParams.get("dataset_id");
      if (datasetIdParam) {
        preselectedDatasetId = parseInt(datasetIdParam);
        console.log("Preselected dataset ID from URL:", preselectedDatasetId);
      }
    }

    // Load datasets AFTER parsing URL params
    await loadDatasets();
  });

  async function loadDatasets() {
    datasetsLoading = true;
    try {
      // Pass preselectedDatasetId to backend for filtering
      const datasetIdFilter =
        preselectedDatasetId !== null ? preselectedDatasetId : undefined;
      console.log("Loading datasets with filter:", datasetIdFilter);

      const response = await datasetsAPI.list(0, 100, datasetIdFilter);
      // Filter to only show valid datasets (detection, classification, and segmentation)
      datasets = response.filter(
        (d) =>
          (d.task_type === "detect" ||
            d.task_type === "classify" ||
            d.task_type === "segment") &&
          d.status === "valid",
      );

      // Auto-select if preselected
      if (preselectedDatasetId) {
        const preselected = datasets.find((d) => d.id === preselectedDatasetId);
        if (preselected) {
          selectedDataset = preselected;
        }
      }
    } catch (error) {
      uiStore.showToast("Failed to load datasets", "error");
      console.error("Error loading datasets:", error);
    } finally {
      datasetsLoading = false;
    }
  }

  async function loadAvailableModels() {
    if (!selectedDataset) return;

    modelsLoading = true;
    basedProjectModels = [];
    checkpointModels = [];

    try {
      console.log(
        `Loading models for dataset task_type: ${selectedDataset.task_type}`,
      );

      // Load all projects to find "Based" system project
      const allProjects = await projectsAPI.list();
      console.log(`Found ${allProjects.length} total projects`);

      const basedProject = allProjects.find(
        (p) => p.is_system && p.name === "Based",
      );

      // Load models from "Based" project filtered by dataset task_type
      if (basedProject) {
        console.log(
          `Found Based project (ID: ${basedProject.id}), loading models...`,
        );
        const basedModels = await modelsAPI.list(
          0,
          100,
          basedProject.id,
          selectedDataset.task_type,
        );
        console.log(`Loaded ${basedModels.length} models from Based project`);
        basedProjectModels = basedModels.filter((m) => m.status === "ready");
        console.log(`${basedProjectModels.length} models are ready`);
      } else {
        console.warn("System project 'Based' not found");
      }

      // Load checkpoint models from projects using the same dataset, filtered by task_type
      console.log(
        `Loading checkpoint models from ${existingProjects.length} existing projects`,
      );
      for (const project of existingProjects) {
        try {
          const projectModels = await modelsAPI.list(
            0,
            100,
            project.id,
            selectedDataset.task_type,
          );
          const readyModels = projectModels
            .filter((m) => m.status === "ready")
            .map((m) => ({ ...m, projectName: project.name }));
          checkpointModels.push(...readyModels);
        } catch (projectError) {
          console.error(
            `Error loading models from project ${project.id}:`,
            projectError,
          );
        }
      }
      console.log(`Loaded ${checkpointModels.length} checkpoint models total`);

      // Auto-select first available model
      if (basedProjectModels.length > 0) {
        selectedBaseModel = basedProjectModels[0].id;
        console.log(`Auto-selected base model ID: ${selectedBaseModel}`);
      } else if (checkpointModels.length > 0) {
        selectedBaseModel = checkpointModels[0].id;
        console.log(`Auto-selected checkpoint model ID: ${selectedBaseModel}`);
      } else {
        selectedBaseModel = null;
        console.warn("No models available for selection");
      }
    } catch (error) {
      console.error("Error loading models:", error);
      uiStore.showToast(
        `Failed to load models: ${error.message || "Unknown error"}`,
        "error",
      );
      basedProjectModels = [];
      checkpointModels = [];
    } finally {
      modelsLoading = false;
      modelsLoaded = true; // Mark as loaded to prevent re-triggering
      console.log("Models loading completed");
    }
  }

  async function selectDataset(dataset: Dataset) {
    selectedDataset = dataset;
    // Reset project selection and loaded flags
    selectedProject = null;
    createNewProject = false;
    projectsLoaded = false;
    modelsLoaded = false; // Reset models loaded flag

    // Auto-fill project and model names if not already set
    if (!projectName || projectName === "") {
      projectName = `${dataset.name} Training`;
    }
    if (!modelName || modelName === "") {
      modelName = `${dataset.name} Model`;
    }

    // Load existing projects for this dataset
    await loadProjectsForDataset(dataset.id);

    // Load available models after projects are loaded
    await loadAvailableModels();
  }

  async function loadProjectsForDataset(datasetId: number) {
    projectsLoading = true;
    try {
      console.log(`=== Loading projects for dataset ${datasetId} ===`);
      console.log(`Dataset task_type: ${selectedDataset?.task_type}`);

      const allProjects = await projectsAPI.list(0, 100, datasetId);
      console.log(`API returned ${allProjects.length} projects:`, allProjects);

      // Filter by matching task_type for compatibility AND exclude system projects
      existingProjects = allProjects.filter(
        (p) => !p.is_system && p.task_type === selectedDataset?.task_type,
      );

      console.log(`After filtering (non-system + matching task_type):`);
      console.log(`  - ${existingProjects.length} compatible projects found`);
      if (existingProjects.length > 0) {
        console.log(
          `  - Projects:`,
          existingProjects.map((p) => ({
            id: p.id,
            name: p.name,
            task_type: p.task_type,
            is_system: p.is_system,
          })),
        );
      } else {
        console.warn(`  - No compatible projects found`);
        console.log(
          `  - All projects received:`,
          allProjects.map((p) => ({
            id: p.id,
            name: p.name,
            task_type: p.task_type,
            is_system: p.is_system,
            dataset_id: p.dataset_id,
          })),
        );
      }
    } catch (error) {
      uiStore.showToast("Failed to load projects", "error");
      console.error("Error loading projects:", error);
      existingProjects = [];
    } finally {
      projectsLoading = false;
      projectsLoaded = true; // Mark as loaded to prevent infinite loop
    }
  }

  function selectExistingProject(project: any) {
    if (project.status === "training") {
      uiStore.showToast(
        "Project is currently training. Please wait for it to complete.",
        "warning",
      );
      return;
    }

    selectedProject = project;
    createNewProject = false;
    showOverrideModal = true;

    // Reset override consent
    overrideConsent = {
      understood: false,
      acceptNewModel: false,
      confirmRetraining: false,
    };
  }

  function selectNewProject() {
    selectedProject = null;
    createNewProject = true;
    showOverrideModal = false;

    // Auto-fill project and model names for new project
    if (!projectName || projectName === "") {
      projectName = `${selectedDataset?.name} Training`;
    }
    if (!modelName || modelName === "") {
      modelName = `${selectedDataset?.name} Model`;
    }
  }

  function confirmOverride() {
    if (
      !overrideConsent.understood ||
      !overrideConsent.acceptNewModel ||
      !overrideConsent.confirmRetraining
    ) {
      uiStore.showToast(
        "Please confirm all items before proceeding",
        "warning",
      );
      return;
    }

    showOverrideModal = false;

    // Pre-fill model name with versioning
    const existingModelsCount = selectedProject?.models?.length || 0;
    modelName = `${selectedProject.name} Model v${existingModelsCount + 1}`;
  }

  function cancelOverride() {
    showOverrideModal = false;
    selectedProject = null;
  }

  function nextStep() {
    if (currentStep < totalSteps) {
      currentStep++;
    }
  }

  function previousStep() {
    if (currentStep > 1) {
      currentStep--;
    }
  }

  function goToStep(targetStep: number) {
    // Only allow navigation to validated steps
    if (targetStep === 1) {
      currentStep = targetStep;
    } else if (targetStep === 2 && canAccessStep2) {
      currentStep = targetStep;
    } else if (targetStep === 3 && canAccessStep3) {
      currentStep = targetStep;
    } else if (targetStep === 4 && canAccessStep4) {
      currentStep = targetStep;
    }
    // Silently ignore clicks on inaccessible steps
  }

  // Reactive declarations for button states
  $: canProceedStep1 = selectedDataset !== null;
  $: canProceedStep2 = selectedProject !== null || createNewProject;
  $: canProceedStep3 = selectedBaseModel !== null && selectedBaseModel > 0;
  $: canSubmit =
    selectedDataset !== null &&
    (selectedProject !== null || createNewProject) &&
    selectedBaseModel !== null &&
    selectedBaseModel > 0 &&
    (selectedProject !== null || projectName.trim() !== "") &&
    modelName.trim() !== "";

  // Step accessibility for direct navigation
  $: canAccessStep1 = true;
  $: canAccessStep2 = canProceedStep1;
  $: canAccessStep3 = canProceedStep1 && canProceedStep2;
  $: canAccessStep4 = canProceedStep1 && canProceedStep2 && canProceedStep3;

  async function handleSubmit() {
    if (!canSubmit || !selectedDataset) return;

    submitting = true;
    try {
      let projectId: number;

      // Use existing project or create new one
      if (selectedProject) {
        projectId = selectedProject.id;
      } else {
        // Create new project
        const project = await projectsAPI.create(
          projectName,
          selectedDataset.id,
          selectedDataset.task_type,
        );
        projectId = project.id;
      }

      // Start training
      const trainingData: TrainingStart = {
        project_id: projectId,
        model_name: modelName,
        base_model_id: selectedBaseModel!,
        epochs: epochs,
        batch_size: batchSize,
        image_size: imageSize,
        learning_rate: learningRate,
      };

      const trainingJob = await trainingAPI.start(trainingData);

      uiStore.showToast("Training started successfully!", "success");

      // Redirect to training job detail or projects page
      navigate(`/projects/${projectId}`);
    } catch (error) {
      uiStore.showToast("Failed to start training", "error");
      console.error("Error starting training:", error);
    } finally {
      submitting = false;
    }
  }

  function getModelDescription(modelName: string): {
    title: string;
    desc: string;
  } {
    const model = baseModels.find((m) => m.name === modelName);
    if (!model) return { title: modelName, desc: "" };
    return { title: model.name.toUpperCase(), desc: model.description };
  }
</script>

<div class="training-wizard">
  <div class="wizard-sidebar">
    <div class="wizard-header">
      <h2>Train New Model</h2>
      <button class="btn-close" on:click={() => window.history.back()}>✕</button
      >
    </div>

    <div class="wizard-steps">
      <button
        type="button"
        class="step-item"
        class:active={currentStep === 1}
        class:completed={currentStep > 1}
        class:clickable={canAccessStep1}
        on:click={() => goToStep(1)}
      >
        <div class="step-number">1</div>
        <div class="step-info">
          <div class="step-title">Select Dataset</div>
          <div class="step-desc">Choose training data</div>
        </div>
      </button>

      <button
        type="button"
        class="step-item"
        class:active={currentStep === 2}
        class:completed={currentStep > 2}
        class:clickable={canAccessStep2}
        disabled={!canAccessStep2}
        on:click={() => goToStep(2)}
      >
        <div class="step-number">2</div>
        <div class="step-info">
          <div class="step-title">Select Project</div>
          <div class="step-desc">New or existing</div>
        </div>
      </button>

      <button
        type="button"
        class="step-item"
        class:active={currentStep === 3}
        class:completed={currentStep > 3}
        class:clickable={canAccessStep3}
        disabled={!canAccessStep3}
        on:click={() => goToStep(3)}
      >
        <div class="step-number">3</div>
        <div class="step-info">
          <div class="step-title">Choose Model</div>
          <div class="step-desc">Select base model</div>
        </div>
      </button>

      <button
        type="button"
        class="step-item"
        class:active={currentStep === 4}
        class:clickable={canAccessStep4}
        disabled={!canAccessStep4}
        on:click={() => goToStep(4)}
      >
        <div class="step-number">4</div>
        <div class="step-info">
          <div class="step-title">Configure</div>
          <div class="step-desc">Training settings</div>
        </div>
      </button>
    </div>
  </div>

  <div class="wizard-content">
    {#if currentStep === 1}
      <!-- Step 1: Dataset Selection -->
      <div class="step-content">
        <h1>Select Dataset</h1>
        <p class="step-subtitle">Choose a validated dataset for training</p>

        {#if datasetsLoading}
          <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading datasets...</p>
          </div>
        {:else if datasets.length === 0}
          <div class="empty-state">
            <p>No validated datasets available</p>
            <a href="/datasets" class="btn btn-primary">Go to Datasets</a>
          </div>
        {:else}
          <div class="dataset-grid">
            {#each datasets as dataset}
              <button
                class="dataset-card"
                class:selected={selectedDataset?.id === dataset.id}
                on:click={() => selectDataset(dataset)}
              >
                <div class="dataset-card-header">
                  <h3>{dataset.name}</h3>
                  {#if selectedDataset?.id === dataset.id}
                    <span class="check-icon">✓</span>
                  {/if}
                </div>
                <p class="dataset-description">
                  {dataset.description || "No description"}
                </p>
                <div class="dataset-stats">
                  <div class="stat">
                    <span class="stat-label">Images:</span>
                    <span class="stat-value">{dataset.images_count || 0}</span>
                  </div>
                  <div class="stat">
                    <span class="stat-label">Classes:</span>
                    <span class="stat-value"
                      >{Object.keys(dataset.classes_json || {}).length}</span
                    >
                  </div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="step-actions">
        <button class="btn btn-outline" on:click={() => window.history.back()}>
          Cancel
        </button>
        <div class="action-right">
          {#if !selectedDataset}
            <span class="hint-text">Select a dataset to continue</span>
          {/if}
          <button
            class="btn btn-primary"
            disabled={!canProceedStep1}
            on:click={nextStep}
          >
            Next →
          </button>
        </div>
      </div>
    {/if}

    {#if currentStep === 2}
      <!-- Step 2: Project Selection -->
      <div class="step-content">
        <h1>Select Project</h1>
        <p class="step-subtitle">Use an existing project or create a new one</p>

        {#if projectsLoading}
          <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading projects...</p>
          </div>
        {:else}
          <div class="project-options">
            <!-- Create New Project Option -->
            <button
              class="project-option-card new-project"
              class:selected={createNewProject}
              on:click={selectNewProject}
            >
              <div class="option-icon">➕</div>
              <h3>Create New Project</h3>
              <p>Start fresh with a new training project</p>
              {#if createNewProject}
                <span class="check-icon">✓</span>
              {/if}
            </button>

            <!-- Existing Projects -->
            {#if existingProjects.length > 0}
              <div class="divider">
                <span>OR</span>
              </div>

              <div class="existing-projects-section">
                <h3>Use Existing Project</h3>
                <p class="section-desc">
                  Continue training with a project that already uses this
                  dataset
                </p>

                <div class="projects-grid">
                  {#each existingProjects as project}
                    <button
                      class="project-card"
                      class:selected={selectedProject?.id === project.id}
                      class:disabled={project.status === "training"}
                      on:click={() => selectExistingProject(project)}
                      disabled={project.status === "training"}
                    >
                      <div class="project-card-header">
                        <h4>{project.name}</h4>
                        {#if selectedProject?.id === project.id}
                          <span class="check-icon">✓</span>
                        {/if}
                      </div>
                      <div class="project-meta">
                        <span class="status-badge badge-{project.status}">
                          {project.status}
                        </span>
                        {#if project.models && project.models.length > 0}
                          <span class="models-badge"
                            >{project.models.length} model{project.models
                              .length !== 1
                              ? "s"
                              : ""}</span
                          >
                        {:else}
                          <span class="models-badge">No models yet</span>
                        {/if}
                      </div>
                      {#if project.status === "training"}
                        <p class="disabled-message">Currently training...</p>
                      {/if}
                    </button>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <div class="step-actions">
        <button class="btn btn-outline" on:click={previousStep}>
          ← Back
        </button>
        <div class="action-right">
          {#if !selectedProject && !createNewProject}
            <span class="hint-text">Select an option to continue</span>
          {/if}
          <button
            class="btn btn-primary"
            disabled={!canProceedStep2}
            on:click={nextStep}
          >
            Next →
          </button>
        </div>
      </div>
    {/if}

    {#if currentStep === 3}
      <!-- Step 3: Model Selection -->
      <div class="step-content">
        <h1>Choose Base Model</h1>
        <p class="step-subtitle">
          Select a model from the system project or continue from a previous
          training
        </p>

        {#if modelsLoading}
          <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading models...</p>
          </div>
        {:else if basedProjectModels.length === 0 && checkpointModels.length === 0}
          <!-- No models available -->
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <h3>No Models Available</h3>
            <p>
              You need to upload at least one model to the "Based" system
              project before you can start training.
            </p>
            <p class="hint-text">
              Navigate to the "Based" project and upload a pre-trained model
              (.pt file) to get started.
            </p>
          </div>
        {:else}
          <!-- Based Project Models -->
          {#if basedProjectModels.length > 0}
            <div class="model-category">
              <h3 class="category-header">
                <span class="category-icon">🔒</span>
                Base Models from System Project
              </h3>
              <div class="model-grid">
                {#each basedProjectModels as model}
                  <button
                    class="model-card"
                    class:selected={selectedBaseModel === model.id}
                    on:click={() => (selectedBaseModel = model.id)}
                  >
                    <div class="model-card-header">
                      <h3>{model.name}</h3>
                      {#if selectedBaseModel === model.id}
                        <span class="check-icon">✓</span>
                      {/if}
                    </div>
                    <div class="model-badge system-badge">System Model</div>
                    <div class="model-specs">
                      <div class="spec">
                        <span class="spec-label">Type:</span>
                        <span class="spec-value">{model.base_type}</span>
                      </div>
                      <div class="spec">
                        <span class="spec-label">Status:</span>
                        <span class="spec-value status-ready"
                          >{model.status}</span
                        >
                      </div>
                    </div>
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Checkpoint Models -->
          {#if checkpointModels.length > 0}
            <div class="model-category">
              <h3 class="category-header">
                <span class="category-icon">📊</span>
                Continue from Previous Training
              </h3>
              <div class="model-grid">
                {#each checkpointModels as model}
                  <button
                    class="model-card"
                    class:selected={selectedBaseModel === model.id}
                    on:click={() => (selectedBaseModel = model.id)}
                  >
                    <div class="model-card-header">
                      <h3>{model.name}</h3>
                      {#if selectedBaseModel === model.id}
                        <span class="check-icon">✓</span>
                      {/if}
                    </div>
                    <div class="model-badge checkpoint-badge">Checkpoint</div>
                    <div class="model-info">
                      <p class="project-name">
                        Project: {model.projectName || "Unknown"}
                      </p>
                    </div>
                    <div class="model-specs">
                      <div class="spec">
                        <span class="spec-label">Type:</span>
                        <span class="spec-value">{model.base_type}</span>
                      </div>
                      {#if model.metrics_json?.["metrics/mAP50-95(B)"]}
                        <div class="spec">
                          <span class="spec-label">mAP:</span>
                          <span class="spec-value"
                            >{(
                              model.metrics_json["metrics/mAP50-95(B)"] * 100
                            ).toFixed(2)}%</span
                          >
                        </div>
                      {/if}
                    </div>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      </div>

      <div class="step-actions">
        <button class="btn btn-outline" on:click={previousStep}>
          ← Back
        </button>
        <div class="action-right">
          {#if !selectedBaseModel}
            <span class="hint-text">Select a model to continue</span>
          {/if}
          <button
            class="btn btn-primary"
            disabled={!canProceedStep3}
            on:click={nextStep}
          >
            Next →
          </button>
        </div>
      </div>
    {/if}

    {#if currentStep === 4}
      <!-- Step 4: Configuration -->
      <div class="step-content">
        <h1>Training Configuration</h1>
        <p class="step-subtitle">Set training parameters and start training</p>

        <div class="config-form">
          <div class="form-section">
            <h3>Project & Model</h3>

            {#if selectedProject}
              <!-- Show existing project info -->
              <div class="info-box">
                <div class="info-item">
                  <span class="info-label">Using Project:</span>
                  <span class="info-value">{selectedProject.name}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">Existing Models:</span>
                  <span class="info-value"
                    >{selectedProject.models?.length || 0}</span
                  >
                </div>
              </div>
            {:else}
              <!-- Show project name input for new project -->
              <div class="form-group">
                <label for="projectName">Project Name</label>
                <input
                  id="projectName"
                  type="text"
                  bind:value={projectName}
                  placeholder="Enter project name"
                />
              </div>
            {/if}

            <div class="form-group">
              <label for="modelName">Model Name</label>
              <input
                id="modelName"
                type="text"
                bind:value={modelName}
                placeholder="Enter model name"
              />
              {#if selectedProject}
                <small class="form-hint"
                  >Creating a new model for this project</small
                >
              {/if}
            </div>
          </div>

          <div class="form-section">
            <h3>Training Parameters</h3>
            <div class="form-row">
              <div class="form-group">
                <label for="epochs">
                  Epochs
                  <span class="label-hint">(1-1000)</span>
                </label>
                <input
                  id="epochs"
                  type="number"
                  bind:value={epochs}
                  min="1"
                  max="1000"
                />
              </div>
              <div class="form-group">
                <label for="batchSize">
                  Batch Size
                  <span class="label-hint">(1-128)</span>
                </label>
                <input
                  id="batchSize"
                  type="number"
                  bind:value={batchSize}
                  min="1"
                  max="128"
                />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label for="imageSize">
                  Image Size
                  <span class="label-hint">(32-1280)</span>
                </label>
                <input
                  id="imageSize"
                  type="number"
                  bind:value={imageSize}
                  min="32"
                  max="1280"
                  step="32"
                />
              </div>
              <div class="form-group">
                <label for="learningRate">
                  Learning Rate
                  <span class="label-hint">(0.0001-1)</span>
                </label>
                <input
                  id="learningRate"
                  type="number"
                  bind:value={learningRate}
                  min="0.0001"
                  max="1"
                  step="0.001"
                />
              </div>
            </div>
          </div>

          <div class="summary-section">
            <h3>Training Summary</h3>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-label">Dataset:</span>
                <span class="summary-value">{selectedDataset?.name}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Model:</span>
                <span class="summary-value">
                  {[...basedProjectModels, ...checkpointModels].find(
                    (m) => m.id === selectedBaseModel,
                  )?.name || "N/A"}
                </span>
              </div>
              <div class="summary-item">
                <span class="summary-label">Images:</span>
                <span class="summary-value"
                  >{selectedDataset?.images_count || 0}</span
                >
              </div>
              <div class="summary-item">
                <span class="summary-label">Classes:</span>
                <span class="summary-value"
                  >{Object.keys(selectedDataset?.classes_json || {})
                    .length}</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="step-actions">
        <button class="btn btn-outline" on:click={previousStep}>
          ← Back
        </button>
        <button
          class="btn btn-primary btn-submit"
          disabled={!canSubmit || submitting}
          on:click={handleSubmit}
        >
          {submitting ? "Starting Training..." : "🚀 Start Training"}
        </button>
      </div>
    {/if}
  </div>
</div>

<!-- Override Consent Modal -->
{#if showOverrideModal}
  <div
    class="modal-overlay"
    on:click={cancelOverride}
    on:keydown={(e) => e.key === "Escape" && cancelOverride()}
    role="button"
    tabindex="-1"
  >
    <div
      class="modal-content"
      on:click|stopPropagation
      role="dialog"
      aria-modal="true"
    >
      <div class="modal-header">
        <h2>⚠️ Retrain Existing Project</h2>
        <button class="btn-close" on:click={cancelOverride}>✕</button>
      </div>

      <div class="modal-body">
        <p class="modal-intro">
          You are about to train a new model for project <strong
            >{selectedProject?.name}</strong
          >. Please confirm you understand the following:
        </p>

        <!-- Check All option -->
        <div class="check-all-section">
          <label class="check-all-label">
            <input
              type="checkbox"
              checked={allChecked}
              on:change={toggleCheckAll}
            />
            <span class="check-all-text">Check All</span>
          </label>
        </div>

        <div class="consent-checklist">
          <label class="consent-item">
            <input type="checkbox" bind:checked={overrideConsent.understood} />
            <div class="consent-text">
              <strong>New Training Session</strong>
              <p>
                This will create a new model and start a separate training job.
                It does not modify existing models.
              </p>
            </div>
          </label>

          <label class="consent-item">
            <input
              type="checkbox"
              bind:checked={overrideConsent.acceptNewModel}
            />
            <div class="consent-text">
              <strong>Existing Models Remain</strong>
              <p>
                All previously trained models in this project remain accessible
                and unchanged.
              </p>
            </div>
          </label>

          <label class="consent-item">
            <input
              type="checkbox"
              bind:checked={overrideConsent.confirmRetraining}
            />
            <div class="consent-text">
              <strong>Project Status Update</strong>
              <p>
                The project status will change to "training" during the training
                process.
              </p>
            </div>
          </label>
        </div>

        <div class="modal-info">
          <div class="info-row">
            <span class="info-label">Current Models:</span>
            <span class="info-value"
              >{selectedProject?.models?.length || 0}</span
            >
          </div>
          <div class="info-row">
            <span class="info-label">Project Status:</span>
            <span class="status-badge badge-{selectedProject?.status}"
              >{selectedProject?.status}</span
            >
          </div>
        </div>
      </div>

      <div class="modal-actions">
        <button class="btn btn-outline" on:click={cancelOverride}>
          Cancel
        </button>
        <button
          class="btn btn-primary"
          disabled={!overrideConsent.understood ||
            !overrideConsent.acceptNewModel ||
            !overrideConsent.confirmRetraining}
          on:click={confirmOverride}
        >
          Confirm & Continue
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* Scrollbar styling */
  .dataset-grid::-webkit-scrollbar,
  .model-grid::-webkit-scrollbar {
    width: 8px;
  }

  .dataset-grid::-webkit-scrollbar-track,
  .model-grid::-webkit-scrollbar-track {
    background: var(--color-bg-light1);
    border-radius: 4px;
  }

  .dataset-grid::-webkit-scrollbar-thumb,
  .model-grid::-webkit-scrollbar-thumb {
    background: var(--color-border);
    border-radius: 4px;
  }

  .dataset-grid::-webkit-scrollbar-thumb:hover,
  .model-grid::-webkit-scrollbar-thumb:hover {
    background: var(--color-text-secondary);
  }

  .training-wizard {
    display: flex;
    height: 100%;
    min-height: calc(100vh - 140px);
    max-height: calc(100vh - 140px);
    background: var(--color-bg-primary);
    box-shadow: var(--shadow-md); 
    overflow: hidden;
  }

  .wizard-sidebar {
    width: 320px;
    background: var(--color-bg-primary);
    padding: 2rem;
    display: flex;
    flex-direction: column;
  }

  .wizard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 3rem;
  }

  .wizard-header h2 {
    margin: 0;
    font-size: 1.5rem;
  }

  .btn-close {
    background: none;
    border: none;
    color: white;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    transition: background var(--transition-fast);
  }

  .btn-close:hover {
    background: var(--color-white-alpha-10);
  }

  .wizard-steps {
    background: var(--color-bg);
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .step-item {
    background: var(--color-bg-primary);
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border-radius: 8px;
    transition: all var(--transition-base);
    opacity: 1;
    background: none;
    border: none;
    color: var(--color-bg);
    width: 100%;
    text-align: left;
    cursor: default;
  }

  .step-item.clickable {
    cursor: pointer;
  }

  .step-item.clickable:hover {
    background: var(--color-white-alpha-5);
  }

  .step-item:disabled:not(.active) {
    cursor: not-allowed;
    opacity: 0.3;
  }

  .step-item.active {
    background: var(--color-white-alpha-10);
    opacity: 1;
  }

  .step-item.completed {
    opacity: 0.7;
  }

  .step-number {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--color-white-alpha-20);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    flex-shrink: 0;
  }

  .step-item.active .step-number {
    background: var(--color-accent);
  }

  .step-item.completed .step-number {
    background: var(--color-success);
  }

  .step-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .step-title {
    font-weight: 600;
    font-size: 1rem;
  }

  .step-desc {
    font-size: 0.875rem;
    opacity: 0.8;
  }

  .wizard-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
    background-color: var(--color-bg-card);
  }

  .step-content {
    flex: 1;
    padding: 2rem;
    overflow-y: auto;
    min-height: 0;
  }

  .step-content h1 {
    margin: 0 0 0.5rem 0;
    font-size: 1.75rem;
    color: var(--color-navy);
  }

  .step-subtitle {
    margin: 0 0 1.5rem 0;
    color: var(--color-text-secondary);
    font-size: 1rem;
  }

  .loading-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem;
    text-align: center;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid var(--color-border-light);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .dataset-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
    overflow-y: auto;
    padding-right: 0.5rem;
  }

  @media (min-width: 1200px) {
    .dataset-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .dataset-card {
    background: white;
    border: 2px solid var(--color-border);
    border-radius: 8px;
    padding: 1rem;
    text-align: left;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .dataset-card:hover {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }

  .dataset-card.selected {
    border-color: var(--color-accent);
    background: var(--color-accent-alpha-5);
    box-shadow: 0 0 0 3px var(--color-accent-alpha-10);
  }

  .dataset-card:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    pointer-events: none;
  }

  .dataset-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .dataset-card-header h3 {
    margin: 0;
    font-size: 1.125rem;
    color: var(--color-navy);
  }

  .check-icon {
    color: var(--color-accent);
    font-size: 1.5rem;
    font-weight: bold;
  }

  .dataset-description {
    margin: 0 0 1rem 0;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .dataset-stats {
    display: flex;
    gap: 1rem;
  }

  .stat {
    display: flex;
    gap: 0.25rem;
    font-size: 0.875rem;
  }

  .stat-label {
    color: var(--color-text-secondary);
  }

  .stat-value {
    font-weight: 600;
    color: var(--color-navy);
  }

  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
    overflow-y: auto;
    padding-right: 0.5rem;
  }

  @media (min-width: 1200px) {
    .model-grid {
      grid-template-columns: repeat(5, 1fr);
    }
  }

  .model-card {
    background: var(--color-bg-card);
    border: 2px solid var(--color-border);
    border-radius: 8px;
    padding: 1rem;
    text-align: left;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .model-card:hover {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }

  .model-card.selected {
    border-color: var(--color-accent);
    background: var(--color-accent-alpha-5);
    box-shadow: 0 0 0 3px var(--color-accent-alpha-10);
  }

  .model-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .model-card-header h3 {
    margin: 0;
    font-size: 1.25rem;
    color: var(--color-navy);
    font-weight: 700;
  }

  .model-description {
    margin: 0 0 1rem 0;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.4;
  }

  .model-specs {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .spec {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
  }

  .spec-label {
    color: var(--color-text-secondary);
  }

  .spec-value {
    font-weight: 600;
    color: var(--color-navy);
  }

  .model-options {
    padding: 1rem;
    background: var(--color-bg-light1);
    border-radius: 8px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.95rem;
  }

  .checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .config-form {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .form-section {
    background: var(--color-bg-primary);
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid var(--color-border);
  }

  .form-section h3 {
    margin: 0 0 1rem 0;
    color: var(--color-navy);
    font-size: 1.125rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .form-group:last-child {
    margin-bottom: 0;
  }

  .form-group label {
    font-weight: 500;
    color: var(--color-navy);
    font-size: 0.95rem;
  }

  .label-hint {
    color: var(--color-text-secondary);
    font-weight: 400;
    font-size: 0.875rem;
  }

  .form-group input {
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: 1rem;
    transition: border-color var(--transition-fast);
  }

  .form-group input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .summary-section {
    background: var(--color-info-alpha-10);
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid var(--color-info-alpha-30);
  }

  .summary-section h3 {
    margin: 0 0 1rem 0;
    color: var(--color-navy);
    font-size: 1.125rem;
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

  .summary-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .summary-label {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .summary-value {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-navy);
  }

  .step-actions {
    padding: 1rem 2rem;
    border-top: 1px solid var(--color-border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--color-bg-primary);
    flex-shrink: 0;
  }

  .action-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .hint-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-size: 1rem;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-base);
    border: none;
  }

  .btn-outline {
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    color: var(--color-navy);
  }

  .btn-outline:hover:not(:disabled) {
    background: var(--color-bg-light1);
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-submit {
    padding: 0.75rem 2rem;
    font-size: 1.125rem;
  }

  /* Project Selection Styles */
  .project-options {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .project-option-card {
    background: var(--color-bg-card);
    border: 2px solid var(--color-border);
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all var(--transition-base);
    position: relative;
  }

  .project-option-card.new-project {
    background: var(--color-bg-primary);
  }

  .project-option-card:hover {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }

  .project-option-card.selected {
    border-color: var(--color-accent);
    background: var(--color-accent-alpha-5);
    box-shadow: 0 0 0 3px var(--color-accent-alpha-10);
  }

  .option-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
  }

  .project-option-card h3 {
    margin: 0 0 0.5rem 0;
    color: var(--color-navy);
    font-size: 1.5rem;
  }

  .project-option-card p {
    margin: 0;
    color: var(--color-text-secondary);
  }

  .divider {
    text-align: center;
    position: relative;
    margin: 1rem 0;
  }

  .divider span {
    background: var(--color-bg);
    padding: 0 1rem;
    color: var(--color-text-secondary);
    font-weight: 600;
    position: relative;
    z-index: 1;
  }

  .divider::before {
    content: "";
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--color-border);
  }

  .existing-projects-section h3 {
    margin: 0 0 0.5rem 0;
    color: var(--color-navy);
    font-size: 1.25rem;
  }

  .section-desc {
    margin: 0 0 1.5rem 0;
    color: var(--color-text-secondary);
    font-size: 0.95rem;
  }

  .projects-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
  }

  .project-card {
    background: var(--color-bg-card);
    border: 2px solid var(--color-border);
    border-radius: 8px;
    padding: 1rem;
    text-align: left;
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .project-card:hover:not(.disabled) {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-lg);
  }

  .project-card.selected {
    border-color: var(--color-accent);
    background: var(--color-accent-alpha-5);
    box-shadow: 0 0 0 3px var(--color-accent-alpha-10);
  }

  .project-card.disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: var(--color-bg-light1);
  }

  .project-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .project-card-header h4 {
    margin: 0;
    font-size: 1.125rem;
    color: var(--color-navy);
  }

  .project-meta {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .status-badge {
    color: var(--color-bg);
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .badge-created {
    background: var(--color-info-alpha-10);
    color: var(--color-info-dark);
  }

  .badge-training {
    background: var(--color-warning-alpha-10);
    color: var(--color-warning-dark);
  }

  .badge-trained {
    background: var(--color-success-alpha-10);
    color: var(--color-success);
  }

  .badge-failed {
    background: var(--color-danger-alpha-10);
    color: var(--color-danger-dark);
  }

  .models-badge {
    padding: 0.25rem 0.75rem;
    background: var(--color-bg-light1);
    border-radius: 12px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .disabled-message {
    margin: 0.5rem 0 0 0;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    font-style: italic;
  }

  .info-box {
    background: var(--color-info-alpha-10);
    padding: 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    border: 1px solid var(--color-info-alpha-30);
  }

  .info-box .info-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .info-box .info-item:last-child {
    margin-bottom: 0;
  }

  .info-label {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .info-value {
    font-weight: 600;
    color: var(--color-navy);
  }

  .form-hint {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  /* Modal Styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .modal-content {
    background: var(--color-bg-card);
    border-radius: 12px;
    max-width: 600px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  }

  .modal-header {
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--color-navy);
  }

  .modal-body {
    padding: 1.5rem;
  }

  .modal-intro {
    margin: 0 0 1.5rem 0;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .check-all-section {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: var(--color-bg-primary);
    border-radius: 8px;
    border: 2px solid #bae6fd;
  }

  .check-all-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    margin: 0;
  }

  .check-all-label input[type="checkbox"] {
    width: 20px;
    height: 20px;
    cursor: pointer;
    flex-shrink: 0;
  }

  .check-all-text {
    font-weight: 600;
    color: var(--color-navy);
    font-size: 1rem;
  }

  .consent-checklist {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .consent-item {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    background: var(--color-bg-secondary);
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .consent-item:hover {
    background: #f3f4f6;
  }

  .consent-item input[type="checkbox"] {
    width: 20px;
    height: 20px;
    cursor: pointer;
    flex-shrink: 0;
    margin-top: 0.25rem;
  }

  .consent-text {
    flex: 1;
  }

  .consent-text strong {
    display: block;
    margin-bottom: 0.25rem;
    color: var(--color-navy);
  }

  .consent-text p {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .modal-info {
    background: var(--color-bg-secondary);
    padding: 1rem;
    border-radius: 6px;
    border: 1px solid #bfdbfe;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .info-row:last-child {
    margin-bottom: 0;
  }

  .modal-actions {
    padding: 1.5rem;
    border-top: 1px solid #e5e7eb;
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
  }

  /* Model Category Styles */
  .category-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e5e7eb;
  }

  .category-header:first-of-type {
    margin-top: 0;
  }

  .category-icon {
    font-size: 1.25rem;
  }

  .category-header h3 {
    margin: 0;
    font-size: 1.125rem;
    color: var(--color-navy);
    font-weight: 600;
  }

  .category-count {
    margin-left: auto;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    font-weight: 400;
  }

  /* Model Badge Styles */
  .model-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .system-badge {
    background: #fef3c7;
    color: #92400e;
  }

  .checkpoint-badge {
    background: #dbeafe;
    color: #1e40af;
  }

  /* Empty State Styles */
  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
    background: #f9fafb;
    border-radius: 12px;
    border: 2px dashed #e5e7eb;
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
    opacity: 0.5;
  }

  .empty-state h3 {
    margin: 0 0 0.5rem 0;
    color: var(--color-navy);
    font-size: 1.5rem;
  }

  .empty-state p {
    margin: 0;
    color: var(--color-text-secondary);
    line-height: 1.6;
    max-width: 500px;
    margin: 0 auto;
  }

  /* Model Card Additional Styles */
  .project-name {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin-top: 0.25rem;
  }

  .model-metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #e5e7eb;
  }

  .metric-item {
    text-align: center;
  }

  .metric-label {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  .metric-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-navy);
    margin-top: 0.25rem;
  }
</style>
