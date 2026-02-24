<script lang="ts">
  import type { FileItem } from "../../api/files";
  import { filesAPI } from "../../api/files";

  export let file: FileItem | null = null;
</script>

{#if file}
  <div class="preview-panel">
    <div class="preview-header">
      <h3>Information</h3>
      {#if file.type !== "folder"}
        <button
          class="download-btn"
          on:click={() => filesAPI.downloadFile(file.id, file.name)}
          title="Download file"
        >
          ⬇
        </button>
      {/if}
    </div>

    {#if file.type === "image"}
      <div class="preview-image">
        <img
          src={filesAPI.getPreviewUrl(file.id)}
          alt={file.name}
          on:error={(e) => {
            e.currentTarget.src =
              'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="200"%3E%3Crect fill="%23f0f0f0" width="200" height="200"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3ENo Preview%3C/text%3E%3C/svg%3E';
          }}
        />
      </div>
    {:else if file.type === "video"}
      <div class="preview-video">
        <video controls>
          <source src={filesAPI.getPreviewUrl(file.id)} type="video/mp4" />
          <track kind="captions" />
          Your browser does not support the video tag.
        </video>
      </div>
    {:else if file.type === "folder"}
      <div class="preview-placeholder">
        <div class="folder-icon">📁</div>
        <p>Folder</p>
      </div>
    {:else}
      <div class="preview-placeholder">
        <div class="file-icon">📄</div>
        <p>{file.type || "File"}</p>
      </div>
    {/if}

    <div class="preview-info">
      <div class="info-row">
        <span class="info-label">Name</span>
        <span class="info-value" title={file.name}>
          {file.name.length > 25
            ? file.name.substring(0, 25) + "..."
            : file.name}
        </span>
      </div>
      <div class="info-row">
        <span class="info-label">Type</span>
        <span class="info-value">{file.type || "unknown"}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Size</span>
        <span class="info-value">{filesAPI.formatFileSize(file.size)}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Date</span>
        <span class="info-value"
          >{new Date(file.uploaded_at).toLocaleString()}</span
        >
      </div>
    </div>
  </div>
{/if}

<style>
  .preview-panel {
    background: white;
    border-left: 1px solid var(--color-light-gray);
    padding: var(--spacing-md);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    width: 300px;
    flex-shrink: 0;
  }

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .preview-header h3 {
    margin: 0;
    color: var(--color-navy);
    font-size: 1.125rem;
    font-weight: 600;
  }

  .download-btn {
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.25rem;
    transition: all var(--transition-fast);
  }

  .download-btn:hover {
    opacity: 0.9;
    transform: scale(1.05);
  }

  .preview-image {
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #f8f9fa;
    border-radius: var(--radius-sm);
    padding: var(--spacing-md);
    min-height: 200px;
  }

  .preview-image img {
    max-width: 100%;
    max-height: 300px;
    border-radius: var(--radius-sm);
    object-fit: contain;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .preview-video {
    width: 100%;
    background: #000;
    border-radius: var(--radius-sm);
    padding: var(--spacing-md);
  }

  .preview-video video {
    width: 100%;
    max-height: 300px;
    border-radius: var(--radius-sm);
  }

  .preview-placeholder {
    width: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: #f8f9fa;
    border-radius: var(--radius-sm);
    padding: var(--spacing-lg);
    min-height: 200px;
  }

  .folder-icon,
  .file-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-sm);
  }

  .preview-placeholder p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    text-transform: capitalize;
  }

  .placeholder-hint {
    font-size: 0.75rem;
    margin-top: var(--spacing-xs) !important;
    opacity: 0.7;
  }

  .preview-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-xs) 0;
    border-bottom: 1px solid var(--color-light-gray);
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .info-label {
    font-weight: 600;
    color: var(--color-navy);
    font-size: 0.875rem;
  }

  .info-value {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
  }
</style>
