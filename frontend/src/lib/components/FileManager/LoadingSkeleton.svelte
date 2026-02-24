<script lang="ts">
  export let count: number = 12;
  export let viewMode: 'grid' | 'list' = 'grid';
</script>

<div class="skeleton-container" class:grid-view={viewMode === 'grid'} class:list-view={viewMode === 'list'}>
  {#if viewMode === 'list'}
    <!-- Table header skeleton -->
    <div class="skeleton-header">
      <div class="skeleton-cell"></div>
      <div class="skeleton-cell"></div>
      <div class="skeleton-cell"></div>
      <div class="skeleton-cell"></div>
    </div>
  {/if}

  {#each Array(count) as _, i}
    <div class="skeleton-item" class:list-item={viewMode === 'list'}>
      {#if viewMode === 'grid'}
        <div class="skeleton-preview shimmer"></div>
        <div class="skeleton-name shimmer"></div>
        <div class="skeleton-meta shimmer"></div>
      {:else}
        <div class="skeleton-cell shimmer"></div>
        <div class="skeleton-cell shimmer"></div>
        <div class="skeleton-cell shimmer"></div>
        <div class="skeleton-cell shimmer"></div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .skeleton-container {
    display: grid;
    gap: var(--spacing-md);
  }

  .skeleton-container.grid-view {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }

  .skeleton-container.list-view {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .skeleton-header {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 150px;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-navy);
    border-radius: 4px 4px 0 0;
    height: 40px;
  }

  .skeleton-item {
    background: var(--color-light-gray);
    border-radius: var(--radius-sm);
    padding: var(--spacing-sm);
  }

  .skeleton-item.list-item {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 150px;
    gap: var(--spacing-sm);
    border-radius: 0;
    border-bottom: 1px solid #e0e0e0;
    padding: var(--spacing-sm) var(--spacing-md);
    background: white;
  }

  .skeleton-preview {
    aspect-ratio: 16/9;
    border-radius: 4px;
    background: #e0e0e0;
    margin-bottom: var(--spacing-sm);
  }

  .skeleton-name {
    height: 20px;
    border-radius: 4px;
    background: #e0e0e0;
    margin-bottom: var(--spacing-xs);
    width: 80%;
  }

  .skeleton-meta {
    height: 16px;
    border-radius: 4px;
    background: #e0e0e0;
    width: 60%;
  }

  .skeleton-cell {
    height: 20px;
    border-radius: 4px;
    background: #e0e0e0;
  }

  .shimmer {
    background: linear-gradient(
      90deg,
      #e0e0e0 0%,
      #f0f0f0 50%,
      #e0e0e0 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }
</style>
