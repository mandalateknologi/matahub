<script lang="ts">
  import { Filemanager, Willow } from "@svar-ui/svelte-filemanager";
  import type { FileItem } from "../../api/files";
  import { createEventDispatcher, onMount } from "svelte";
  import { filesAPI } from "../../api/files";

  export let files: FileItem[] = [];

  const dispatch = createEventDispatcher();

  let api: any;
  let selectedFile: FileItem | null = null;
  let currentPath: string = "/Shared"; // Track current navigation path in SVAR

  /**
   * Transform ATVISION FileItem[] to SVAR data format
   * SVAR expects flat array with parent property for hierarchy
   * Example: { id: "/Workflows/1", value: "1", type: "folder", parent: "/Workflows" }
   */
  function transformToSvarData(files: FileItem[]): any[] {
    // Add root folders to SVAR data
    const rootFolders = [
      { id: "/Workflows", value: "Workflows", type: "folder", parent: "/" },
      { id: "/Shared", value: "Shared", type: "folder", parent: "/" },
      { id: "/Trash", value: "Trash", type: "folder", parent: "/" },
    ];

    // Filter out ONLY the root folder entries themselves from backend
    // (workflows, shared, trash folders at root level)
    // Keep all files and subfolders within these directories
    const filteredFiles = files.filter((file) => {
      // Only exclude if it's a folder type AND the name matches root folder names
      // AND it's at the root level (folder_path equals the folder name)
      const isRootFolderEntry =
        file.type === "folder" &&
        (file.name === "workflows" ||
          file.name === "shared" ||
          file.name === "trash") &&
        file.folder_path === file.name;

      return !isRootFolderEntry;
    });

    const svarFiles = filteredFiles.map((file) => {
      // Normalize folder_path to match root folder names
      const pathParts = file.folder_path.split("/");
      const rootFolder = pathParts[0]; // 'workflows', 'shared', or 'trash'
      const capitalizedRoot =
        rootFolder.charAt(0).toUpperCase() + rootFolder.slice(1);

      // Build hierarchical ID and parent
      let id: string;
      let parent: string;

      if (
        file.folder_path === "workflows" ||
        file.folder_path === "shared" ||
        file.folder_path === "trash"
      ) {
        // File/folder directly in root folder (e.g., workflows/file.txt)
        id = `/${capitalizedRoot}/${file.name}`;
        parent = `/${capitalizedRoot}`;
      } else {
        // File/folder in subfolder (e.g., workflows/subfolder/file.txt)
        const subPath = pathParts.slice(1).join("/");
        id = `/${capitalizedRoot}/${subPath}/${file.name}`;

        // Parent is everything except the file name
        const parentParts = pathParts.slice(1);
        if (parentParts.length > 0) {
          parent = `/${capitalizedRoot}/${parentParts.join("/")}`;
        } else {
          parent = `/${capitalizedRoot}`;
        }
      }

      return {
        id: id,
        value: file.name, // SVAR uses "value" for display name
        type: file.type === "folder" ? "folder" : "file",
        size: file.size,
        date: new Date(file.uploaded_at).toISOString(),
        parent: parent,
        ext: file.type === "folder" ? undefined : getFileExtension(file.name),
        // Additional metadata for our use
        atv_id: file.id,
        atv_path: file.folder_path,
        atv_deleted: file.is_deleted,
        atv_system: file.is_system_folder,
      };
    });

    return [...rootFolders, ...svarFiles];
  }

  function getFileExtension(filename: string): string {
    const parts = filename.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
  }

  $: svarData = transformToSvarData(files);

  /**
   * Previews function for SVAR FileManager
   * Returns image URL for thumbnails and previews
   */
  function previews(file: any) {
    // Only return preview URL for image files
    if (file && file.atv_id && file.type === "file") {
      // Get the original file from our files array
      const originalFile = files.find((f) => f.id === file.atv_id);
      if (originalFile && originalFile.type === "image") {
        return filesAPI.getPreviewUrl(originalFile.id);
      }
    }
    return null;
  }

  /**
   * Handle file/folder selection
   */
  function handleSelect(event: CustomEvent) {
    const selection = event.detail;
    console.log("SVAR select event:", selection);

    // Try to get current path from API
    if (api && api.getState) {
      const state = api.getState();
      console.log("SVAR state:", state);
      if (state && state.path) {
        const backendPath = state.path
          .substring(1)
          .toLowerCase()
          .replace(/\/+/g, "/");
        console.log("Current path from SVAR API:", backendPath);
        dispatch("navigate", backendPath);
      }
    }

    if (selection && Array.isArray(selection)) {
      // Update selected file for preview
      if (selection.length === 1 && selection[0].atv_id) {
        selectedFile = files.find((f) => f.id === selection[0].atv_id) || null;
      } else {
        selectedFile = null;
      }

      const selectedIds = selection
        .map((item: any) => item.atv_id)
        .filter((id: any) => id !== undefined);
      dispatch("select", selectedIds);
    }
  }

  /**
   * Handle file/folder open (double-click)
   */
  function handleOpen(event: CustomEvent) {
    const item = event.detail;
    if (item && item.atv_id) {
      const file = files.find((f) => f.id === item.atv_id);
      if (file) {
        dispatch("open", file);
      }
    }
  }

  /**
   * Handle context menu
   */
  function handleContextMenu(event: CustomEvent) {
    const { file: item, event: nativeEvent } = event.detail || {};
    if (item && item.atv_id) {
      const file = files.find((f) => f.id === item.atv_id);
      if (file) {
        dispatch("contextmenu", { file, event: nativeEvent });
      }
    }
  }

  /**
   * Expose API methods for parent component
   */
  export function getApi() {
    return api;
  }

  export function refreshData() {
    if (api && api.exec) {
      // Refresh the file manager data
      api.exec("set-data", { data: svarData });
    }
  }

  /**
   * Initialize SVAR FileManager API
   */
  function init(apiInstance: any) {
    api = apiInstance;

    // Listen to folder navigation by tracking current path from API state
    api.on("select-file", ({ id, toggle, range }) => {
      if (!id) return;
      console.log(`Selected file ID is ${id}`);

      // Get current path from SVAR state after selection
      setTimeout(() => {
        if (api && api.getState) {
          const state = api.getState();
          console.log("SVAR state after select:", state);

          if (state && state.path) {
            // Convert SVAR path (/Workflows/2) to backend format (workflows/2)
            const backendPath = state.path
              .substring(1)
              .toLowerCase()
              .replace(/\/+/g, "/");
            console.log("Current folder path:", backendPath);

            // Only dispatch if path actually changed
            if (backendPath !== currentPath.substring(1).toLowerCase()) {
              currentPath = state.path;
              dispatch("navigate", backendPath);
            }
          }
        }
      }, 100); // Small delay to ensure SVAR has updated its state
    });
  }

  // Always hide SVAR's "Add New" button (using custom buttons instead)
  onMount(() => {
    const styleId = "svar-toolbar-style";
    let styleEl = document.getElementById(styleId) as HTMLStyleElement;

    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = styleId;
      document.head.appendChild(styleEl);
    }

    // Permanently hide SVAR's Add New button
    styleEl.textContent =
      '.wx-filemanager .wx-toolbar .wx-button[data-action="add"] { display: none !important; }';
  });
