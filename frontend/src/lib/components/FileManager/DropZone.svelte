<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { filesAPI } from '../../api/files';
  import { uiStore } from '../../stores/uiStore';

  export let enabled: boolean = true;
  export let currentFolder: string = 'shared';

  const dispatch = createEventDispatcher();

  let isDragging = false;
  let dragCounter = 0; // Track nested drag events
  let uploadingFiles: Map<string, { name: string; size: number; progress: number; status: 'uploading' | 'success' | 'error'; error?: string }> = new Map();
  let showProgress = false;

  // File validation constants
  const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'];
  const VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];
  const MAX_IMAGE_SIZE = 100 * 1024 * 1024; // 100 MB
  const MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024; // 2 GB

  function handleDragEnter(e: DragEvent) {
    if (!enabled) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    dragCounter++;
    if (e.dataTransfer?.types.includes('Files')) {
      isDragging = true;
    }
  }

  function handleDragLeave(e: DragEvent) {
    if (!enabled) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    dragCounter--;
    if (dragCounter === 0) {
      isDragging = false;
    }
  }

  function handleDragOver(e: DragEvent) {
    if (!enabled) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'copy';
    }
  }

  function validateFile(file: File): { valid: boolean; error?: string } {
    const extension = '.' + file.name.split('.').pop()?.toLowerCase();
    
    // Check file type
    const isImage = IMAGE_EXTENSIONS.includes(extension);
    const isVideo = VIDEO_EXTENSIONS.includes(extension);
    
    if (!isImage && !isVideo) {
      return {
        valid: false,
        error: `Invalid file type. Allowed: ${[...IMAGE_EXTENSIONS, ...VIDEO_EXTENSIONS].join(', ')}`
      };
    }
    
    // Check file size
    if (isImage && file.size > MAX_IMAGE_SIZE) {
      return {
        valid: false,
        error: `Image file too large. Max size: ${filesAPI.formatFileSize(MAX_IMAGE_SIZE)}`
      };
    }
    
    if (isVideo && file.size > MAX_VIDEO_SIZE) {
      return {
        valid: false,
        error: `Video file too large. Max size: ${filesAPI.formatFileSize(MAX_VIDEO_SIZE)}`
      };
    }
    
    return { valid: true };
  }

  async function handleDrop(e: DragEvent) {
    if (!enabled) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = false;
    dragCounter = 0;
    
    const files = Array.from(e.dataTransfer?.files || []);
    
    if (files.length === 0) return;
    
    // Validate all files first
    const validFiles: File[] = [];
    const invalidFiles: { name: string; error: string }[] = [];
    
    for (const file of files) {
      const validation = validateFile(file);
      if (validation.valid) {
        validFiles.push(file);
      } else {
        invalidFiles.push({ name: file.name, error: validation.error! });
      }
    }
    
    // Show errors for invalid files
    if (invalidFiles.length > 0) {
      invalidFiles.forEach(({ name, error }) => {
        uiStore.showToast(`${name}: ${error}`, 'error');
      });
    }
    
    if (validFiles.length === 0) return;
    
    // Start uploading valid files
    showProgress = true;
    
    for (const file of validFiles) {
      const fileId = `${file.name}-${Date.now()}`;
      uploadingFiles.set(fileId, {
        name: file.name,
        size: file.size,
        progress: 0,
        status: 'uploading'
      });
      uploadingFiles = uploadingFiles; // Trigger reactivity
      
      try {
        await filesAPI.uploadFile(file, currentFolder);
        
        const fileData = uploadingFiles.get(fileId);
        if (fileData) {
          fileData.progress = 100;
          fileData.status = 'success';
          uploadingFiles = uploadingFiles;
        }
      } catch (error: any) {
        const fileData = uploadingFiles.get(fileId);
        if (fileData) {
          fileData.status = 'error';
          fileData.error = error.response?.data?.detail || 'Upload failed';
          uploadingFiles = uploadingFiles;
        }
      }
    }
    
    // Auto-close progress after a delay if all successful
    setTimeout(() => {
      const allSuccess = Array.from(uploadingFiles.values()).every(f => f.status === 'success');
      if (allSuccess) {
        closeProgress();
        dispatch('uploadComplete');
      }
    }, 2000);
  }

  function closeProgress() {
    showProgress = false;
    uploadingFiles.clear();
    uploadingFiles = uploadingFiles;
  }

  function cancelUpload(fileId: string) {
    uploadingFiles.delete(fileId);
    uploadingFiles = uploadingFiles;
    
    if (uploadingFiles.size === 0) {
      showProgress = false;
    }
  }

  $: uploadStats = {
    total: uploadingFiles.size,
    success: Array.from(uploadingFiles.values()).filter(f => f.status === 'success').length,
    failed: Array.from(uploadingFiles.values()).filter(f => f.status === 'error').length,
    uploading: Array.from(uploadingFiles.values()).filter(f => f.status === 'uploading').length
  };
