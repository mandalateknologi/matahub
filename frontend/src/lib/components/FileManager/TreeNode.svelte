<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let node: any;
  export let currentFolder: string;
  export let depth: number = 0;

  const dispatch = createEventDispatcher();

  function handleFolderClick(node: any) {
    dispatch("navigate", node.path);
  }

  function toggleExpand(node: any, event: Event) {
    event.stopPropagation();
    node.expanded = !node.expanded;
    dispatch("toggle");
  }
</script>

<div class="tree-node">
  <div
    class="tree-item"
    class:active={currentFolder === node.path}
    style="padding-left: {depth * 20 + 12}px"
    on:click={() => handleFolderClick(node)}
  >
    {#if node.children.length > 0}
      <button class="expand-btn" on:click={(e) => toggleExpand(node, e)}>
        {node.expanded ? "▼" : "▶"}
      </button>
    {:else}
      <span class="expand-spacer"></span>
    {/if}
    <span class="tree-label">{node.name}</span>
  </div>

  {#if node.expanded && node.children.length > 0}
    {#each node.children as child}
      <svelte:self
        node={child}
        {currentFolder}
        depth={depth + 1}
        on:navigate
        on:toggle
      />
    {/each}
  {/if}
</div>

<style>
  .tree-node {
    user-select: none;
  }

  .tree-item {
    display: flex;
    align-items: center;
    padding: var(--spacing-xs) var(--spacing-sm);
    cursor: pointer;
    transition: background-color var(--transition-fast);
    gap: var(--spacing-xs);
  }

  .tree-item:hover {
    background: rgba(0, 0, 0, 0.05);
  }

  .tree-item.active {
    background: var(--color-accent);
    color: white;
    font-weight: 600;
  }

  .tree-item.active:hover {
    background: var(--color-accent);
  }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: inherit;
    font-size: 10px;
    flex-shrink: 0;
  }

  .expand-btn:hover {
    opacity: 0.7;
  }

  .expand-spacer {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
  }

  .tree-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.9rem;
  }
</style>
