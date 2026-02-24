<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { FileItem } from "../../api/files";
  import TreeNode from "./TreeNode.svelte";

  export let files: FileItem[] = [];
  export let currentFolder: string = "shared";

  const dispatch = createEventDispatcher();

  // Build folder tree structure
  interface TreeNode {
    name: string;
    path: string;
    children: TreeNode[];
    expanded: boolean;
    isFolder: boolean;
  }

  // System folders that should always appear at root
  const SYSTEM_FOLDERS = ["workflows", "shared", "trash"];

  $: folderTree = buildFolderTree(files);

  function buildFolderTree(files: FileItem[]): TreeNode[] {
    const rootNodes: TreeNode[] = [];
    const pathMap = new Map<string, TreeNode>();

    // Create root system folders first
    SYSTEM_FOLDERS.forEach((folderName) => {
      const icon = getFolderIcon(folderName);
      const node: TreeNode = {
        name: `${icon} ${capitalize(folderName)}`,
        path: folderName,
        children: [],
        expanded:
          currentFolder === folderName ||
          currentFolder.startsWith(folderName + "/"),
        isFolder: true,
      };
      pathMap.set(folderName, node);
      rootNodes.push(node);
    });

    // Collect all unique folder paths from files
    const allPaths = new Set<string>();

    files.forEach((file) => {
      // Only add paths for actual folders in the file list
      if (file.type === "folder") {
        const folderFullPath = file.folder_path + "/" + file.name;
        allPaths.add(folderFullPath);
      }

      // Also add intermediate parent paths that don't exist yet
      // but ONLY if they're not system folder names appearing in wrong places
      const parts = file.folder_path.split("/").filter((p) => p);
      for (let i = 1; i < parts.length; i++) {
        const intermediatePath = parts.slice(0, i).join("/");
        // Don't add if this creates a system folder as a child
        const folderName = parts[i - 1];
        if (!SYSTEM_FOLDERS.includes(folderName) || i === 1) {
          allPaths.add(intermediatePath);
        }
      }
    });

    // Remove any system folders from the path list (they're already at root)
    SYSTEM_FOLDERS.forEach((sf) => allPaths.delete(sf));

    // Sort paths by depth to ensure parents are processed before children
    const sortedPaths = Array.from(allPaths).sort((a, b) => {
      const depthA = a.split("/").length;
      const depthB = b.split("/").length;
      if (depthA !== depthB) return depthA - depthB;
      return a.localeCompare(b);
    });

    // Build tree structure
    sortedPaths.forEach((path) => {
      // Skip if already processed
      if (pathMap.has(path)) return;

      const parts = path.split("/");
      const folderName = parts[parts.length - 1];
      const parentPath = parts.slice(0, -1).join("/");

      // Skip creating nodes for system folder names in wrong places
      if (SYSTEM_FOLDERS.includes(folderName) && parts.length > 1) {
        return;
      }

      // Create node
      const node: TreeNode = {
        name: `📁 ${folderName}`,
        path: path,
        children: [],
        expanded:
          currentFolder === path || currentFolder.startsWith(path + "/"),
        isFolder: true,
      };
      pathMap.set(path, node);

      // Add to parent (should exist because we process by depth)
      const parentNode = pathMap.get(parentPath);
      if (parentNode) {
        // Check if child already exists to avoid duplicates
        if (!parentNode.children.some((c) => c.path === path)) {
          parentNode.children.push(node);
        }
      }
    });

    return rootNodes;
  }

  function getFolderIcon(folderName: string): string {
    const icons: Record<string, string> = {
      workflows: "⚙️",
      shared: "👥",
      trash: "🗑️",
    };
    return icons[folderName] || "📁";
  }

  function capitalize(str: string): string {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function handleNavigate(event: CustomEvent) {
    dispatch("navigate", event.detail);
  }

  function handleToggle() {
    // Trigger reactivity when tree is toggled
    folderTree = [...folderTree];
  }
</script>

<div class="tree-view">
  <div class="tree-header">
    <h3>📂 My Files</h3>
  </div>

  <div class="tree-content">
    {#each folderTree as node}
      <TreeNode
        {node}
        {currentFolder}
        depth={0}
        on:navigate={handleNavigate}
        on:toggle={handleToggle}
      />
    {/each}
  </div>
</div>

<style>
  .tree-view {
    width: 250px;
    background: #f8f9fa;
    border-right: 1px solid #dee2e6;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .tree-header {
    padding: var(--spacing-md);
    background: var(--color-navy);
    color: white;
    border-bottom: 1px solid #dee2e6;
  }

  .tree-header h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
  }

  .tree-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-sm) 0;
  }

  /* Scrollbar styling */
  .tree-content::-webkit-scrollbar {
    width: 6px;
  }

  .tree-content::-webkit-scrollbar-track {
    background: transparent;
  }

  .tree-content::-webkit-scrollbar-thumb {
    background: #cbd5e0;
    border-radius: 3px;
  }

  .tree-content::-webkit-scrollbar-thumb:hover {
    background: #a0aec0;
  }
</style>