</script>

<div 
  class="dropzone-container"
  on:dragenter={handleDragEnter}
  on:dragleave={handleDragLeave}
  on:dragover={handleDragOver}
  on:drop={handleDrop}
>
  <slot />
  
  {#if isDragging && enabled}
    <div class="dropzone-overlay">
      <div class="dropzone-content">
        <div class="dropzone-icon">📤</div>
        <div class="dropzone-text">Drop files here to upload</div>
        <div class="dropzone-hint">Images and videos only</div>
      </div>
    </div>
  {/if}
</div>

<!-- Upload Progress Modal -->
{#if showProgress && uploadingFiles.size > 0}
  <div class="modal-overlay">
    <div class="modal-content upload-modal">
      <div class="modal-header">
        <h3>Uploading Files</h3>
        <button class="modal-close" on:click={closeProgress}>×</button>
      </div>
      <div class="modal-body">
        <div class="upload-stats">
          <span class="stat-item">Total: {uploadStats.total}</span>
          {#if uploadStats.uploading > 0}
            <span class="stat-item stat-uploading">Uploading: {uploadStats.uploading}</span>
          {/if}
          {#if uploadStats.success > 0}
            <span class="stat-item stat-success">Success: {uploadStats.success}</span>
          {/if}
          {#if uploadStats.failed > 0}
            <span class="stat-item stat-error">Failed: {uploadStats.failed}</span>
          {/if}
        </div>
        
        <div class="upload-list">
          {#each Array.from(uploadingFiles.entries()) as [fileId, file]}
            <div class="upload-item" class:success={file.status === 'success'} class:error={file.status === 'error'}>
              <div class="upload-item-header">
                <span class="file-name">{file.name}</span>
                <span class="file-size">{filesAPI.formatFileSize(file.size)}</span>
                {#if file.status === 'uploading'}
                  <button class="cancel-btn" on:click={() => cancelUpload(fileId)}>✕</button>
                {/if}
              </div>
              
              {#if file.status === 'uploading'}
                <div class="progress-bar">
                  <div class="progress-fill indeterminate"></div>
                </div>
              {:else if file.status === 'success'}
                <div class="status-message success">✓ Upload complete</div>
              {:else if file.status === 'error'}
                <div class="status-message error">✗ {file.error || 'Upload failed'}</div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .dropzone-container {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .dropzone-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(225, 96, 76, 0.1);
    border: 3px dashed var(--color-accent);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    pointer-events: none;
  }

  .dropzone-content {
    text-align: center;
    color: var(--color-navy);
  }

  .dropzone-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-md);
  }

  .dropzone-text {
    font-size: var(--font-size-xl);
    font-weight: 600;
    margin-bottom: var(--spacing-xs);
  }

  .dropzone-hint {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  /* Upload Progress Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .upload-modal {
    background: white;
    border-radius: var(--radius-md);
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-light-gray);
  }

  .modal-header h3 {
    margin: 0;
    color: var(--color-navy);
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 2rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    line-height: 1;
    padding: 0;
    width: 32px;
    height: 32px;
  }

  .modal-body {
    padding: var(--spacing-md);
    overflow-y: auto;
    flex: 1;
  }

  .upload-stats {
    display: flex;
    gap: var(--spacing-md);
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-sm);
    background: var(--color-bg-light1);
    border-radius: var(--radius-sm);
  }

  .stat-item {
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .stat-uploading {
    color: var(--color-status-info);
  }

  .stat-success {
    color: var(--color-status-success);
  }

  .stat-error {
    color: var(--color-status-error);
  }

  .upload-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .upload-item {
    padding: var(--spacing-sm);
    background: white;
    border: 1px solid var(--color-light-gray);
    border-radius: var(--radius-sm);
  }

  .upload-item.success {
    border-color: var(--color-status-success);
    background: #f0fdf4;
  }

  .upload-item.error {
    border-color: var(--color-status-error);
    background: #fef2f2;
  }

  .upload-item-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-xs);
  }

  .file-name {
    flex: 1;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-size {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .cancel-btn {
    padding: 2px 6px;
    background: transparent;
    border: 1px solid var(--color-text-secondary);
    border-radius: 4px;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: var(--font-size-sm);
  }

  .cancel-btn:hover {
    background: var(--color-status-error);
    color: white;
    border-color: var(--color-status-error);
  }

  .progress-bar {
    height: 6px;
    background: var(--color-light-gray);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--color-accent);
    transition: width var(--transition-base);
  }

  .progress-fill.indeterminate {
    width: 100%;
    animation: indeterminate 1.5s ease-in-out infinite;
  }

  @keyframes indeterminate {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  .status-message {
    font-size: var(--font-size-sm);
    padding: var(--spacing-xs);
    border-radius: 4px;
  }

  .status-message.success {
    color: var(--color-status-success);
  }

  .status-message.error {
    color: var(--color-status-error);
  }
</style>
