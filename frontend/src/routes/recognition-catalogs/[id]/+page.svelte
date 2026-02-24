<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router";
  import { location } from "svelte-spa-router";
  import { recognitionCatalogsAPI } from "../../../lib/api/recognitionCatalogs";
  import { uiStore } from "../../../lib/stores/uiStore";
  import type {
    RecognitionCatalogDetail,
    RecognitionLabel,
    RecognitionLabelDetail,
    SimilaritySearchResponse,
  } from "../../../lib/types/recognition";

  export let id: number | undefined = undefined;

  // Extract id from URL path and load dataset
  $: if ($location) {
    const match = $location.match(/^\/recognition-catalogs\/(\d+)/);
    if (match && match[1]) {
      const parsedId = parseInt(match[1]);
      if (parsedId !== id) {
        id = parsedId;
      }
    }
  }

  let catalog: RecognitionCatalogDetail | null = null;
  let loading = false;
  let activeTab: "labels" | "search" | "semantic" = "labels";

  // Label management
  let showAddLabelModal = false;
  let showUploadModal = false;
  let showZipUploadModal = false;
  let showLabelDetailModal = false;
  let selectedLabel: RecognitionLabel | null = null;
  let selectedLabelDetail: RecognitionLabelDetail | null = null;
  let labelFormData = { label_name: "", description: "" };
  let uploadFiles: FileList | null = null;
  let zipFile: File | null = null;
  let uploading = false;
  let uploadingZip = false;
  let uploadProgress = {
    show: false,
    step: '',
    message: ''
  };

  // View and filter
  let viewMode: "card" | "list" | "table" = "card";
  let searchQuery = "";

  // Similarity search
  let searchFile: File | null = null;
  let searchResults: SimilaritySearchResponse | null = null;
  let searching = false;
  let topK = 5;
  let threshold = 0.5;

  // Semantic text search
  let textQuery = "";
  let semanticResults: SimilaritySearchResponse | null = null;
  let searchingText = false;
  let semanticTopK = 5;
  let semanticThreshold = 0.2;

  // Reactive statement to load catalog when ID changes
  $: if (id !== undefined && !isNaN(id)) {
    loadCatalog();
  }

  // Filter labels based on search query
  $: filteredLabels =
    catalog?.labels?.filter((label) =>
      label.label_name.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  async function loadCatalog() {
    if (id === undefined || isNaN(id)) return;

    loading = true;
    try {
      catalog = await recognitionCatalogsAPI.getCatalog(id);
    } catch (error: any) {
      uiStore.showToast(
        error.response?.data?.detail || "Failed to load catalog",
        "error"
      );
      console.error("Error loading catalog:", error);
    } finally {
      loading = false;
    }
  }

  async function loadLabelDetail(labelId: number) {
    if (id === undefined || isNaN(id)) return;

    try {
      selectedLabelDetail = await recognitionCatalogsAPI.getLabel(id, labelId);
    } catch (error) {
      uiStore.showToast("Failed to load label details", "error");
      console.error("Error loading label:", error);
    }
  }

  function openAddLabelModal() {
    labelFormData = { label_name: "", description: "" };
    showAddLabelModal = true;
  }

  function closeAddLabelModal() {
    showAddLabelModal = false;
  }

  async function handleAddLabel() {
    if (id === undefined || isNaN(id)) return;

    if (!labelFormData.label_name) {
      uiStore.showToast("Please enter a label name", "error");
      return;
    }

    try {
      await recognitionCatalogsAPI.createLabel(id, {
        label_name: labelFormData.label_name,
        description: labelFormData.description || undefined,
      });
      uiStore.showToast("Label created successfully", "success");
      closeAddLabelModal();
      await loadCatalog();
    } catch (error: any) {
      uiStore.showToast(
        error.response?.data?.detail || "Failed to create label",
        "error"
      );
      console.error("Error creating label:", error);
    }
  }

  async function handleDeleteLabel(labelId: number, labelName: string) {
    if (id === undefined || isNaN(id)) return;

    if (!confirm(`Delete label "${labelName}" and all its images?`)) {
      return;
    }

    try {
      await recognitionCatalogsAPI.deleteLabel(id, labelId);
      uiStore.showToast("Label deleted successfully", "success");
      await loadCatalog();
      if (selectedLabel?.id === labelId) {
        selectedLabel = null;
        selectedLabelDetail = null;
      }
    } catch (error) {
      uiStore.showToast("Failed to delete label", "error");
      console.error("Error deleting label:", error);
    }
  }

  function openUploadModal(label: RecognitionLabel) {
    selectedLabel = label;
    uploadFiles = null;
    showUploadModal = true;
  }

  function closeUploadModal() {
    showUploadModal = false;
    selectedLabel = null;
  }

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    uploadFiles = target.files;
  }

  async function handleUploadImages() {
    if (id === undefined || isNaN(id)) return;

    if (!uploadFiles || uploadFiles.length === 0 || !selectedLabel) {
      uiStore.showToast("Please select images to upload", "error");
      return;
    }

    uploading = true;
    uploadProgress.show = true;
    uploadProgress.step = 'Uploading';
    uploadProgress.message = `Uploading ${uploadFiles.length} image(s)...`;
    
    const labelId = selectedLabel.id; // Store label ID before closing modal

    try {
      const filesArray = Array.from(uploadFiles);
      await recognitionCatalogsAPI.uploadImages(id, labelId, filesArray);

      uploadProgress.step = 'Processing';
      uploadProgress.message = 'Creating thumbnails and generating embeddings...';
      
      // Small delay to show processing message
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const msg =
        filesArray.length <= 5
          ? "Images uploaded and processed successfully"
          : `${filesArray.length} images uploaded. Processing in background...`;

      closeUploadModal();
      uploadProgress.show = false;
      
      uiStore.showToast(msg, "success");

      // Reload catalog to update header counts
      await loadCatalog();

      // Reload label detail and auto-select to show new images
      await loadLabelDetail(labelId);

      // Find and set the selected label from the reloaded catalog
      if (catalog) {
        selectedLabel = catalog.labels.find((l) => l.id === labelId) || null;
      }
    } catch (error) {
      uploadProgress.show = false;
      uiStore.showToast("Failed to upload images", "error");
      console.error("Error uploading images:", error);
    } finally {
      uploading = false;
    }
  }

  function handleSearchFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      searchFile = target.files[0];
    }
  }

  async function handleSearch() {
    if (id === undefined || isNaN(id)) return;

    if (!searchFile) {
      uiStore.showToast("Please select a query image", "error");
      return;
    }

    searching = true;
    searchResults = null;
    try {
      searchResults = await recognitionCatalogsAPI.searchSimilar(
        id,
        searchFile,
        {
          top_k: topK,
          threshold: threshold,
        }
      );

      if (searchResults.matches.length === 0) {
        uiStore.showToast("No matches found above threshold", "info");
      }
    } catch (error) {
      uiStore.showToast("Search failed", "error");
      console.error("Error searching:", error);
    } finally {
      searching = false;
    }
  }

  async function handleTextSearch() {
    if (id === undefined || isNaN(id)) return;

    if (!textQuery.trim()) {
      uiStore.showToast("Please enter a search query", "error");
      return;
    }

    searchingText = true;
    semanticResults = null;
    try {
      semanticResults = await recognitionCatalogsAPI.searchByText(
        id,
        textQuery,
        {
          top_k: semanticTopK,
          threshold: semanticThreshold,
        }
      );

      if (semanticResults.matches.length === 0) {
        uiStore.showToast("No matches found above threshold", "info");
      }
    } catch (error: any) {
      uiStore.showToast(
        error.response?.data?.detail || "Text search failed",
        "error"
      );
      console.error("Error in text search:", error);
    } finally {
      searchingText = false;
    }
  }

  function useExampleQuery(example: string) {
    textQuery = example;
  }

  function selectLabel(label: RecognitionLabel) {
    selectedLabel = label;
    loadLabelDetail(label.id);
    showLabelDetailModal = true;
  }

  function closeLabelDetailModal() {
    showLabelDetailModal = false;
    // Keep selectedLabel and selectedLabelDetail for potential re-opening
  }

  function openZipUploadModal() {
    zipFile = null;
    showZipUploadModal = true;
  }

  function closeZipUploadModal() {
    showZipUploadModal = false;
    zipFile = null;
  }

  function handleZipFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      zipFile = target.files[0];
    }
  }

  async function handleUploadZip() {
    if (id === undefined || isNaN(id)) return;

    if (!zipFile) {
      uiStore.showToast("Please select a ZIP file", "error");
      return;
    }

    uploadingZip = true;
    uploadProgress.show = true;
    uploadProgress.step = 'Uploading';
    uploadProgress.message = 'Uploading ZIP file to server...';
    
    try {
      const result = await recognitionCatalogsAPI.uploadZip(id, zipFile);

      uploadProgress.step = 'Processing';
      uploadProgress.message = 'Extracting and processing images...';
      
      // Small delay to show processing message
      await new Promise(resolve => setTimeout(resolve, 500));
      
      closeZipUploadModal();
      uploadProgress.show = false;

      uiStore.showToast(
        `Successfully uploaded! ${result.labels_created} labels created, ${result.images_uploaded} images uploaded.`,
        "success"
      );

      await loadCatalog();
    } catch (error: any) {
      uploadProgress.show = false;
      uiStore.showToast(
        error.response?.data?.detail || "Failed to upload ZIP",
        "error"
      );
      console.error("Error uploading ZIP:", error);
    } finally {
      uploadingZip = false;
    }
  }

  function getImageUrl(
    labelId: number,
    imageId: number,
    thumbnail = true
  ): string {
    if (id === undefined || isNaN(id)) return "";
    return recognitionCatalogsAPI.getImageUrl(id, labelId, imageId, thumbnail);
  }
