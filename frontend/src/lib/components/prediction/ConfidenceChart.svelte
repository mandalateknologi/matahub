<script lang="ts">
  import { onMount } from "svelte";
  import { Chart } from "chart.js";
  import { getConfidenceHistogramConfig } from "$lib/utils/chartConfig";
  import type { PredictionResult } from "@/lib/types";

  export let results: PredictionResult[];
  export let bins: number = 10;

  let chartCanvas: HTMLCanvasElement;
  let chart: Chart | null = null;

  // Extract confidence values from all results
  $: confidenceValues = results
    .flatMap((result) => {
      if (result.probabilities && result.probabilities.length > 0) {
        // For classification, use the top confidence
        return [Math.max(...result.probabilities)];
      } else if (
        result.confidence !== undefined &&
        result.confidence !== null
      ) {
        // For detection/segmentation
        return [result.confidence];
      }
      return [];
    })
    .filter((val) => val !== undefined && val !== null);

  // Calculate statistics
  $: stats =
    confidenceValues.length > 0
      ? {
          mean:
            confidenceValues.reduce((a, b) => a + b, 0) /
            confidenceValues.length,
          min: Math.min(...confidenceValues),
          max: Math.max(...confidenceValues),
          count: confidenceValues.length,
        }
      : null;

  onMount(() => {
    return () => {
      if (chart) {
        chart.destroy();
      }
    };
  });

  // Create or update chart when data changes
  $: if (chartCanvas && confidenceValues.length > 0) {
    if (chart) {
      chart.destroy();
    }

    const config = getConfidenceHistogramConfig(confidenceValues, bins);
    chart = new Chart(chartCanvas, config);
  }
</script>

<div class="confidence-chart">
  {#if confidenceValues.length > 0}
    <div class="header">
      <h3>Confidence Distribution</h3>
      <span class="badge">{stats?.count || 0} Predictions</span>
    </div>

    <!-- Chart Visualization -->
    <div class="chart-container">
      <canvas bind:this={chartCanvas}></canvas>
    </div>

    <!-- Statistics -->
    {#if stats}
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-label">Mean Confidence</div>
          <div class="stat-value">{(stats.mean * 100).toFixed(2)}%</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Min Confidence</div>
          <div class="stat-value">{(stats.min * 100).toFixed(2)}%</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Max Confidence</div>
          <div class="stat-value">{(stats.max * 100).toFixed(2)}%</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">Total Count</div>
          <div class="stat-value">{stats.count}</div>
        </div>
      </div>
    {/if}

    <!-- Info Text -->
    <div class="info-text">
      <p>
        This histogram shows the distribution of confidence scores across all
        predictions. Higher confidence values indicate more certain predictions.
      </p>
    </div>
  {:else}
    <div class="no-data">
      <p>No confidence data available</p>
      <span class="hint">Run predictions to see confidence distribution</span>
    </div>
  {/if}
</div>

<style>
  .confidence-chart {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .header h3 {
    margin: 0;
    color: var(--color-navy);
    font-size: 1.25rem;
  }

  .badge {
    background: var(--color-info);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .chart-container {
    height: 300px;
    margin-bottom: 1.5rem;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .stat-item {
    padding: 1rem;
    background: var(--color-light-gray);
    border-radius: 6px;
    text-align: center;
  }

  .stat-label {
    font-size: 0.875rem;
    color: var(--color-gray);
    margin-bottom: 0.5rem;
  }

  .stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-navy);
  }

  .info-text {
    padding: 1rem;
    background: #eff6ff;
    border-left: 4px solid var(--color-info);
    border-radius: 6px;
  }

  .info-text p {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-navy);
    line-height: 1.5;
  }

  .no-data {
    text-align: center;
    padding: 3rem 2rem;
  }

  .no-data p {
    margin: 0 0 0.5rem 0;
    color: var(--color-gray);
    font-size: 1rem;
  }

  .no-data .hint {
    font-size: 0.875rem;
    color: var(--color-gray);
    opacity: 0.7;
  }
</style>
