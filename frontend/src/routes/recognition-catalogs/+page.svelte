<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { recognitionCatalogsAPI } from "../../lib/api/recognitionCatalogs";
  import { uiStore } from "../../lib/stores/uiStore";
  import ViewToggle from "../../lib/components/shared/ViewToggle.svelte";
  import type { RecognitionCatalog } from "../../lib/types/recognition";

  // State variables
  let catalogs: RecognitionCatalog[] = [];
  let categories: string[] = [];
  let loading = false;
  let searchTerm = "";
  let selectedCategory = "all";
  let view: "card" | "list" = "card";
  let sortBy = "created_at";
  let sortOrder: "asc" | "desc" = "desc";

  // Modal state
  let showCreateModal = false;
  let creating = false;
  let formData = {
    name: "",
    description: "",
    category: "",
  };

  onMount(async () => {
    const savedView = localStorage.getItem("recognitionCatalogsViewMode");
    if (savedView === "list" || savedView === "card") {
      view = savedView;
    }
    await loadCatalogs();
    await loadCategories();
  });

  async function loadCatalogs() {
    loading = true;
    try {
      catalogs = await recognitionCatalogsAPI.listCatalogs();
    } catch (error) {
      uiStore.showToast("Failed to load recognition catalogs", "error");
      console.error("Error loading catalogs:", error);
    } finally {
      loading = false;
    }
  }

  async function loadCategories() {
    try {
      categories = await recognitionCatalogsAPI.listCategories();
    } catch (error) {
      console.error("Error loading categories:", error);
    }
  }

  function handleViewChange(newView: "card" | "list") {
    view = newView;
    localStorage.setItem("recognitionCatalogsViewMode", newView);
  }

  function openCreateModal() {
    formData = {
      name: "",
      description: "",
      category: "",
    };
    showCreateModal = true;
  }

  function closeCreateModal() {
    showCreateModal = false;
    formData = {
      name: "",
      description: "",
      category: "",
    };
  }

  async function handleCreate() {
    if (!formData.name || !formData.category) {
      uiStore.showToast("Please fill in all required fields", "error");
      return;
    }

    creating = true;
    try {
      await recognitionCatalogsAPI.createCatalog({
        name: formData.name,
        description: formData.description || undefined,
        category: formData.category,
      });

      uiStore.showToast("Recognition catalog created successfully", "success");
      closeCreateModal();
      await loadCatalogs();
      await loadCategories();
    } catch (error) {
      uiStore.showToast("Failed to create catalog", "error");
      console.error("Error creating catalog:", error);
    } finally {
      creating = false;
    }
  }

  async function handleDelete(catalogId: number, catalogName: string) {
    if (
      !confirm(
        `Are you sure you want to delete "${catalogName}"? This will delete all labels and images.`
      )
    ) {
      return;
    }

    try {
      await recognitionCatalogsAPI.deleteCatalog(catalogId);
      uiStore.showToast("Catalog deleted successfully", "success");
      await loadCatalogs();
    } catch (error) {
      uiStore.showToast("Failed to delete catalog", "error");
      console.error("Error deleting catalog:", error);
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
  $: totalCatalogs = catalogs.length;
  $: totalImages = catalogs.reduce((sum, c) => sum + (c.image_count || 0), 0);
  $: totalLabels = catalogs.reduce((sum, c) => sum + (c.label_count || 0), 0);

  // Computed filtered and sorted catalogs
  $: filteredCatalogs = catalogs
    .filter((catalog) => {
      const matchesSearch =
        catalog.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (catalog.description || "")
          .toLowerCase()
          .includes(searchTerm.toLowerCase()) ||
        catalog.category.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory =
        selectedCategory === "all" || catalog.category === selectedCategory;
      return matchesSearch && matchesCategory;
    })
    .sort((a, b) => {
      let aValue: any = a[sortBy as keyof RecognitionCatalog];
      let bValue: any = b[sortBy as keyof RecognitionCatalog];

      if (sortBy === "created_at" || sortBy === "updated_at") {
        aValue = new Date(aValue).getTime();
        bValue = new Date(bValue).getTime();
      }

      if (sortOrder === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });
</script>

<div class="recognition-catalogs-page">
  <!-- Header -->
  <div class="page-header">
    <div class="header-left">
      <h1>🎭 Recognition Catalog</h1>
      <p class="subtitle">Manage face and object recognition databases</p>
    </div>
    <div class="header-actions">
      <button class="btn btn-primary" on:click={openCreateModal}>
        <span class="icon">➕</span>
        New Catalog
      </button>
    </div>
  </div>

  <!-- Statistics -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-icon">📚</div>
      <div class="stat-content">
        <div class="stat-value">{totalCatalogs}</div>
        <div class="stat-label">Total Catalogs</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">🏷️</div>
      <div class="stat-content">
        <div class="stat-value">{totalLabels}</div>
        <div class="stat-label">Total Labels</div>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">🖼️</div>
      <div class="stat-content">
        <div class="stat-value">{totalImages}</div>
        <div class="stat-label">Total Images</div>
      </div>
    </div>
  </div>

  <!-- Filters and View Toggle -->
  <div class="controls-bar">
    <div class="filters">
      <input
        type="text"
        placeholder="Search catalogs..."
        bind:value={searchTerm}
        class="search-input"
      />
      <select bind:value={selectedCategory} class="filter-select">
        <option value="all">All Categories</option>
        {#each categories as category}
          <option value={category}>{category}</option>
        {/each}
      </select>
    </div>
    <ViewToggle {view} onChange={handleViewChange} />
  </div>

  <!-- Loading State -->
  {#if loading}
    <div class="loading-container">
      <div class="spinner"></div>
      <p>Loading catalogs...</p>
    </div>
  {:else if filteredCatalogs.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🎭</div>
      <h2>No recognition catalogs found</h2>
      <p>
        {#if searchTerm || selectedCategory !== "all"}
          Try adjusting your filters or create a new catalog.
        {:else}
          Get started by creating your first recognition catalog.
        {/if}
      </p>
      {#if !searchTerm && selectedCategory === "all"}
        <button class="btn btn-primary" on:click={openCreateModal}>
          Create First Catalog
        </button>
      {/if}
    </div>
  {:else if view === "card"}
    <!-- Card View -->
    <div class="catalogs-grid">
      {#each filteredCatalogs as catalog}
        <div
          class="catalog-card"
          on:click={() => {
            navigate(`/recognition-catalogs/${catalog.id}`);
          }}
        >
          <div class="card-header">
            <h3>{catalog.name}</h3>
            <span class="category-badge">{catalog.category}</span>
          </div>
          {#if catalog.description}
            <p class="description">{catalog.description}</p>
          {/if}
          <div class="card-stats">
            <div class="stat-item">
              <span class="stat-icon">🏷️</span>
              <span>{catalog.label_count} labels</span>
            </div>
            <div class="stat-item">
              <span class="stat-icon">🖼️</span>
              <span>{catalog.image_count} images</span>
            </div>
          </div>
          <div class="card-footer">
            <span class="date">Created {formatDate(catalog.created_at)}</span>
            <button
              class="btn-icon btn-danger"
              on:click|stopPropagation={() =>
                handleDelete(catalog.id, catalog.name)}
              title="Delete catalog"
            >
              🗑️
            </button>
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
            <th on:click={() => handleSort("name")} class="sortable">
              Name {getSortIndicator("name")}
            </th>
            <th on:click={() => handleSort("category")} class="sortable">
              Category {getSortIndicator("category")}
            </th>
            <th on:click={() => handleSort("label_count")} class="sortable">
              Labels {getSortIndicator("label_count")}
            </th>
            <th on:click={() => handleSort("image_count")} class="sortable">
              Images {getSortIndicator("image_count")}
            </th>
            <th on:click={() => handleSort("created_at")} class="sortable">
              Created {getSortIndicator("created_at")}
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredCatalogs as catalog}
            <tr
              on:click={() => navigate(`/recognition-catalogs/${catalog.id}`)}
            >
              <td>
                <strong>{catalog.name}</strong>
                {#if catalog.description}
                  <br />
                  <span class="text-muted">{catalog.description}</span>
                {/if}
              </td>
              <td>
                <span class="category-badge">{catalog.category}</span>
              </td>
              <td>{catalog.label_count}</td>
              <td>{catalog.image_count}</td>
              <td>{formatDate(catalog.created_at)}</td>
              <td>
                <button
                  class="btn-icon btn-danger"
                  on:click|stopPropagation={() =>
                    handleDelete(catalog.id, catalog.name)}
                  title="Delete catalog"
                >
                  🗑️
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Create Modal -->
{#if showCreateModal}
  <div class="modal-backdrop" on:click={closeCreateModal}>
    <div class="modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Create Recognition Catalog</h2>
        <button class="close-btn" on:click={closeCreateModal}>&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="catalog-name">Name *</label>
          <input
            id="catalog-name"
            type="text"
            bind:value={formData.name}
            placeholder="e.g., Office Employees"
            required
          />
        </div>
        <div class="form-group">
          <label for="catalog-category">Category *</label>
          <input
            id="catalog-category"
            type="text"
            bind:value={formData.category}
            placeholder="e.g., Office Faces, VVIP Database"
            list="category-suggestions"
            required
          />
          <datalist id="category-suggestions">
            {#each categories as category}
              <option value={category}></option>
            {/each}
          </datalist>
        </div>
        <div class="form-group">
          <label for="catalog-description">Description</label>
          <textarea
            id="catalog-description"
            bind:value={formData.description}
            placeholder="Optional description..."
            rows="3"
          ></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-secondary"
          on:click={closeCreateModal}
          disabled={creating}
        >
          Cancel
        </button>
        <button
          class="btn btn-primary"
          on:click={handleCreate}
          disabled={creating}
        >
          {creating ? "Creating..." : "Create Catalog"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .recognition-catalogs-page {
    padding: 1.5rem;
    width: 100%;
    max-width: 100%;
  }

  @media (min-width: 768px) {
    .recognition-catalogs-page {
      padding: 2rem;
    }
  }

  @media (min-width: 1920px) {
    .recognition-catalogs-page {
      padding: 2rem 3rem;
    }
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
  }

  .header-left h1 {
    margin: 0;
    font-size: 2rem;
    color: var(--color-navy);
  }

  .subtitle {
    margin: 0.5rem 0 0 0;
    color: var(--color-text-secondary);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  @media (min-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
      margin-bottom: 2rem;
    }
  }

  .stat-card {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .stat-icon {
    font-size: 2.5rem;
  }

  .stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--color-navy);
  }

  .stat-label {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .controls-bar {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  @media (min-width: 768px) {
    .controls-bar {
      flex-direction: row;
      justify-content: space-between;
      align-items: center;
    }
  }

  .filters {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 1;
  }

  @media (min-width: 640px) {
    .filters {
      flex-direction: row;
      gap: 1rem;
    }
  }

  .search-input {
    flex: 1;
    width: 100%;
  }

  @media (min-width: 640px) {
    .search-input {
      max-width: 400px;
    }
  }

  .filter-select {
    width: 100%;
    min-width: unset;
  }

  @media (min-width: 640px) {
    .filter-select {
      width: auto;
      min-width: 200px;
    }
  }

  .catalogs-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  @media (min-width: 768px) {
    .catalogs-grid {
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1.5rem;
    }
  }

  @media (min-width: 1440px) {
    .catalogs-grid {
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    }
  }

  @media (min-width: 1920px) {
    .catalogs-grid {
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 2rem;
    }
  }

  .catalog-card {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition:
      transform 0.2s,
      box-shadow 0.2s;
  }

  .catalog-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    margin-bottom: 0.75rem;
  }

  .card-header h3 {
    margin: 0;
    font-size: 1.25rem;
    color: var(--color-navy);
  }

  .category-badge {
    background: var(--color-accent);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .description {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    margin-bottom: 1rem;
    line-height: 1.5;
  }

  .card-stats {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .stat-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .date {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .loading-container {
    text-align: center;
    padding: 4rem 2rem;
  }

  .spinner {
    margin: 0 auto 1rem;
  }

  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
  }

  .table-container {
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table thead {
    background: var(--color-navy);
    color: white;
  }

  .data-table th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
  }

  .data-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .data-table th.sortable:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .data-table tbody tr {
    border-bottom: 1px solid var(--color-border);
    cursor: pointer;
    transition: background 0.2s;
  }

  .data-table tbody tr:hover {
    background: var(--color-background);
  }

  .data-table td {
    padding: 1rem;
  }

  .text-muted {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.5rem;
    font-size: 1.25rem;
    transition: transform 0.2s;
  }

  .btn-icon:hover {
    transform: scale(1.2);
  }

  .btn-danger:hover {
    filter: brightness(1.2);
  }

  /* Modal styles */
  .modal-backdrop {
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
  }

  .modal {
    background: white;
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--color-navy);
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    line-height: 1;
  }

  .modal-body {
    padding: 1.5rem;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: var(--color-navy);
  }

  .form-group input,
  .form-group textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 1rem;
  }

  .form-group input:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid var(--color-border);
  }
</style>
