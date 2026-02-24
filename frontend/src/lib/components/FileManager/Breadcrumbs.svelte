<script lang="ts">
  let {
    currentFolder = "shared",
    onNavigate,
  }: {
    currentFolder?: string;
    onNavigate?: (path: string) => void;
  } = $props();

  let pathParts = $derived(currentFolder.split("/").filter((p) => p));

  function navigateToPath(index: number) {
    const newPath = pathParts.slice(0, index + 1).join("/");
    onNavigate?.(newPath);
  }

  function navigateToRoot() {
    onNavigate?.(pathParts[0] || "shared");
  }
</script>

<nav class="breadcrumbs">
  <button class="breadcrumb-item" on:click={navigateToRoot}>
    📁 My Files
  </button>

  {#each pathParts as part, index}
    <span class="separator">›</span>
    <button
      class="breadcrumb-item"
      class:active={index === pathParts.length - 1}
      on:click={() => navigateToPath(index)}
    >
      {part}
    </button>
  {/each}
</nav>

<style>
  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm) 0;
    flex-wrap: wrap;
  }

  .breadcrumb-item {
    background: none;
    border: none;
    color: var(--color-navy);
    font-size: 0.875rem;
    cursor: pointer;
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: 4px;
    transition: all var(--transition-fast);
  }

  .breadcrumb-item:hover {
    background: var(--color-light-gray);
  }

  .breadcrumb-item.active {
    font-weight: 600;
    color: var(--color-accent);
    cursor: default;
  }

  .breadcrumb-item.active:hover {
    background: none;
  }

  .separator {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }
</style>
