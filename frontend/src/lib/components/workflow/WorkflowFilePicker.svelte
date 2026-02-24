<script lang="ts">
  import { onMount } from "svelte";
  import { filesAPI, type FileItem } from "../../api/files";
  import TreeView from "../FileManager/TreeView.svelte";
  import FileList from "../FileManager/FileList.svelte";
  import Breadcrumbs from "../FileManager/Breadcrumbs.svelte";
  import LoadingSkeleton from "../FileManager/LoadingSkeleton.svelte";
  import { uiStore } from "../../stores/uiStore";

  // Props
  let {
    workflowId = null,
    selectionMode = "folder",
    fileType = "any",
    multiSelect = false,
    onSelect,
    onClose,
  }: {
    workflowId?: number | null;
    selectionMode?: "file" | "folder";
    fileType?: "image" | "video" | "any";
    multiSelect?: boolean;
    onSelect: (selection: string | string[]) => void;
    onClose: () => void;
  } = $props();

  // State
  let loading = $state(true);
  let files = $state<FileItem[]>([]);
  let currentFolder = $state<string>("shared");
  let selectedFiles = $state<Set<number>>(new Set());
  let selectedFolderPath = $state<string>("");

  // Load files on mount
  onMount(async () => {
    await loadFiles();
  });

  // Reactive: Auto-select folder when navigating
  $effect(() => {
    if (selectionMode === "folder") {
      selectedFolderPath = currentFolder;
    }
  });

  // Load all files for tree/list view
  async function loadFiles() {
    loading = true;
    try {
      const response = await filesAPI.listFiles();
      console.log("API response:", response);
      const allFiles = Array.isArray(response) ? response : [];
      console.log("All files:", allFiles);
      console.log(
        "Sample file object:",
        allFiles[0] ? JSON.stringify(allFiles[0], null, 2) : "no files"
      );

      // Filter files based on workflow context AND file type in a single pass
      if (workflowId) {
        // Show only shared folder and current workflow's folder
        const workflowFolderPrefix = `workflows/${workflowId}`;
        files = allFiles.filter((f) => {
          // Check folder path
          const folderMatch =
            f.folder_path === "shared" ||
            f.folder_path.startsWith("shared/") ||
            f.folder_path === workflowFolderPrefix ||
            f.folder_path.startsWith(workflowFolderPrefix + "/");

          if (!folderMatch) return false;

          // Check file type if in file selection mode
          if (selectionMode === "file" && fileType !== "any") {
            return f.type === "folder" || f.type === fileType;
          }

          return true;
        });
      } else {
        // Show shared and all workflow folders
        files = allFiles.filter((f) => {
          // Check folder path
          const folderMatch =
            f.folder_path === "shared" ||
            f.folder_path.startsWith("shared/") ||
            f.folder_path === "workflows" ||
            f.folder_path.startsWith("workflows/");

          if (!folderMatch) return false;

          // Check file type if in file selection mode
          if (selectionMode === "file" && fileType !== "any") {
            return f.type === "folder" || f.type === fileType;
          }

          return true;
        });
      }

      console.log("[snapshot] Filtered files:", $state.snapshot(files));
      console.log("Current folder:", currentFolder);
      const filesInCurrentFolder = files.filter(
        (f) => f.folder_path === currentFolder
      );
      console.log(
        "[snapshot] Files in current folder:",
        $state.snapshot(filesInCurrentFolder)
      );

      console.log(
        "[loadFiles] FINAL files.length:",
        files.length,
        "snapshot:",
        $state.snapshot(files).length
      );
    } catch (error: any) {
      uiStore.showToast("Failed to load files", "error");
      console.error("Load files error:", error);
    } finally {
      loading = false;
      console.log("[loadFiles] After finally - files.length:", files.length);
    }
  }

  // Handle folder navigation from TreeView or FileList
  function handleNavigate(folder: string) {
    currentFolder = folder;
    if (selectionMode === "folder") {
      selectedFolderPath = currentFolder;
    }
  }

  // Handle file selection from FileList
  function handleSelect(selected: Set<number>) {
    if (selectionMode === "file") {
      selectedFiles = selected;
    }
  }

  // Handle confirm button
  function handleConfirm() {
    if (selectionMode === "folder") {
      // Return selected folder path
      onSelect(selectedFolderPath);
    } else {
      // Return selected file(s)
      const selectedFileObjects = files.filter((f) => selectedFiles.has(f.id));
      const paths = selectedFileObjects.map(
        (f) => f.folder_path + "/" + f.name
      );
      onSelect(multiSelect ? paths : paths[0]);
    }
    handleClose();
  }

  // Handle cancel button
  function handleClose() {
    onClose();
  }

  // Handle backdrop click
  function handleBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  }

  // Computed: Can confirm?
  let canConfirm = $derived(
    selectionMode === "folder"
      ? selectedFolderPath.length > 0
      : selectedFiles.size > 0
  );
