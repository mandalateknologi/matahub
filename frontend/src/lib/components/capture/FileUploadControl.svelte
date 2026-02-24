<script lang="ts">
  /**
   * FileUploadControl - File input with preview for capture page
   * Handles single image, batch images, and video uploads
   */

  // Svelte 5: Props using $props() rune
  let {
    sourceType = "image",
    selectedFile = null,
    selectedFiles = [],
    imagePreview = null,
    disabled = false,
    onFileSelect = undefined,
    onFilesSelect = undefined,
    onClearPreview = undefined,
  }: {
    sourceType?: "image" | "batch" | "video";
    selectedFile?: File | null;
    selectedFiles?: File[];
    imagePreview?: string | null;
    disabled?: boolean;
    onFileSelect?: ((file: File) => void) | undefined;
    onFilesSelect?: ((files: File[]) => void) | undefined;
    onClearPreview?: (() => void) | undefined;
  } = $props();

  // Internal refs
  let fileInputElement: HTMLInputElement;

  // Handle single file selection (image/video)
  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];

    if (!file) return;

    if (sourceType === "image") {
      // Preview single image
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result as string;
        onFileSelect?.(file);
      };
      reader.readAsDataURL(file);
    } else if (sourceType === "video") {
      // Just dispatch the video file
      onFileSelect?.(file);
    }
  }

  // Handle batch files selection
  function handleBatchSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    const files = Array.from(target.files || []);

    if (files.length > 0) {
      onFilesSelect?.(files);
    }
  }

  // Clear preview/selection
  function clearPreview() {
    if (fileInputElement) {
      fileInputElement.value = "";
    }
    onClearPreview?.();
  }

  // Svelte 5: Derived reactive values
  const acceptedTypes = $derived(
    sourceType === "video" ? "video/*" : "image/*",
  );
  const isMultiple = $derived(sourceType === "batch");
  const hasSelection = $derived(
    sourceType === "batch"
      ? selectedFiles.length > 0
      : selectedFile !== null || imagePreview !== null,
  );
</script>

<div class="file-upload-control">
  <!-- File Input Button -->
  <div class="upload-button-container">
    <input
      bind:this={fileInputElement}
      type="file"
      accept={acceptedTypes}
      multiple={isMultiple}
      on:change={isMultiple ? handleBatchSelect : handleFileSelect}
      {disabled}
      class="file-input-hidden"
      id="file-upload-input"
    />
    <label for="file-upload-input" class="upload-button" class:disabled>
      <span class="upload-icon">📁</span>
      <span class="upload-label">
        {#if sourceType === "image"}
          Choose Image
        {:else if sourceType === "batch"}
          Choose Images
        {:else if sourceType === "video"}
          Choose Video
        {/if}
      </span>
    </label>

    {#if hasSelection}
      <button
        class="btn-clear-preview"
        on:click={clearPreview}
        {disabled}
        type="button"
      >
        ✕ Clear
      </button>
    {/if}
  </div>

  <!-- Preview/Selection Info -->
  {#if sourceType === "image" && imagePreview}
    <div class="preview-container">
      <img src={imagePreview} alt="Preview" class="preview-image" />
      <p class="preview-filename">{selectedFile?.name || "Image"}</p>
    </div>
  {:else if sourceType === "batch" && selectedFiles.length > 0}
    <div class="batch-info">
      <p class="batch-count">
        ✓ {selectedFiles.length}
        {selectedFiles.length === 1 ? "image" : "images"} selected
      </p>
      <div class="batch-preview-grid">
        {#each selectedFiles.slice(0, 6) as file}
          <div class="batch-preview-item" title={file.name}>
            <img
              src={URL.createObjectURL(file)}
              alt={file.name}
              class="batch-preview-thumb"
            />
          </div>
        {/each}
        {#if selectedFiles.length > 6}
          <div class="batch-preview-more">
            +{selectedFiles.length - 6} more
          </div>
        {/if}
      </div>
    </div>
  {:else if sourceType === "video" && selectedFile}
    <div class="video-info">
      <span class="video-icon">🎥</span>
      <p class="video-filename">{selectedFile.name}</p>
      <p class="video-size">
        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
      </p>
    </div>
  {/if}
</div>

<style>
  .file-upload-control {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  /* Upload Button Container */
  .upload-button-container {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .file-input-hidden {
    display: none;
  }

  .upload-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    background: var(--color--accent, #e1604c);
    color: white;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.95rem;
    transition: all 0.2s ease;
    border: 2px solid transparent;
  }

  .upload-button:hover:not(.disabled) {
    background: var(--color-accent, #e1604c);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(225, 96, 76, 0.2);
  }

  .upload-button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .upload-icon {
    font-size: 1.2rem;
  }

  .btn-clear-preview {
    padding: 0.75rem 1rem;
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    transition: all 0.2s ease;
    min-width: 76.63px;
    min-height: 76.63px;
  }

  .btn-clear-preview:hover:not(:disabled) {
    background: #c82333;
    transform: translateY(-1px);
  }

  .btn-clear-preview:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Single Image Preview */
  .preview-container {
    background: #f5f5f5;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
  }

  .preview-image {
    max-width: 100%;
    max-height: 200px;
    border-radius: 6px;
    object-fit: contain;
  }

  .preview-filename {
    margin: 0;
    font-size: 0.9rem;
    color: #666;
    font-weight: 500;
    word-break: break-all;
    text-align: center;
  }

  /* Batch Preview */
  .batch-info {
    background: #f5f5f5;
    border-radius: 8px;
    padding: 1rem;
  }

  .batch-count {
    margin: 0 0 0.75rem;
    color: var(--color-accent, #e1604c);
    font-weight: 600;
    font-size: 0.95rem;
  }

  .batch-preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
    gap: 0.5rem;
  }

  .batch-preview-item {
    aspect-ratio: 1;
    border-radius: 4px;
    overflow: hidden;
    background: #e0e0e0;
  }

  .batch-preview-thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .batch-preview-more {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-navy, #1d2f43);
    color: white;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
  }

  /* Video Info */
  .video-info {
    background: #f5f5f5;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .video-icon {
    font-size: 2rem;
  }

  .video-filename {
    flex: 1;
    margin: 0;
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
    word-break: break-all;
  }

  .video-size {
    margin: 0;
    color: #666;
    font-size: 0.9rem;
  }
</style>
