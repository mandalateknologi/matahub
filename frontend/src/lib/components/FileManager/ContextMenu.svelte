<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from "svelte";
  import type { FileItem } from "../../api/files";

  export let file: FileItem | null = null;
  export let x: number = 0;
  export let y: number = 0;
  export let visible: boolean = false;
  export let canUpload: boolean = true;
  export let isTrashFolder: boolean = false;
  export let isWorkflowFolder: boolean = false;

  const dispatch = createEventDispatcher();

  let menuElement: HTMLDivElement;

  function handleDownload() {
    dispatch("download", file);
    close();
  }

  function handlePreview() {
    dispatch("preview", file);
    close();
  }

  function handleMove() {
    dispatch("move", file);
    close();
  }

  function handleRename() {
    dispatch("rename", file);
    close();
  }

  function handleDelete() {
    dispatch("delete", file);
    close();
  }

  function handleRestore() {
    dispatch("restore", file);
    close();
  }

  function handlePermanentDelete() {
    dispatch("permanentDelete", file);
    close();
  }

  function close() {
    visible = false;
    dispatch("close");
  }

  function handleClickOutside(event: MouseEvent) {
    if (visible && menuElement && !menuElement.contains(event.target as Node)) {
      close();
    }
  }

  function handleEscape(event: KeyboardEvent) {
    if (event.key === "Escape" && visible) {
      close();
    }
  }

  onMount(() => {
    document.addEventListener("click", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
  });

  onDestroy(() => {
    document.removeEventListener("click", handleClickOutside);
    document.removeEventListener("keydown", handleEscape);
  });

  // Adjust position if menu would go off-screen
  $: if (visible && menuElement) {
    const rect = menuElement.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (x + rect.width > viewportWidth) {
      x = viewportWidth - rect.width - 10;
    }

    if (y + rect.height > viewportHeight) {
      y = viewportHeight - rect.height - 10;
    }
  }
</script>

{#if visible && file}
  <div
    bind:this={menuElement}
    class="context-menu"
    style="left: {x}px; top: {y}px;"
  >
    {#if file.type !== "folder"}
      <button class="menu-item" on:click={handleDownload}>
        <span class="menu-icon">⬇</span>
        <span class="menu-text">Download</span>
      </button>

      {#if file.type === "image" || file.type === "video"}
        <button class="menu-item" on:click={handlePreview}>
          <span class="menu-icon">👁</span>
          <span class="menu-text">Preview</span>
        </button>
      {/if}

      <div class="menu-divider"></div>
    {/if}

    {#if !isTrashFolder && canUpload}
      <button class="menu-item" on:click={handleMove}>
        <span class="menu-icon">📁</span>
        <span class="menu-text">Move to...</span>
      </button>

      <button class="menu-item" on:click={handleRename}>
        <span class="menu-icon">✏️</span>
        <span class="menu-text">Rename</span>
      </button>

      <div class="menu-divider"></div>
    {/if}

    {#if isTrashFolder}
      <button class="menu-item" on:click={handleRestore}>
        <span class="menu-icon">♻️</span>
        <span class="menu-text">Restore</span>
      </button>

      <button class="menu-item danger" on:click={handlePermanentDelete}>
        <span class="menu-icon">🗑️</span>
        <span class="menu-text">Delete Permanently</span>
      </button>
    {:else if !isWorkflowFolder}
      <button class="menu-item danger" on:click={handleDelete}>
        <span class="menu-icon">🗑️</span>
        <span class="menu-text">Move to Trash</span>
      </button>
    {/if}
  </div>
{/if}

<style>
  .context-menu {
    position: fixed;
    background: white;
    border: 1px solid var(--color-light-gray);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-lg);
    padding: var(--spacing-xs);
    min-width: 200px;
    z-index: 2000;
    animation: fadeIn 150ms ease-out;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  .menu-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    width: 100%;
    padding: var(--spacing-sm);
    background: transparent;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background var(--transition-fast);
    text-align: left;
    font-size: var(--font-size-sm);
  }

  .menu-item:hover {
    background: var(--color-light-gray);
  }

  .menu-item.danger:hover {
    background: var(--color-status-error);
    color: white;
  }

  .menu-icon {
    font-size: 1rem;
    flex-shrink: 0;
  }

  .menu-text {
    flex: 1;
  }

  .menu-divider {
    height: 1px;
    background: var(--color-light-gray);
    margin: var(--spacing-xs) 0;
  }
</style>
