<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { projectsAPI } from "../../lib/api/projects";
  import StatCard from "../../lib/components/shared/StatCard.svelte";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import EmptyState from "../../lib/components/shared/EmptyState.svelte";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import ConfirmDeleteModal from "../../lib/components/shared/ConfirmDeleteModal.svelte";
  import { uiStore } from "../../lib/stores/uiStore";
  import type { Project, DeleteConfirmation } from "@/lib/types";

  let projects: Project[] = [];
  let loading = true;
  let searchTerm = "";
  let view: "card" | "list" = "card";
  let selectedStatFilter: string | null = null;
  let statsAnimated = false;

  // Delete confirmation modal state
  let showDeleteModal = false;
  let projectToDelete: Project | null = null;
  let deleteConfirmation: DeleteConfirmation | null = null;

  // Statistics calculations
  $: totalProjects = projects.length;
  $: activeProjects = projects.filter((p) => p.status === "training").length;
  $: completedJobs = 0; // Would need backend support
  $: totalModels = 0; // Would need backend support
  $: avgAccuracy = 0; // Would need backend support
  $: trainedProjects = projects.filter((p) => p.status === "trained").length;

  // Filtering logic
  $: filteredProjects = projects.filter((project) => {
    const matchesSearch =
      searchTerm === "" ||
      project.name.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStat =
      selectedStatFilter === null ||
      (selectedStatFilter === "training" && project.status === "training") ||
      (selectedStatFilter === "trained" && project.status === "trained");

    return matchesSearch && matchesStat;
  });

  // Auto-reset filter when search changes
  $: if (searchTerm) {
    selectedStatFilter = null;
  }

  onMount(async () => {
    await loadProjects();
    setTimeout(() => (statsAnimated = true), 100);
  });

  async function loadProjects() {
    try {
      loading = true;
      projects = await projectsAPI.list();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to load projects", "error");
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

  function handleCreateProject() {
    navigate("/projects/new");
  }

  function handleProjectClick(projectId: number) {
    navigate(`/projects/${projectId}`);
  }

  function handleViewChange(newView: "card" | "list") {
    view = newView;
  }

  function getStatusClass(status: string): string {
    const statusMap: Record<string, string> = {
      created: "badge-info",
      training: "badge-running",
      trained: "badge-completed",
      failed: "badge-failed",
    };
    return statusMap[status] || "badge-neutral";
  }

  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString();
  }

  async function handleDeleteProject(project: Project, event: MouseEvent) {
    event.stopPropagation();

    if (project.is_system) {
      uiStore.showToast("System projects cannot be deleted", "error");
      return;
    }

    projectToDelete = project;

    // First attempt: check if confirmation is needed
    try {
      const result = await projectsAPI.delete(project.id, false);
      if (result && "requires_confirmation" in result) {
        deleteConfirmation = result;
        showDeleteModal = true;
      } else {
        // No related records, deleted successfully
        uiStore.showToast(
          `Project "${project.name}" deleted successfully`,
          "success",
        );
        await loadProjects();
      }
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to delete project", "error");
    }
  }

  async function confirmDelete() {
    if (!projectToDelete) return;

    try {
      await projectsAPI.delete(projectToDelete.id, true);
      uiStore.showToast(
        `Project "${projectToDelete.name}" deleted successfully`,
        "success",
      );
      showDeleteModal = false;
      projectToDelete = null;
      deleteConfirmation = null;
      await loadProjects();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to delete project", "error");
    }
  }

  function cancelDelete() {
    showDeleteModal = false;
    projectToDelete = null;
    deleteConfirmation = null;
  }
</script>

<div class="page">
  <div class="page-header">
    <div class="header-content">
      <h1>Projects</h1>
      <p class="subtitle">Create and manage training projects</p>
    </div>
    <button class="btn btn-primary" on:click={handleCreateProject}>
      + Create Project
    </button>
  </div>

  {#if loading}
    <LoadingSpinner message="Loading projects..." />
  {:else}
    <!-- Statistics Grid -->
    {#if projects.length > 0}
      <div class="stats-grid">
        <StatCard
          icon="📊"
          value={totalProjects}
          label="Total Projects"
          animate={statsAnimated}
          ariaLabel="Total number of projects"
        />
        <StatCard
          icon="⚡"
          value={activeProjects}
          label="Training"
          breakdown="{trainedProjects} trained"
          isClickable={true}
          filterType="training"
          isActive={selectedStatFilter === "training"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
        <StatCard
          icon="🏁"
          value={completedJobs}
          label="Completed Jobs"
          animate={statsAnimated}
          ariaLabel="Total completed training jobs"
        />
        <StatCard
          icon="🤖"
          value={totalModels}
          label="Total Models"
          animate={statsAnimated}
          ariaLabel="Total trained models"
        />
        <StatCard
          icon="🎯"
          value={avgAccuracy > 0 ? `${avgAccuracy.toFixed(1)}%` : "0"}
          label="Avg Accuracy"
          animate={statsAnimated}
          ariaLabel="Average model accuracy"
        />
        <StatCard
          icon="✅"
          value={trainedProjects}
          label="Trained"
          isClickable={true}
          filterType="trained"
          isActive={selectedStatFilter === "trained"}
          animate={statsAnimated}
          on:click={(e) => handleStatClick(e.detail)}
        />
      </div>
    {/if}

    <!-- Controls -->
    {#if projects.length > 0}
      <div class="controls">
        <input
          type="text"
          class="search-input"
          placeholder="🔍 Search projects..."
          bind:value={searchTerm}
        />
        <ViewToggle {view} onChange={handleViewChange} />
      </div>
    {/if}

    <!-- Projects List -->
    {#if filteredProjects.length === 0}
      <EmptyState
        icon={searchTerm || selectedStatFilter ? "🔍" : "📂"}
        title={searchTerm || selectedStatFilter
          ? "No Projects Found"
          : "Create Your First Project"}
        message={searchTerm || selectedStatFilter
          ? "No projects match your search criteria. Try different keywords or clear filters to see all available projects."
          : "Projects organize your datasets, models, and detection tasks. Create a project to get started with object detection and training workflows."}
        actionLabel={searchTerm || selectedStatFilter
          ? "Clear Search"
          : "Create Project"}
        onAction={searchTerm || selectedStatFilter
          ? () => {
              searchTerm = "";
              selectedStatFilter = null;
            }
          : handleCreateProject}
      />
    {:else if view === "card"}
      <div class="projects-grid">
        {#each filteredProjects as project (project.id)}
          <div
            class="project-card"
            on:click={() => handleProjectClick(project.id)}
            on:keydown={(e) =>
              e.key === "Enter" && handleProjectClick(project.id)}
            role="button"
            tabindex="0"
          >
            <div class="card-header">
              <div class="card-title-row">
                <h3>{project.name}</h3>
                {#if project.is_system}
                  <span class="system-badge" title="System Project"
                    >🔒 SYSTEM</span
                  >
                {/if}
              </div>
              <span class="status-badge badge-{project.status}">
                {project.status}
              </span>
            </div>
            <div class="project-stats">
              <div class="stat-item">
                <span class="stat-label">Task:</span>
                <span class="stat-value">{project.task_type}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Dataset:</span>
                <span class="stat-value">
                  {project.dataset_id ? `#${project.dataset_id}` : "None"}
                </span>
              </div>
            </div>
            <div class="card-footer">
              <span class="date-text"
                >Created {formatDate(project.created_at)}</span
              >
              {#if !project.is_system}
                <button
                  class="delete-btn"
                  on:click={(e) => handleDeleteProject(project, e)}
                  title="Delete project"
                >
                  🗑️
                </button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div class="projects-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Models</th>
              <th>Jobs</th>
              <th>Avg Accuracy</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredProjects as project (project.id)}
              <tr
                on:click={() => handleProjectClick(project.id)}
                class="clickable-row"
              >
                <td>
                  <div class="table-name">
                    <strong>{project.name}</strong>
                    {#if project.is_system}
                      <span class="system-badge-small" title="System Project"
                        >🔒</span
                      >
                    {/if}
                  </div>
                </td>
                <td>
                  <span class="status-badge badge-{project.status}">
                    {project.status}
                  </span>
                </td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td>{formatDate(project.created_at)}</td>
                <td>
                  {#if !project.is_system}
                    <button
                      class="delete-btn-table"
                      on:click={(e) => handleDeleteProject(project, e)}
                      title="Delete project"
                    >
                      🗑️
                    </button>
                  {:else}
                    <span class="text-muted">-</span>
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

<!-- Delete Confirmation Modal -->
<ConfirmDeleteModal
  show={showDeleteModal}
  projectName={projectToDelete?.name || ""}
  modelsCount={deleteConfirmation?.models_count || 0}
  jobsCount={deleteConfirmation?.jobs_count || 0}
  onCancel={cancelDelete}
  onConfirm={confirmDelete}
/>

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

  .btn {
    padding: var(--spacing-md) var(--spacing-xl);
    border-radius: var(--radius-md);
    font-weight: 600;
    font-size: var(--font-size-base);
    transition: all var(--transition-fast);
  }

  .btn-primary {
    background-color: var(--color-accent);
    color: var(--color-white);
    border: none;
    cursor: pointer;
  }

  .btn-primary:hover {
    background-color: var(--color-accent-dark);
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
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

  /* Card Grid */
  .projects-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  @media (min-width: 768px) {
    .projects-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-lg);
    }
  }

  @media (min-width: 1200px) {
    .projects-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  @media (min-width: 1600px) {
    .projects-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .project-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    border: 2px solid transparent;
  }

  .project-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-md);
  }

  .card-header h3 {
    font-size: var(--font-size-lg);
    margin: 0;
  }

  .status-badge {
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
  }

  .project-description {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-md);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .project-stats {
    display: flex;
    gap: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-light-grey);
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .stat-label {
    font-size: var(--font-size-xs);
    color: var(--color-grey);
  }

  .stat-value {
    font-size: var(--font-size-lg);
    font-weight: 600;
    color: var(--color-navy);
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .date-text {
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
  }

  /* Table View */
  .projects-table {
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

    .projects-grid {
      grid-template-columns: 1fr;
    }

    .projects-table {
      overflow-x: auto;
    }

    table {
      min-width: 600px;
    }
  }

  .badge-trained {
    background: var(--color-success-alpha-10);
    color: var(--color-success-dark);
  }

  /* System Project Badge */
  .card-title-row {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    flex-wrap: wrap;
  }

  .system-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    background: var(--color-warning-alpha-10);
    border: 1px solid var(--color-warning-alpha-30);
    border-radius: var(--border-radius-sm);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-warning);
  }

  .system-badge-small {
    margin-left: 0.5rem;
    font-size: 0.9rem;
  }

  /* Delete Button */
  .delete-btn {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0.25rem;
    opacity: 0.6;
    transition: all var(--transition-fast);
  }

  .delete-btn:hover {
    opacity: 1;
    transform: scale(1.1);
  }

  .delete-btn-table {
    background: none;
    border: none;
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    opacity: 0.6;
    transition: all var(--transition-fast);
  }

  .delete-btn-table:hover {
    opacity: 1;
    transform: scale(1.2);
  }

  .text-muted {
    color: var(--color-text-secondary);
    font-size: 0.9rem;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  /* Checkbox Label */
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    cursor: pointer;
  }

  .checkbox-label input[type="checkbox"] {
    width: 1.25rem;
    height: 1.25rem;
    cursor: pointer;
  }
</style>
