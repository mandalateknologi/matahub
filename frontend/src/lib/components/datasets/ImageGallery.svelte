<script lang="ts">
  import { onMount, createEventDispatcher } from "svelte";
  import type { DatasetFile, BoundingBox } from "@/lib/types";
  import ThumbnailOverlay from "./ThumbnailOverlay.svelte";
  import { datasetsAPI } from "../../api/datasets";

  export let datasetId: number;
  export let files: DatasetFile[] = [];
  export let hasMore: boolean = false;
  export let onLoadMore: () => Promise<void>;
  export let onDeleteFile: (file: DatasetFile) => Promise<void>;
  export let loading: boolean = false;
  export let taskType: string = "detect";
  export let classes: { [key: string]: string } = {};
  export let labeledFiles: Set<string> = new Set();
  export let searchTerm: string = "";
  export let sortBy: string = "name_asc";
  export let labelFilter: string = "all";
  export let recentlyUploaded: Set<string> = new Set();
  export let recentlyEdited: Set<string> = new Set();

  const dispatch = createEventDispatcher();

  let selectedFile: DatasetFile | null = null;
  let showDeleteModal = false;
  let fileToDelete: DatasetFile | null = null;
  let deleting = false;

  // Store label data for each file (boxes for detect, polygons for segment)
  let labelCache: Map<string, { boxes?: BoundingBox[]; polygons?: any[] }> =
    new Map();
  let loadingLabels = false;

  function getImageUrl(file: DatasetFile): string {
    const token = localStorage.getItem("access_token");
    // Encode the file path to handle special characters and spaces
    const encodedPath = file.path
      .split("/")
      .map((segment) => encodeURIComponent(segment))
      .join("/");
    const url = `/api/datasets/${datasetId}/image/${encodedPath}`;
    // Only add token if it exists and is not the string "null"
    if (token && token !== "null" && token !== "undefined") {
      return `${url}?token=${encodeURIComponent(token)}`;
    }
    return url;
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function handleImageClick(file: DatasetFile) {
    selectedFile = file;
  }

  function closePreview() {
    selectedFile = null;
  }

  function confirmDelete(file: DatasetFile) {
    fileToDelete = file;
    showDeleteModal = true;
  }

  function handleLabelImage(file: DatasetFile) {
    dispatch("labelImage", file);
  }

  function hasLabel(file: DatasetFile): boolean {
    return labeledFiles.has(file.path);
  }

  function getBoxesForFile(file: DatasetFile): BoundingBox[] {
    return labelCache.get(file.path)?.boxes || [];
  }

  function getPolygonsForFile(file: DatasetFile): any[] {
    return labelCache.get(file.path)?.polygons || [];
  }

  function getClassName(file: DatasetFile): string | null {
    if (taskType !== "classify" || !file.class_name) return null;
    return file.class_name;
  }

  function getClassDisplayName(file: DatasetFile): string {
    const className = getClassName(file);
    if (!className) return "";
    // Check if we have a friendly name in the classes mapping
    return classes[className] || className;
  }

  // Client-side search and filter removed - handled by backend
  $: sortedFiles = files;

  async function loadLabelsForFiles() {
    if (
      (taskType !== "detect" && taskType !== "segment") ||
      loadingLabels ||
      files.length === 0
    )
      return;

    loadingLabels = true;

    // Filter files that need label loading
    const filesToLoad = files.filter(
      (file) => !labelCache.has(file.path) && labeledFiles.has(file.path)
    );

    if (filesToLoad.length === 0) {
      loadingLabels = false;
      return;
    }

    const labelPromises = filesToLoad.map(async (file) => {
      try {
        const labelData = await datasetsAPI.getImageLabels(
          datasetId,
          file.path
        );
        if (labelData.boxes && labelData.boxes.length > 0) {
          labelCache.set(file.path, { boxes: labelData.boxes });
        } else if (labelData.polygons && labelData.polygons.length > 0) {
          labelCache.set(file.path, { polygons: labelData.polygons });
        }
      } catch (error) {
        // Silently fail - image might not have labels
      }
    });

    await Promise.all(labelPromises);
    loadingLabels = false;
    // Trigger reactivity by creating new Map instance
    labelCache = new Map(labelCache);
  }

  async function handleDelete() {
    if (!fileToDelete) return;

    deleting = true;
    try {
      await onDeleteFile(fileToDelete);
      showDeleteModal = false;
      fileToDelete = null;
    } catch (error) {
      console.error("Delete failed:", error);
    } finally {
      deleting = false;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      if (selectedFile) {
        closePreview();
      } else if (showDeleteModal) {
        showDeleteModal = false;
        fileToDelete = null;
      }
    }
  }

  onMount(() => {
    document.addEventListener("keydown", handleKeydown);
    return () => {
      document.removeEventListener("keydown", handleKeydown);
    };
  });

  // Load labels when files or labeledFiles change
  $: if (
    files.length > 0 &&
    (taskType === "detect" || taskType === "segment") &&
    labeledFiles &&
    labeledFiles.size > 0
  ) {
    loadLabelsForFiles();
  }
</script>

<div class="image-gallery">
  {#if sortedFiles.length === 0 && (searchTerm || labelFilter !== "all")}
    <div class="empty-state">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="64"
        height="64"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="11" cy="11" r="8"></circle>
        <path d="m21 21-4.35-4.35"></path>
      </svg>
      <p>No images match your filters</p>
      {#if searchTerm}
        <p class="hint-text">Search: "{searchTerm}"</p>
      {/if}
      {#if labelFilter !== "all"}
        <p class="hint-text">
          Filter: {labelFilter === "labeled"
            ? "Labeled Only"
            : "Unlabeled Only"}
        </p>
      {/if}
      <p class="hint-text">Try adjusting your filters or search terms</p>
    </div>
  {:else if sortedFiles.length === 0}
    <div class="empty-state">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="64"
        height="64"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <polyline points="21 15 16 10 5 21"></polyline>
      </svg>
      <p>No images in this folder</p>
    </div>
  {:else}
    <div class="gallery-grid">
      {#each sortedFiles as file (file.path)}
        <div
          class="image-card"
          class:recently-uploaded={recentlyUploaded.has(file.path)}
          class:recently-edited={recentlyEdited.has(file.path)}
        >
          <button
            class="image-wrapper"
            on:click={() => handleImageClick(file)}
            title="Click to preview"
          >
            {#if taskType === "detect" && labelCache.has(file.path) && getBoxesForFile(file).length > 0}
              <ThumbnailOverlay
                imageUrl={getImageUrl(file)}
                boxes={getBoxesForFile(file)}
                {classes}
                size={200}
              />
              <span
                class="box-count-badge"
                title="{getBoxesForFile(file).length} bounding boxes"
              >
                {getBoxesForFile(file).length}
              </span>
            {:else if taskType === "segment" && labelCache.has(file.path) && getPolygonsForFile(file).length > 0}
              <ThumbnailOverlay
                imageUrl={getImageUrl(file)}
                polygons={getPolygonsForFile(file)}
                {classes}
                size={200}
              />
              <span
                class="box-count-badge"
                title="{getPolygonsForFile(file)
                  .length} polygon{getPolygonsForFile(file).length !== 1
                  ? 's'
                  : ''}"
              >
                {getPolygonsForFile(file).length}
              </span>
            {:else}
              <img src={getImageUrl(file)} alt={file.name} loading="lazy" />
            {/if}
            {#if taskType === "classify" && getClassName(file)}
              <span
                class="class-name-badge"
                title="Class: {getClassDisplayName(file)}"
              >
                {getClassDisplayName(file)}
              </span>
            {/if}
            {#if (taskType === "detect" || taskType === "segment") && hasLabel(file)}
              <span class="label-indicator" title="Has labels">✓</span>
            {/if}
          </button>
          <div class="image-info">
            <span class="image-name" title={file.name}>{file.name}</span>
            <span class="image-size">{formatFileSize(file.size)}</span>
          </div>
          {#if taskType === "detect" || taskType === "segment"}
            <button
              class="label-btn"
              on:click={() => handleLabelImage(file)}
              title={taskType === "segment"
                ? "Add polygon labels"
                : "Label image"}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                {#if taskType === "segment"}
                  <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                  <path d="M2 17l10 5 10-5"></path>
                  <path d="M2 12l10 5 10-5"></path>
                {:else}
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <polyline points="21 15 16 10 5 21"></polyline>
                {/if}
              </svg>
              {taskType === "segment" ? "Polygon" : "Label"}
            </button>
          {/if}
          <button
            class="delete-btn"
            on:click={() => confirmDelete(file)}
            title="Delete image"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="3 6 5 6 21 6"></polyline>
              <path
                d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
              ></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </div>
      {/each}
    </div>

    {#if hasMore}
      <div class="load-more-section">
        <button class="load-more-btn" on:click={onLoadMore} disabled={loading}>
          {loading ? "Loading..." : "Load More"}
        </button>
      </div>
    {/if}
  {/if}
</div>

<!-- Image Preview Modal -->
{#if selectedFile}
  <div class="modal-overlay" on:click={closePreview}>
    <div class="modal-content" on:click|stopPropagation>
      <button class="modal-close" on:click={closePreview}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      <div class="preview-image-container">
        {#if taskType === "detect" && labelCache.has(selectedFile.path) && getBoxesForFile(selectedFile).length > 0}
          <ThumbnailOverlay
            imageUrl={getImageUrl(selectedFile)}
            boxes={getBoxesForFile(selectedFile)}
            {classes}
            size={800}
          />
        {:else}
          <img
            src={getImageUrl(selectedFile)}
            alt={selectedFile.name}
            class="preview-image"
          />
        {/if}
      </div>
      <div class="preview-info">
        <h3>{selectedFile.name}</h3>
        <div class="preview-details">
          <span>{formatFileSize(selectedFile.size)}</span>
          {#if taskType === "detect" && hasLabel(selectedFile)}
            <span class="preview-box-count">
              • {getBoxesForFile(selectedFile).length} bounding box{getBoxesForFile(
                selectedFile
              ).length !== 1
                ? "es"
                : ""}
            </span>
          {:else if taskType === "classify" && getClassName(selectedFile)}
            <span class="preview-class-name">
              • Class: {getClassDisplayName(selectedFile)}
            </span>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteModal && fileToDelete}
  <div
    class="modal-overlay"
    on:click={() => {
      showDeleteModal = false;
      fileToDelete = null;
    }}
  >
    <div class="modal-content delete-modal" on:click|stopPropagation>
      <div class="delete-modal-header">
        <svg
          class="delete-icon"
          xmlns="http://www.w3.org/2000/svg"
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="15" y1="9" x2="9" y2="15"></line>
          <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
        <h3>Delete Image</h3>
      </div>
      <div class="delete-modal-body">
        <p class="delete-message">
          Are you sure you want to delete <strong class="file-name"
            >{fileToDelete.name}</strong
          >?
        </p>
        <p class="warning-text">This action cannot be undone.</p>
      </div>
      <div class="modal-actions">
        <button
          class="btn-secondary"
          on:click={() => {
            showDeleteModal = false;
            fileToDelete = null;
          }}
          disabled={deleting}
        >
          Cancel
        </button>
        <button class="btn-danger" on:click={handleDelete} disabled={deleting}>
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .image-gallery {
    width: 100%;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    color: var(--color-text-secondary);
    text-align: center;
  }

  .empty-state svg {
    opacity: 0.3;
    margin-bottom: 1rem;
  }

  .empty-state p {
    margin: 0.5rem 0;
  }

  .hint-text {
    font-size: 0.875rem;
    color: var(--color-grey);
  }

  .gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .image-card {
    position: relative;
    background: var(--color-bg-secondary);
    border-radius: 8px;
    overflow: hidden;
    transition:
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
  }

  .image-card.recently-uploaded {
    animation: highlight-uploaded 3s ease-out;
    border: 3px solid var(--color-success);
  }

  .image-card.recently-edited {
    animation: highlight-edited 3s ease-out;
    border: 3px solid var(--color-accent);
  }

  @keyframes highlight-uploaded {
    0% {
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
    }
    50% {
      box-shadow: 0 0 20px 10px rgba(16, 185, 129, 0.3);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
    }
  }

  @keyframes highlight-edited {
    0% {
      box-shadow: 0 0 0 0 rgba(225, 96, 76, 0.7);
    }
    50% {
      box-shadow: 0 0 20px 10px rgba(225, 96, 76, 0.3);
    }
    100% {
      box-shadow: 0 0 0 0 rgba(225, 96, 76, 0);
    }
  }

  .image-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .image-wrapper {
    position: relative;
    width: 100%;
    padding-top: 100%; /* 1:1 aspect ratio */
    overflow: hidden;
    cursor: pointer;
    background: var(--color-bg-tertiary);
    border: none;
    display: block;
  }

  .image-wrapper img {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform var(--transition-base);
  }

  .image-wrapper:hover img {
    transform: scale(1.05);
  }

  .image-info {
    display: flex;
    flex-direction: column;
    padding: 0.75rem;
    gap: 0.25rem;
  }

  .image-name {
    font-size: 0.875rem;
    color: var(--color-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .image-size {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .label-indicator {
    position: absolute;
    top: 0.5rem;
    left: 0.5rem;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(34, 197, 94, 0.95);
    color: white;
    border-radius: 50%;
    font-weight: 600;
    font-size: 0.875rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    z-index: 2;
  }

  .box-count-badge {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    min-width: 28px;
    height: 28px;
    padding: 0 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(29, 47, 67, 0.95);
    color: white;
    border-radius: 14px;
    font-weight: 600;
    font-size: 0.75rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    z-index: 2;
    border: 2px solid rgba(255, 255, 255, 0.3);
  }

  .class-name-badge {
    position: absolute;
    bottom: 0.5rem;
    left: 0.5rem;
    right: 0.5rem;
    padding: 0.5rem 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(225, 96, 76, 0.95);
    color: white;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.8125rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    z-index: 2;
    text-transform: capitalize;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .label-btn {
    position: absolute;
    bottom: 0.5rem;
    left: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    background: rgba(225, 96, 76, 0.95);
    color: white;
    border: 2px solid rgba(255, 255, 255, 0.9);
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    opacity: 0;
    transition:
      opacity var(--transition-fast),
      background var(--transition-fast),
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    z-index: 3;
  }

  .image-card:hover .label-btn {
    opacity: 1;
    transform: translateY(-2px);
  }

  .label-btn:hover {
    background: rgba(225, 96, 76, 1);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.4);
    border-color: white;
  }

  .label-btn svg {
    width: 14px;
    height: 14px;
  }

  .delete-btn {
    position: absolute;
    bottom: 0.5rem;
    right: 0.5rem;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.95);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    opacity: 0;
    transition:
      opacity var(--transition-fast),
      background var(--transition-fast),
      color var(--transition-fast);
    color: var(--color-error);
    z-index: 3;
  }

  .image-card:hover .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    background: var(--color-error);
    color: white;
  }

  .load-more-section {
    display: flex;
    justify-content: center;
    padding: 1rem 0;
  }

  .load-more-btn {
    padding: 0.75rem 2rem;
    background: var(--color-bg-secondary);
    color: var(--color-accent);
    border: 2px solid var(--color-accent);
    border-radius: 6px;
    font-size: 0.9375rem;
    font-weight: 500;
    cursor: pointer;
    transition: background var(--transition-fast);
  }

  .load-more-btn:hover:not(:disabled) {
    background: var(--color-accent);
    color: var(--color-bg-secondary);
  }

  .load-more-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Modal Styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 2rem;
  }

  .modal-content {
    position: relative;
    background: var(--color-bg-primary);
    border-radius: 12px;
    max-width: 90vw;
    max-height: 90vh;
    overflow: auto;
    padding: 1.5rem;
  }

  .modal-close {
    position: absolute;
    top: 1rem;
    right: 1rem;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    border-radius: 50%;
    cursor: pointer;
    transition: background var(--transition-fast);
    z-index: 10;
  }

  .modal-close:hover {
    background: white;
  }

  .preview-image-container {
    display: flex;
    align-items: center;
    justify-content: center;
    max-width: 100%;
    max-height: 80vh;
    margin: 0 auto;
  }

  .preview-image {
    display: block;
    max-width: 100%;
    max-height: 80vh;
    width: auto;
    height: auto;
    margin: 0 auto;
    border-radius: 8px;
  }

  .preview-info {
    margin-top: 1rem;
    text-align: center;
  }

  .preview-info h3 {
    margin: 0 0 0.5rem;
    font-size: 1.125rem;
    color: var(--color-text-primary);
  }

  .preview-details {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .preview-box-count {
    color: var(--color-primary);
    font-weight: 500;
  }

  .preview-class-name {
    color: var(--color-accent);
    font-weight: 600;
    text-transform: capitalize;
  }

  /* Delete Modal */
  .delete-modal {
    max-width: 440px;
    padding: 2rem;
  }

  .delete-modal-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .delete-icon {
    color: var(--color-accent);
    margin-bottom: 1rem;
  }

  .delete-modal h3 {
    margin: 0;
    color: var(--color-navy);
    font-size: 1.5rem;
    font-weight: 600;
    text-align: center;
  }

  .delete-modal-body {
    margin-bottom: 2rem;
  }

  .delete-message {
    margin: 0 0 1rem;
    color: var(--color-navy);
    font-size: 1rem;
    line-height: 1.6;
    text-align: center;
  }

  .file-name {
    color: var(--color-accent);
    font-weight: 600;
    word-break: break-all;
  }

  .warning-text {
    margin: 0;
    padding: 0.75rem 1rem;
    background: rgba(239, 68, 68, 0.1);
    border-left: 3px solid var(--color-accent);
    color: #b91c1c;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 4px;
    text-align: center;
  }

  .modal-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }

  .btn-secondary,
  .btn-danger {
    padding: 0.75rem 2rem;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-primary);
  }

  .btn-secondary {
    background: #f3f4f6;
    color: var(--color-navy);
    border: 2px solid #e5e7eb;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #e5e7eb;
    border-color: #d1d5db;
    transform: translateY(-1px);
  }

  .btn-danger {
    background: var(--color-accent);
    color: white;
    box-shadow: 0 2px 4px rgba(225, 96, 76, 0.2);
  }

  .btn-danger:hover:not(:disabled) {
    background: #c84a34;
    box-shadow: 0 4px 8px rgba(225, 96, 76, 0.3);
    transform: translateY(-1px);
  }

  .btn-secondary:disabled,
  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  .searching-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(225, 96, 76, 0.1);
    border-radius: 50%;
    border-top-color: var(--color-accent);
    animation: spin 1s ease-in-out infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
