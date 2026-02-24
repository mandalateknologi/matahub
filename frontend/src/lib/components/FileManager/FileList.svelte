<script lang="ts">
  import type { FileItem } from "../../api/files";
  import { filesAPI } from "../../api/files";

  // TypeScript Callback Signature Interfaces
  interface ContextMenuDetail {
    file: FileItem;
    event: MouseEvent;
  }

  let {
    files = [],
    currentFolder = "shared",
    selectedFiles = new Set(),
    onNavigate,
    onSelect,
    onContextMenu,
    onPreview,
  }: {
    files?: FileItem[];
    currentFolder?: string;
    selectedFiles?: Set<number>;
    onNavigate?: (folder: string) => void;
    onSelect?: (selected: Set<number>) => void;
    onContextMenu?: (detail: ContextMenuDetail) => void;
    onPreview?: (file: FileItem | null) => void;
  } = $props();

  let sortBy = $state<"name" | "size" | "date" | "type">("name");
  let sortDirection = $state<"asc" | "desc">("asc");

  // System folders that should not appear as items in the list
  const SYSTEM_FOLDERS = ["workflows", "shared", "trash"];

  // Filter files for current folder and exclude system folder entries
  let displayFiles = $derived.by(() => {
    const filtered = files.filter((f) => {
      // Must be in current folder
      if (f.folder_path !== currentFolder) return false;

      // Exclude system folders from appearing as items
      if (f.type === "folder" && SYSTEM_FOLDERS.includes(f.name)) return false;

      return true;
    });
    return filtered;
  });

  // Sort files
  let sortedFiles = $derived.by(() => {
    return [...displayFiles].sort((a, b) => {
      // Folders first
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (a.type !== "folder" && b.type === "folder") return 1;

      let comparison = 0;
      switch (sortBy) {
        case "name":
          comparison = a.name.localeCompare(b.name);
          break;
        case "size":
          comparison = a.size - b.size;
          break;
        case "date":
          comparison =
            new Date(a.uploaded_at).getTime() -
            new Date(b.uploaded_at).getTime();
          break;
        case "type":
          comparison = a.type.localeCompare(b.type);
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
  });

  function handleSort(column: typeof sortBy) {
    if (sortBy === column) {
      sortDirection = sortDirection === "asc" ? "desc" : "asc";
    } else {
      sortBy = column;
      sortDirection = "asc";
    }
  }

  function handleFileClick(file: FileItem, event: MouseEvent) {
    if (event.ctrlKey || event.metaKey) {
      // Toggle selection
      if (selectedFiles.has(file.id)) {
        selectedFiles.delete(file.id);
      } else {
        selectedFiles.add(file.id);
      }
      selectedFiles = selectedFiles;
    } else {
      // Single select
      selectedFiles = new Set([file.id]);
    }
    onSelect?.(selectedFiles);

    // Update preview when single file is selected
    if (selectedFiles.size === 1) {
      onPreview?.(file);
    } else {
      onPreview?.(null);
    }
  }

  function handleFileDoubleClick(file: FileItem) {
    if (file.type === "folder") {
      const newPath = file.folder_path + "/" + file.name;
      onNavigate?.(newPath);
    }
  }

  function handleContextMenu(file: FileItem, event: MouseEvent) {
    event.preventDefault();
    onContextMenu?.({ file, event });
  }

  function getFileIcon(fileType: string): string {
    switch (fileType) {
      case "image":
        return "🖼️";
      case "video":
        return "🎥";
      case "folder":
        return "📁";
      default:
        return "📄";
    }
  }
</script>

<div class="file-list">
  <table>
    <thead>
      <tr>
        <th class="col-name" on:click={() => handleSort("name")}>
          Name {sortBy === "name" ? (sortDirection === "asc" ? "↑" : "↓") : ""}
        </th>
        <th class="col-size" on:click={() => handleSort("size")}>
          Size {sortBy === "size" ? (sortDirection === "asc" ? "↑" : "↓") : ""}
        </th>
        <th class="col-date" on:click={() => handleSort("date")}>
          Modified {sortBy === "date"
            ? sortDirection === "asc"
              ? "↑"
              : "↓"
            : ""}
        </th>
        <th class="col-type" on:click={() => handleSort("type")}>
          Type {sortBy === "type" ? (sortDirection === "asc" ? "↑" : "↓") : ""}
        </th>
      </tr>
    </thead>
    <tbody>
      {#each sortedFiles as file (file.id)}
        <tr
          class:selected={selectedFiles.has(file.id)}
          on:click={(e) => handleFileClick(file, e)}
          on:dblclick={() => handleFileDoubleClick(file)}
          on:contextmenu={(e) => handleContextMenu(file, e)}
        >
          <td class="col-name">
            <span class="file-icon">{getFileIcon(file.type)}</span>
            <span class="file-name">{file.name}</span>
          </td>
          <td class="col-size">
            {file.type === "folder" ? "--" : filesAPI.formatFileSize(file.size)}
          </td>
          <td class="col-date">
            {new Date(file.uploaded_at).toLocaleDateString()}
          </td>
          <td class="col-type">
            {file.type}
          </td>
        </tr>
      {/each}

      {#if sortedFiles.length === 0}
        <tr class="empty-state">
          <td colspan="4">
            <div class="empty-message">📂 This folder is empty</div>
          </td>
        </tr>
      {/if}
    </tbody>
  </table>
</div>

<style>
  .file-list {
    flex: 1;
    overflow: auto;
    background: white;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    position: sticky;
    top: 0;
    background: var(--color-bg-light1);
    z-index: 10;
  }

  th {
    text-align: left;
    padding: var(--spacing-sm) var(--spacing-md);
    font-weight: 600;
    color: var(--color-navy);
    font-size: 0.875rem;
    border-bottom: 2px solid var(--color-light-gray);
    cursor: pointer;
    user-select: none;
  }

  th:hover {
    background: var(--color-light-gray);
  }

  tbody tr {
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  tbody tr:hover {
    background: #f8f9fa;
  }

  tbody tr.selected {
    background: #e8f4f8;
  }

  td {
    padding: var(--spacing-sm) var(--spacing-md);
    font-size: 0.875rem;
    color: var(--color-text);
  }

  .col-name {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .file-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .file-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .col-size,
  .col-date,
  .col-type {
    white-space: nowrap;
  }

  .empty-state td {
    padding: var(--spacing-xl);
  }

  .empty-message {
    text-align: center;
    color: var(--color-text-secondary);
    font-size: 1rem;
  }

  /* Column widths */
  .col-name {
    width: 50%;
  }
  .col-size {
    width: 15%;
  }
  .col-date {
    width: 20%;
  }
  .col-type {
    width: 15%;
  }
</style>