</script>

<div class="catalog-detail-page">
  {#if loading}
    <div class="loading-container">
      <div class="spinner"></div>
      <p>Loading catalog...</p>
    </div>
  {:else if catalog}
    <!-- Header -->
    <div class="page-header">
      <div>
        <button
          class="btn-back"
          on:click={() => navigate("/recognition-catalogs")}
        >
          ← Back
        </button>
        <h1>{catalog.name}</h1>
        <span class="category-badge">{catalog.category}</span>
        {#if catalog.description}
          <p class="description">{catalog.description}</p>
        {/if}
      </div>
      <div class="stats-mini">
        <div class="stat">
          <strong>{catalog.label_count}</strong> Labels
        </div>
        <div class="stat">
          <strong>{catalog.image_count}</strong> Images
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        class:active={activeTab === "labels"}
        on:click={() => (activeTab = "labels")}
      >
        🏷️ Labels & Images
      </button>
      <button
        class="tab"
        class:active={activeTab === "search"}
        on:click={() => (activeTab = "search")}
      >
        🔍 Similarity Search
      </button>
      <button
        class="tab"
        class:active={activeTab === "semantic"}
        on:click={() => (activeTab = "semantic")}
      >
        🧠 Semantic Search
      </button>
    </div>

    <!-- Labels Tab -->
    {#if activeTab === "labels"}
      <div class="labels-section">
        <div class="section-header">
          <h2>Labels ({catalog.label_count})</h2>
          <div class="header-actions">
            <button class="btn btn-secondary" on:click={openZipUploadModal}>
              📦 Upload ZIP
            </button>
            <button class="btn btn-primary" on:click={openAddLabelModal}>
              ➕ Add Label
            </button>
          </div>
        </div>

        <!-- Search and View Controls -->
        <div class="controls-bar">
          <div class="search-box">
            <input
              type="text"
              placeholder="Search labels..."
              bind:value={searchQuery}
            />
            <span class="search-icon">🔍</span>
          </div>
          <div class="view-toggle">
            <button
              class="view-btn"
              class:active={viewMode === "card"}
              on:click={() => (viewMode = "card")}
              title="Card View"
            >
              ⊞
            </button>
            <button
              class="view-btn"
              class:active={viewMode === "list"}
              on:click={() => (viewMode = "list")}
              title="List View"
            >
              ☰
            </button>
            <button
              class="view-btn"
              class:active={viewMode === "table"}
              on:click={() => (viewMode = "table")}
              title="Table View"
            >
              ⊟
            </button>
          </div>
        </div>

        {#if filteredLabels.length > 0}
          {#if searchQuery}
            <p class="search-results-text">
              Found {filteredLabels.length} label{filteredLabels.length !== 1
                ? "s"
                : ""}
            </p>
          {/if}

          {#if viewMode === "card"}
            <div class="labels-grid">
              {#each filteredLabels as label}
                <div class="label-card" on:click={() => selectLabel(label)}>
                  <div class="label-header">
                    <h3>{label.label_name}</h3>
                    <div class="label-actions">
                      <button
                        class="btn-icon"
                        on:click|stopPropagation={() => openUploadModal(label)}
                        title="Upload images"
                      >
                        📤
                      </button>
                      <button
                        class="btn-icon btn-danger"
                        on:click|stopPropagation={() =>
                          handleDeleteLabel(label.id, label.label_name)}
                        title="Delete label"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                  {#if label.description}
                    <p class="label-description">{label.description}</p>
                  {/if}
                  <div class="label-stats">
                    <span>🖼️ {label.image_count} images</span>
                  </div>
                </div>
              {/each}
            </div>
          {:else if viewMode === "list"}
            <div class="labels-list">
              {#each filteredLabels as label}
                <div
                  class="label-list-item"
                  on:click={() => selectLabel(label)}
                >
                  <div class="label-list-info">
                    <h4>{label.label_name}</h4>
                    {#if label.description}
                      <p class="description-truncate">{label.description}</p>
                    {/if}
                  </div>
                  <div class="label-list-stats">
                    <span class="image-count">🖼️ {label.image_count}</span>
                  </div>
                  <div class="label-list-actions">
                    <button
                      class="btn-icon"
                      on:click|stopPropagation={() => openUploadModal(label)}
                      title="Upload images"
                    >
                      📤
                    </button>
                    <button
                      class="btn-icon btn-danger"
                      on:click|stopPropagation={() =>
                        handleDeleteLabel(label.id, label.label_name)}
                      title="Delete label"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="labels-table-container">
              <table class="labels-table">
                <thead>
                  <tr>
                    <th>Label Name</th>
                    <th>Description</th>
                    <th>Images</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each filteredLabels as label}
                    <tr on:click={() => selectLabel(label)}>
                      <td class="label-name">{label.label_name}</td>
                      <td class="label-desc">{label.description || "-"}</td>
                      <td class="label-count">{label.image_count}</td>
                      <td class="label-actions-cell">
                        <button
                          class="btn-icon"
                          on:click|stopPropagation={() =>
                            openUploadModal(label)}
                          title="Upload images"
                        >
                          📤
                        </button>
                        <button
                          class="btn-icon btn-danger"
                          on:click|stopPropagation={() =>
                            handleDeleteLabel(label.id, label.label_name)}
                          title="Delete label"
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
        {:else if searchQuery}
          <div class="empty-state">
            <p>No labels found matching "{searchQuery}"</p>
          </div>
        {:else}
          <div class="empty-state">
            <p>No labels created yet. Add a label to get started.</p>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Search Tab -->
    {#if activeTab === "search"}
      <div class="search-section">
        <div class="search-form">
          <h2>Search Similar Images</h2>
          <p class="subtitle">
            Upload an image to find similar matches in this catalog
          </p>

          <div class="form-group">
            <label for="search-image">Query Image</label>
            <input
              id="search-image"
              type="file"
              accept="image/*"
              on:change={handleSearchFileSelect}
            />
          </div>

          <div class="search-params">
            <div class="form-group">
              <label for="top-k">Top K Results: {topK}</label>
              <input
                id="top-k"
                type="range"
                min="1"
                max="20"
                bind:value={topK}
              />
            </div>
            <div class="form-group">
              <label for="threshold"
                >Similarity Threshold: {threshold.toFixed(2)}</label
              >
              <input
                id="threshold"
                type="range"
                min="0"
                max="1"
                step="0.05"
                bind:value={threshold}
              />
            </div>
          </div>

          <button
            class="btn btn-primary"
            on:click={handleSearch}
            disabled={!searchFile || searching}
          >
            {searching ? "Searching..." : "🔍 Search"}
          </button>
        </div>

        {#if searchResults}
          <div class="search-results">
            <h3>
              Found {searchResults.matches.length} matches
              <span class="text-muted"
                >({searchResults.inference_time_ms.toFixed(0)}ms)</span
              >
            </h3>

            {#if searchResults.matches.length > 0}
              <div class="matches-grid">
                {#each searchResults.matches as match}
                  <div class="match-card">
                    <img
                      src={getImageUrl(match.label_id, match.image_id, true)}
                      alt={match.label_name}
                      loading="lazy"
                    />
                    <div class="match-info">
                      <h4>{match.label_name}</h4>
                      <div class="similarity-score">
                        <div class="score-bar">
                          <div
                            class="score-fill"
                            style="width: {match.similarity_score * 100}%"
                          ></div>
                        </div>
                        <span class="score-value"
                          >{(match.similarity_score * 100).toFixed(1)}%</span
                        >
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="text-muted">
                No matches above threshold of {threshold.toFixed(2)}
              </p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Semantic Text Search Tab -->
    {#if activeTab === "semantic"}
      <div class="search-section">
        <div class="search-form">
          <h2>🧠 Semantic Text Search</h2>
          <p class="subtitle">
            Find images using natural language descriptions. CLIP understands context, emotions, and abstract concepts.
          </p>

          <!-- Example Queries -->
          <div class="example-queries">
            <p class="example-label">Try these examples:</p>
            <div class="example-buttons">
              <button class="example-btn" on:click={() => useExampleQuery("a happy child playing in nature")}>
                a happy child playing in nature
              </button>
              <button class="example-btn" on:click={() => useExampleQuery("futuristic city skyline at night")}>
                futuristic city skyline at night
              </button>
              <button class="example-btn" on:click={() => useExampleQuery("person wearing a red jacket")}>
                person wearing a red jacket
              </button>
              <button class="example-btn" on:click={() => useExampleQuery("golden sunset over ocean")}>
                golden sunset over ocean
              </button>
              <button class="example-btn" on:click={() => useExampleQuery("animal in the wild")}>
                animal in the wild
              </button>
              <button class="example-btn" on:click={() => useExampleQuery("modern architecture building")}>
                modern architecture building
              </button>
            </div>
          </div>

          <!-- Text Query Input -->
          <div class="form-group">
            <label for="text-query">Describe what you're looking for</label>
            <textarea
              id="text-query"
              bind:value={textQuery}
              placeholder="e.g., a person smiling outdoors, a colorful abstract painting, mountains covered in snow..."
              rows="3"
            ></textarea>
            <p class="help-text">
              💡 Be descriptive! Include objects, scenes, emotions, colors, actions, or styles.
            </p>
          </div>

          <!-- Search Parameters -->
          <div class="search-params">
            <div class="form-group">
              <label for="semantic-top-k">Top K Results: {semanticTopK}</label>
              <input
                id="semantic-top-k"
                type="range"
                min="1"
                max="20"
                bind:value={semanticTopK}
              />
            </div>
            <div class="form-group">
              <label for="semantic-threshold"
                >Similarity Threshold: {semanticThreshold.toFixed(2)}</label
              >
              <input
                id="semantic-threshold"
                type="range"
                min="0"
                max="1"
                step="0.05"
                bind:value={semanticThreshold}
              />
            </div>
          </div>

          <button
            class="btn btn-primary"
            on:click={handleTextSearch}
            disabled={!textQuery.trim() || searchingText}
          >
            {searchingText ? "Searching..." : "🔍 Search"}
          </button>
        </div>

        <!-- Results -->
        {#if semanticResults}
          <div class="search-results">
            <h3>
              Found {semanticResults.matches.length} matches
              <span class="text-muted"
                >({semanticResults.inference_time_ms.toFixed(0)}ms)</span
              >
            </h3>
            <p class="query-display">
              <strong>Query:</strong> "{textQuery}"
            </p>

            {#if semanticResults.matches.length > 0}
              <div class="matches-grid">
                {#each semanticResults.matches as match}
                  <div class="match-card">
                    <img
                      src={getImageUrl(match.label_id, match.image_id, true)}
                      alt={match.label_name}
                      loading="lazy"
                    />
                    <div class="match-info">
                      <h4>{match.label_name}</h4>
                      <div class="similarity-score">
                        <div class="score-bar">
                          <div
                            class="score-fill"
                            style="width: {match.similarity_score * 100}%"
                          ></div>
                        </div>
                        <span class="score-value"
                          >{(match.similarity_score * 100).toFixed(1)}%</span
                        >
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="text-muted">
                No matches above threshold of {semanticThreshold.toFixed(2)}. Try lowering the threshold or using different keywords.
              </p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  {:else}
    <div class="error-state">
      <h2>Catalog not found</h2>
      <p>
        The catalog you're looking for doesn't exist or you don't have
        permission to view it.
      </p>
      <button
        class="btn btn-primary"
        on:click={() => navigate("/recognition-catalogs")}
      >
        ← Back to Catalogs
      </button>
    </div>
  {/if}
</div>

<!-- Add Label Modal -->
{#if showAddLabelModal}
  <div class="modal-backdrop" on:click={closeAddLabelModal}>
    <div class="modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Add Label</h2>
        <button class="close-btn" on:click={closeAddLabelModal}>&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="label-name">Label Name *</label>
          <input
            id="label-name"
            type="text"
            bind:value={labelFormData.label_name}
            placeholder="e.g., John Doe"
            required
          />
        </div>
        <div class="form-group">
          <label for="label-description">Description</label>
          <textarea
            id="label-description"
            bind:value={labelFormData.description}
            placeholder="Optional description..."
            rows="3"
          ></textarea>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" on:click={closeAddLabelModal}
          >Cancel</button
        >
        <button class="btn btn-primary" on:click={handleAddLabel}
          >Add Label</button
        >
      </div>
    </div>
  </div>
{/if}

<!-- Upload Images Modal -->
{#if showUploadModal && selectedLabel}
  <div class="modal-backdrop" on:click={closeUploadModal}>
    <div class="modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Upload Images for "{selectedLabel.label_name}"</h2>
        <button class="close-btn" on:click={closeUploadModal}>&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="image-files">Select Images</label>
          <input
            id="image-files"
            type="file"
            accept="image/*"
            multiple
            on:change={handleFileSelect}
          />
          {#if uploadFiles}
            <p class="help-text">{uploadFiles.length} file(s) selected</p>
            {#if uploadFiles.length > 5}
              <p class="info-text">
                ℹ️ {uploadFiles.length} images will be processed in the background.
              </p>
            {/if}
          {/if}
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-secondary"
          on:click={closeUploadModal}
          disabled={uploading}
        >
          Cancel
        </button>
        <button
          class="btn btn-primary"
          on:click={handleUploadImages}
          disabled={uploading}
        >
          {uploading ? "Uploading..." : "Upload Images"}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Label Detail Modal -->
{#if showLabelDetailModal && selectedLabelDetail}
  <div class="modal-backdrop" on:click={closeLabelDetailModal}>
    <div class="modal modal-large" on:click|stopPropagation>
      <div class="modal-header">
        <h2>📁 {selectedLabelDetail.label_name}</h2>
        <button class="close-btn" on:click={closeLabelDetailModal}
          >&times;</button
        >
      </div>
      <div class="modal-body">
        {#if selectedLabelDetail.description}
          <p class="label-description-full">
            {selectedLabelDetail.description}
          </p>
        {/if}
        <div class="modal-stats">
          <span
            ><strong>{selectedLabelDetail.images?.length || 0}</strong> images</span
          >
        </div>
        {#if selectedLabelDetail.images && selectedLabelDetail.images.length > 0}
          <div class="images-grid-modal">
            {#each selectedLabelDetail.images as image}
              <div class="image-card">
                <img
                  src={getImageUrl(selectedLabelDetail.id, image.id, true)}
                  alt="Recognition"
                  loading="lazy"
                />
                <div class="image-status">
                  {image.is_processed ? "✅" : "⏳"}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-muted">No images uploaded yet</p>
        {/if}
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-secondary"
          on:click={() => openUploadModal(selectedLabelDetail)}
        >
          📤 Upload Images
        </button>
        <button class="btn btn-primary" on:click={closeLabelDetailModal}>
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Upload ZIP Modal -->
{#if showZipUploadModal}
  <div class="modal-backdrop" on:click={closeZipUploadModal}>
    <div class="modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Upload Catalogue Dataset (ZIP)</h2>
        <button class="close-btn" on:click={closeZipUploadModal}>&times;</button
        >
      </div>
      <div class="modal-body">
        <div class="info-box">
          <p><strong>📂 Expected ZIP Structure:</strong></p>
          <pre>data.zip
├── Aaron/
│   ├── image1.jpg
│   └── image2.jpg
└── BumbleBee/
    ├── bee1.png
    └── bee2.png</pre>
          <p class="help-text">
            Each folder becomes a label. Images inside are added to that label.
            If labels already exist, images will be added to them.
          </p>
        </div>
        <div class="form-group">
          <label for="zip-file">Select ZIP File</label>
          <input
            id="zip-file"
            type="file"
            accept=".zip"
            on:change={handleZipFileSelect}
          />
          {#if zipFile}
            <p class="help-text">Selected: {zipFile.name}</p>
          {/if}
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-secondary"
          on:click={closeZipUploadModal}
          disabled={uploadingZip}
        >
          Cancel
        </button>
        <button
          class="btn btn-primary"
          on:click={handleUploadZip}
          disabled={uploadingZip}
        >
          {uploadingZip ? "Uploading..." : "Upload ZIP"}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Upload Progress Panel -->
{#if uploadProgress.show}
  <div class="progress-overlay">
    <div class="progress-panel">
      <div class="progress-header">
        <h3>Processing Dataset Upload</h3>
      </div>
      <div class="progress-body">
        <div class="spinner-container">
          <div class="spinner"></div>
        </div>
        <div class="progress-step">{uploadProgress.step}</div>
        <div class="progress-message">{uploadProgress.message}</div>
        <div class="progress-info">
          <p>⏳ This may take a few moments depending on the size of your dataset.</p>
          <p>📊 The system is:</p>
          <ul>
            <li>Extracting ZIP archive</li>
            <li>Creating label folders</li>
            <li>Processing and copying images</li>
            <li>Generating thumbnails</li>
            <li>Creating embeddings for recognition</li>
          </ul>
          <p class="help-text">✅ Please wait while the upload completes...</p>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .catalog-detail-page {
    padding: 1.5rem;
    width: 100%;
    max-width: 100%;
  }

  @media (min-width: 768px) {
    .catalog-detail-page {
      padding: 2rem;
    }
  }

  @media (min-width: 1920px) {
    .catalog-detail-page {
      padding: 2rem 3rem;
    }
  }

  .page-header {
    margin-bottom: 2rem;
  }

  .btn-back {
    background: none;
    border: none;
    color: var(--color-accent);
    cursor: pointer;
    padding: 0.5rem 0;
    margin-bottom: 1rem;
    font-size: 1rem;
  }

  .page-header h1 {
    margin: 0.5rem 0;
    font-size: 2rem;
    color: var(--color-navy);
  }

  .category-badge {
    display: inline-block;
    background: var(--color-accent);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.875rem;
    margin-left: 0.5rem;
  }

  .description {
    color: var(--color-text-secondary);
    margin-top: 0.5rem;
  }

  .stats-mini {
    display: flex;
    gap: 2rem;
    margin-top: 1rem;
  }

  .stat {
    color: var(--color-text-secondary);
  }

  .tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 2rem;
    border-bottom: 2px solid var(--color-border);
  }

  .tab {
    background: none;
    border: none;
    padding: 1rem 1.5rem;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    color: var(--color-text-secondary);
    font-size: 1rem;
    transition: all 0.2s;
  }

  .tab.active {
    color: var(--color-accent);
    border-bottom-color: var(--color-accent);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .section-header h2 {
    margin: 0;
    color: var(--color-navy);
  }

  .labels-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }

  @media (min-width: 768px) {
    .labels-grid {
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    }
  }

  @media (min-width: 1440px) {
    .labels-grid {
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.5rem;
    }
  }

  @media (min-width: 1920px) {
    .labels-grid {
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 2rem;
    }
  }

  .label-card {
    background: white;
    border: 2px solid var(--color-border);
    border-radius: 8px;
    padding: 1rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .label-card:hover,
  .label-card.selected {
    border-color: var(--color-accent);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .label-header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    margin-bottom: 0.5rem;
  }

  .label-header h3 {
    margin: 0;
    font-size: 1.1rem;
    color: var(--color-navy);
  }

  .label-actions {
    display: flex;
    gap: 0.25rem;
  }

  .label-description {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin-bottom: 0.5rem;
  }

  .label-stats {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .images-section {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
  }

  .images-section h3 {
    margin-top: 0;
    color: var(--color-navy);
  }

  .images-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
  }

  @media (min-width: 640px) {
    .images-grid {
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 1rem;
    }
  }

  @media (min-width: 1440px) {
    .images-grid {
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 1.25rem;
    }
  }

  @media (min-width: 1920px) {
    .images-grid {
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1.5rem;
    }
  }

  .image-card {
    position: relative;
    aspect-ratio: 1;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--color-border);
  }

  .image-card img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .image-status {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
  }

  .search-section {
    background: white;
    border-radius: 8px;
    padding: 2rem;
  }

  .search-form h2 {
    margin-top: 0;
    color: var(--color-navy);
  }

  .subtitle {
    color: var(--color-text-secondary);
    margin-bottom: 1.5rem;
  }

  .search-params {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    margin: 1rem 0;
  }

  @media (min-width: 640px) {
    .search-params {
      grid-template-columns: 1fr 1fr;
    }
  }

  .search-results {
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 2px solid var(--color-border);
  }

  .search-results h3 {
    color: var(--color-navy);
  }

  .matches-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 0.75rem;
  }

  @media (min-width: 640px) {
    .matches-grid {
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1rem;
    }
  }

  @media (min-width: 1024px) {
    .matches-grid {
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 1.25rem;
    }
  }

  @media (min-width: 1440px) {
    .matches-grid {
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 1.5rem;
    }
  }

  @media (min-width: 1920px) {
    .matches-grid {
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 2rem;
    }
  }

  .match-card {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }

  .match-card img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
  }

  .match-info {
    padding: 1rem;
  }

  .match-info h4 {
    margin: 0 0 0.5rem 0;
    color: var(--color-navy);
  }

  .similarity-score {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .score-bar {
    flex: 1;
    height: 8px;
    background: var(--color-border);
    border-radius: 4px;
    overflow: hidden;
  }

  .score-fill {
    height: 100%;
    background: linear-gradient(to right, var(--color-accent), #4caf50);
    transition: width 0.3s;
  }

  .score-value {
    font-weight: 600;
    color: var(--color-accent);
    min-width: 50px;
    text-align: right;
  }

  /* Semantic Search Specific Styles */
  .example-queries {
    background: #f0f8ff;
    border: 1px solid #b3d9ff;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1.5rem;
  }

  .example-label {
    font-weight: 600;
    color: var(--color-navy);
    margin-bottom: 0.75rem;
    font-size: 0.875rem;
  }

  .example-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .example-btn {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
    color: var(--color-navy);
  }

  .example-btn:hover {
    background: var(--color-accent);
    color: white;
    border-color: var(--color-accent);
    transform: translateY(-2px);
  }

  .query-display {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    border-left: 3px solid var(--color-accent);
  }

  .query-display strong {
    color: var(--color-navy);
  }

  .form-group textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 1rem;
    font-family: inherit;
    resize: vertical;
  }

  .form-group textarea:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .loading-container,
  .error-state,
  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
  }

  .text-muted {
    color: var(--color-text-secondary);
  }

  .info-text {
    color: var(--color-accent);
    font-size: 0.875rem;
    margin-top: 0.5rem;
  }

  .help-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin-top: 0.5rem;
  }

  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.25rem;
    font-size: 1.25rem;
    transition: transform 0.2s;
  }

  .btn-icon:hover {
    transform: scale(1.2);
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

  .header-actions {
    display: flex;
    gap: 0.75rem;
  }

  .controls-bar {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .search-box {
    position: relative;
    flex: 1;
    min-width: 250px;
  }

  .search-box input {
    width: 100%;
    padding: 0.75rem 2.5rem 0.75rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 1rem;
  }

  .search-box input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .search-icon {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-secondary);
  }

  .view-toggle {
    display: flex;
    gap: 0.25rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 0.25rem;
    background: white;
  }

  .view-btn {
    background: none;
    border: none;
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    border-radius: 2px;
    color: var(--color-text-secondary);
    font-size: 1.25rem;
    transition: all 0.2s;
  }

  .view-btn:hover {
    background: var(--color-border);
  }

  .view-btn.active {
    background: var(--color-accent);
    color: white;
  }

  .search-results-text {
    color: var(--color-text-secondary);
    margin-bottom: 1rem;
    font-size: 0.875rem;
  }

  /* List View Styles */
  .labels-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .label-list-item {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .label-list-item:hover {
    border-color: var(--color-accent);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .label-list-info {
    flex: 1;
    min-width: 0;
  }

  .label-list-info h4 {
    margin: 0;
    font-size: 1rem;
    color: var(--color-navy);
  }

  .description-truncate {
    margin: 0.25rem 0 0 0;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .label-list-stats {
    display: flex;
    gap: 1rem;
    color: var(--color-text-secondary);
  }

  .image-count {
    font-size: 0.875rem;
    white-space: nowrap;
  }

  .label-list-actions {
    display: flex;
    gap: 0.5rem;
  }

  /* Table View Styles */
  .labels-table-container {
    background: white;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--color-border);
  }

  .labels-table {
    width: 100%;
    border-collapse: collapse;
  }

  .labels-table thead {
    background: var(--color-navy);
    color: white;
  }

  .labels-table th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
  }

  .labels-table tbody tr {
    border-bottom: 1px solid var(--color-border);
    cursor: pointer;
    transition: background 0.2s;
  }

  .labels-table tbody tr:hover {
    background: #f8f9fa;
  }

  .labels-table tbody tr:last-child {
    border-bottom: none;
  }

  .labels-table td {
    padding: 1rem;
  }

  .label-name {
    font-weight: 500;
    color: var(--color-navy);
  }

  .label-desc {
    color: var(--color-text-secondary);
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .label-count {
    text-align: center;
  }

  .label-actions-cell {
    text-align: right;
  }

  /* Modal Large */
  .modal-large {
    max-width: 900px;
    max-height: 85vh;
  }

  .label-description-full {
    color: var(--color-text-secondary);
    margin-bottom: 1rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
  }

  .modal-stats {
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-secondary);
  }

  .images-grid-modal {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
    max-height: 50vh;
    overflow-y: auto;
  }

  @media (min-width: 640px) {
    .images-grid-modal {
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 1rem;
    }
  }

  .info-box {
    background: #f0f8ff;
    border: 1px solid var(--color-accent);
    border-radius: 4px;
    padding: 1rem;
    margin-bottom: 1.5rem;
  }

  .info-box strong {
    color: var(--color-navy);
  }

  .info-box pre {
    background: white;
    padding: 0.75rem;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.875rem;
    margin: 0.5rem 0;
    border: 1px solid var(--color-border);
  }

  /* Upload Progress Panel */
  .progress-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    animation: fadeIn 0.2s ease-in;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .progress-panel {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  .progress-header {
    padding: 1.5rem;
    border-bottom: 2px solid var(--color-accent);
    background: linear-gradient(135deg, var(--color-navy) 0%, #2a4a6a 100%);
    border-radius: 12px 12px 0 0;
  }

  .progress-header h3 {
    margin: 0;
    color: white;
    font-size: 1.25rem;
    text-align: center;
  }

  .progress-body {
    padding: 2rem;
    text-align: center;
  }

  .spinner-container {
    display: flex;
    justify-content: center;
    margin-bottom: 1.5rem;
  }

  .spinner {
    width: 60px;
    height: 60px;
    border: 4px solid var(--color-border);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .progress-step {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-accent);
    margin-bottom: 0.5rem;
  }

  .progress-message {
    font-size: 1rem;
    color: var(--color-navy);
    margin-bottom: 1.5rem;
  }

  .progress-info {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 1.5rem;
    text-align: left;
    border: 1px solid var(--color-border);
  }

  .progress-info p {
    margin: 0.5rem 0;
    color: var(--color-text-secondary);
    font-size: 0.9rem;
  }

  .progress-info ul {
    margin: 0.75rem 0;
    padding-left: 1.5rem;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .progress-info li {
    margin: 0.5rem 0;
    line-height: 1.5;
  }

</style>
