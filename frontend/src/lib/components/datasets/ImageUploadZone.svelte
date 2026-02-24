<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let accept: string = 'image/jpeg,image/jpg,image/png,image/bmp,image/tiff,image/webp';
  export let multiple: boolean = true;
  export let maxSize: number = 10 * 1024 * 1024; // 10MB
  export let disabled: boolean = false;

  const dispatch = createEventDispatcher();

  let dragging = false;
  let fileInput: HTMLInputElement;
  let error: string = '';

  function handleDragEnter() {
    if (!disabled) {
      dragging = true;
    }
  }

  function handleDragLeave() {
    dragging = false;
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragging = false;
    
    if (disabled) return;

    const files = Array.from(event.dataTransfer?.files || []);
    processFiles(files);
  }

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    const files = Array.from(target.files || []);
    processFiles(files);
    // Reset input to allow selecting the same file again
    target.value = '';
  }

  function processFiles(files: File[]) {
    error = '';

    // Validate files
    const invalidFiles: string[] = [];
    const oversizedFiles: string[] = [];
    const validFiles: File[] = [];

    files.forEach(file => {
      // Check file type
      if (!file.type.startsWith('image/')) {
        invalidFiles.push(file.name);
        return;
      }

      // Check file size
      if (file.size > maxSize) {
        oversizedFiles.push(file.name);
        return;
      }

      validFiles.push(file);
    });

    // Report errors
    if (invalidFiles.length > 0) {
      error = `Invalid file type: ${invalidFiles.join(', ')}. Only images are allowed.`;
      return;
    }

    if (oversizedFiles.length > 0) {
      error = `File too large: ${oversizedFiles.join(', ')}. Maximum size is ${formatSize(maxSize)}.`;
      return;
    }

    // Dispatch valid files
    if (validFiles.length > 0) {
      dispatch('filesSelected', validFiles);
    }
  }

  function formatSize(bytes: number): string {
    return `${(bytes / (1024 * 1024)).toFixed(0)}MB`;
  }

  function openFilePicker() {
    if (!disabled) {
      fileInput.click();
    }
  }
</script>

<div 
  class="upload-zone"
  class:dragging
  class:disabled
  on:dragenter|preventDefault={handleDragEnter}
  on:dragover|preventDefault
  on:dragleave={handleDragLeave}
  on:drop|preventDefault={handleDrop}
  on:click={openFilePicker}
  role="button"
  tabindex={disabled ? -1 : 0}
  on:keydown={(e) => e.key === 'Enter' && openFilePicker()}
>
  <input
    bind:this={fileInput}
    type="file"
    {accept}
    {multiple}
    {disabled}
    on:change={handleFileSelect}
    style="display: none;"
  />

  <div class="upload-icon">
    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
      <polyline points="17 8 12 3 7 8"></polyline>
      <line x1="12" y1="3" x2="12" y2="15"></line>
    </svg>
  </div>

  <div class="upload-text">
    <p class="primary-text">
      {#if dragging}
        Drop images here
      {:else if disabled}
        Upload disabled
      {:else}
        Click to upload or drag and drop
      {/if}
    </p>
    {#if !disabled}
      <p class="secondary-text">
        {multiple ? 'Multiple images allowed' : 'Single image only'} • Maximum {formatSize(maxSize)} per file
      </p>
    {/if}
  </div>

  {#if error}
    <div class="error-message">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      {error}
    </div>
  {/if}
</div>

<style>
  .upload-zone {
    border: 2px dashed var(--color-border);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all var(--transition-fast);
    background: var(--color-bg-secondary);
  }

  .upload-zone:hover:not(.disabled) {
    border-color: var(--color-primary);
    background: var(--color-bg-hover);
  }

  .upload-zone.dragging {
    border-color: var(--color-primary);
    background: rgba(29, 47, 67, 0.05);
  }

  .upload-zone.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: var(--color-bg-tertiary);
  }

  .upload-icon {
    margin-bottom: 1rem;
    color: var(--color-primary);
    display: flex;
    justify-content: center;
  }

  .upload-zone.dragging .upload-icon {
    color: var(--color-accent);
  }

  .upload-text {
    margin-bottom: 0.5rem;
  }

  .primary-text {
    margin: 0 0 0.5rem;
    font-size: 1rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .secondary-text {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .error-message {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: rgba(231, 76, 60, 0.1);
    border-radius: 6px;
    color: var(--color-danger);
    font-size: 0.875rem;
  }

  .error-message svg {
    flex-shrink: 0;
  }
</style>
