<script lang="ts">
  /**
   * StatsPanel - Displays detection results and statistics
   *
   * Extracted from capture page (Phase 1) to improve code organization.
   * Shows detected objects with confidence scores and summary statistics.
   */

  // Svelte 5: Props using $props() rune
  let {
    detectionResults = [],
    showFrameStats = false,
    frameWidth = 0,
    frameHeight = 0,
    fps = 0,
  }: {
    detectionResults?: Array<{
      class_name: string;
      confidence: number;
    }>;
    showFrameStats?: boolean;
    frameWidth?: number;
    frameHeight?: number;
    fps?: number;
  } = $props();
</script>

<div class="results-area">
  <h3>Results</h3>
  <div class="results-list">
    {#if detectionResults.length > 0}
      {#each detectionResults as result}
        <span class="result-badge">
          {result.class_name} ({(result.confidence * 100).toFixed(0)}%)
        </span>
      {/each}
    {:else}
      <p class="text-muted">No results yet</p>
    {/if}
  </div>

  {#if detectionResults.length > 0}
    <div class="results-summary">
      Total: {detectionResults.length} object{detectionResults.length !== 1
        ? "s"
        : ""}
    </div>
  {/if}

  {#if showFrameStats && (frameWidth > 0 || frameHeight > 0 || fps > 0)}
    <div class="frame-stats">
      {#if frameWidth > 0 && frameHeight > 0}
        <div class="stat-item">
          <span class="stat-label">Resolution:</span>
          <span class="stat-value">{frameWidth}×{frameHeight}</span>
        </div>
      {/if}
      {#if fps > 0}
        <div class="stat-item">
          <span class="stat-label">FPS:</span>
          <span class="stat-value">{fps.toFixed(1)}</span>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .results-area {
    padding: 1rem;
    background-color: var(--color-bg-secondary, #f5f7fa);
    border-radius: 8px;
    margin-bottom: 1rem;
  }

  .results-area h3 {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
  }

  .results-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    min-height: 2rem;
  }

  .result-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    background-color: var(--color-accent, #e1604c);
    color: white;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .text-muted {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-tertiary, #adb5bd);
    font-style: italic;
  }

  .results-summary {
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border, #e1e4e8);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
  }

  .frame-stats {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border, #e1e4e8);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
  }

  .stat-label {
    color: var(--color-text-secondary, #6c757d);
  }

  .stat-value {
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
  }
</style>