</script>

<Willow>
  <div class="svar-wrapper" class:has-preview={selectedFile !== null}>
    <Filemanager
      bind:this={api}
      data={svarData}
      mode="table"
      on:select={handleSelect}
      on:open={handleOpen}
      {previews}
      {init}
    />

    {#if selectedFile}
      <div class="preview-panel">
        <div class="preview-header">
          <h3>Information</h3>
          {#if selectedFile.type !== "folder"}
            <button
              class="download-btn"
              on:click={() =>
                filesAPI.downloadFile(selectedFile.id, selectedFile.name)}
              title="Download file"
            >
              ⬇
            </button>
          {/if}
        </div>

        {#if selectedFile.type === "image"}
          <div class="preview-image">
            <img
              src={filesAPI.getPreviewUrl(selectedFile.id)}
              alt={selectedFile.name}
              on:error={(e) => {
                e.currentTarget.src =
                  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="200"%3E%3Crect fill="%23f0f0f0" width="200" height="200"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3ENo Preview%3C/text%3E%3C/svg%3E';
              }}
            />
          </div>
        {:else if selectedFile.type === "video"}
          <div class="preview-video">
            <video controls>
              <source
                src={filesAPI.getPreviewUrl(selectedFile.id)}
                type="video/mp4"
              />
              <track kind="captions" />
              Your browser does not support the video tag.
            </video>
          </div>
        {:else if selectedFile.type === "folder"}
          <div class="preview-placeholder">
            <div class="folder-icon">📁</div>
            <p>Folder</p>
          </div>
        {:else}
          <div class="preview-placeholder">
            <div class="file-icon">📄</div>
            <p>{selectedFile.type || "File"}</p>
          </div>
        {/if}

        <div class="preview-info">
          <div class="info-row">
            <span class="info-label">Name</span>
            <span class="info-value" title={selectedFile.name}>
              {selectedFile.name.length > 25
                ? selectedFile.name.substring(0, 25) + "..."
                : selectedFile.name}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">Type</span>
            <span class="info-value">{selectedFile.type || "unknown"}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Size</span>
            <span class="info-value"
              >{filesAPI.formatFileSize(selectedFile.size)}</span
            >
          </div>
          <div class="info-row">
            <span class="info-label">Date</span>
            <span class="info-value"
              >{new Date(selectedFile.uploaded_at).toLocaleString()}</span
            >
          </div>
        </div>
      </div>
    {/if}
  </div>
</Willow>

<style>
  .svar-wrapper {
    width: 100%;
    height: 100%;
    min-height: 500px;
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  .svar-wrapper.has-preview {
    grid-template-columns: 1fr 300px;
  }

  .preview-panel {
    background: white;
    border-left: 1px solid var(--color-light-gray);
    padding: var(--spacing-md);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .preview-header h3 {
    margin: 0;
    color: var(--color-navy);
    font-size: 1.125rem;
    font-weight: 600;
  }

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
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

  .download-btn:active {
    transform: scale(0.95);
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
    display: flex;
    justify-content: center;
    align-items: center;
    background: #000;
    border-radius: var(--radius-sm);
    padding: var(--spacing-md);
    min-height: 200px;
  }

  .preview-video video {
    max-width: 100%;
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

  /* Override SVAR CSS variables to match ATVISION design system */
  :global(.wx-filemanager) {
    --wx-color-primary: var(--color-navy);
    --wx-color-primary-hover: var(--color-accent);
    --wx-color-font: var(--color-navy);
    --wx-font-family: var(--font-primary);
    --wx-border-radius: var(--radius-sm);
    --wx-background: white;
  }

  /* Customize file manager toolbar */
  :global(.wx-filemanager .wx-toolbar) {
    background: var(--color-bg-light1);
    border-bottom: 1px solid var(--color-light-gray);
    padding: var(--spacing-sm);
  }

  /* Customize file items */
  :global(.wx-filemanager .wx-file-item) {
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
  }

  :global(.wx-filemanager .wx-file-item:hover) {
    background: var(--color-light-gray);
  }

  :global(.wx-filemanager .wx-file-item.selected) {
    background: #e8f4f8;
    border-color: var(--color-accent);
  }

  /* Customize folder tree */
  :global(.wx-filemanager .wx-tree-item) {
    padding: var(--spacing-xs) var(--spacing-sm);
  }

  :global(.wx-filemanager .wx-tree-item.active) {
    background: var(--color-accent);
    color: white;
  }
</style>