</script>

<!-- Modal Backdrop -->
<div class="modal-backdrop" on:click={handleBackdropClick}>
  <div class="modal-content" on:click|stopPropagation>
    <!-- Header -->
    <div class="modal-header">
      <h2>
        {#if selectionMode === "folder"}
          Select Folder
        {:else}
          Select Files
        {/if}
      </h2>
      <button class="close-btn" on:click={handleClose} title="Close">×</button>
    </div>

    <!-- Breadcrumbs -->
    <div class="breadcrumbs-container">
      <Breadcrumbs
        {currentFolder}
        onNavigate={(path) => {
          currentFolder = path;
          if (selectionMode === "folder") {
            selectedFolderPath = currentFolder;
          }
        }}
      />
    </div>

    <!-- Main Content -->
    <div class="picker-content">
      {#if loading}
        <LoadingSkeleton count={10} />
      {:else}
        <!-- TreeView Sidebar -->
        <div class="tree-sidebar">
          <TreeView
            {files}
            {currentFolder}
            on:navigate={(e) => handleNavigate(e.detail)}
          />
        </div>

        <!-- File List -->
        <div class="file-list-container">
          {#key files.length}
            {@const filesSnapshot = $state.snapshot(files)}
            {console.log(
              "[WorkflowFilePicker] Before FileList - files.length:",
              files.length,
              "snapshot:",
              filesSnapshot.length
            )}
            <FileList
              {files}
              {currentFolder}
              {selectedFiles}
              onNavigate={handleNavigate}
              onSelect={handleSelect}
            />
          {/key}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="modal-footer">
      <div class="selection-info">
        {#if selectionMode === "folder"}
          <span
            >Selected Folder: <strong>{selectedFolderPath || "None"}</strong
            ></span
          >
        {:else}
          <span>Selected Files: <strong>{selectedFiles.size}</strong></span>
        {/if}
      </div>
      <div class="footer-actions">
        <button class="btn btn-secondary" on:click={handleClose}>Cancel</button>
        <button
          class="btn btn-primary"
          on:click={handleConfirm}
          disabled={!canConfirm}
        >
          Confirm
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal-content {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 1200px;
    height: 80vh;
    max-height: 800px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease;
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

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #e0e0e0;
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
    color: #999;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.2s;
  }

  .close-btn:hover {
    background: #f0f0f0;
    color: #333;
  }

  .breadcrumbs-container {
    padding: 1rem 2rem;
    border-bottom: 1px solid #e0e0e0;
    background: #f9fafb;
  }

  .picker-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .tree-sidebar {
    width: 280px;
    border-right: 1px solid #e0e0e0;
    overflow-y: auto;
    background: #fafafa;
  }

  .file-list-container {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem 2rem;
    border-top: 1px solid #e0e0e0;
    background: #f9fafb;
  }

  .selection-info {
    font-size: 0.9rem;
    color: #666;
  }

  .selection-info strong {
    color: var(--color-navy);
    font-weight: 600;
  }

  .footer-actions {
    display: flex;
    gap: 1rem;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    border: none;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
    font-weight: 600;
    font-size: 1rem;
    padding: 0.875rem 2rem;
    box-shadow: 0 2px 8px rgba(225, 96, 76, 0.3);
  }

  .btn-primary:hover:not(:disabled) {
    background: #d14a36;
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.4);
    transform: translateY(-1px);
  }

  .btn-primary:disabled {
    background: #ccc;
    cursor: not-allowed;
    box-shadow: none;
  }

  .btn-secondary {
    background: white;
    color: #666;
    border: 1px solid #ddd;
  }

  .btn-secondary:hover {
    background: #f5f5f5;
    border-color: #999;
  }
</style>
