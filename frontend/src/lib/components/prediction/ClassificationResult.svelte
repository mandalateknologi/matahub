<script lang="ts">
  import { onMount } from "svelte";
  import { Chart } from "chart.js";
  import { getClassificationBarConfig } from "$lib/utils/chartConfig";
  import type { PredictionResponse } from "@/lib/types";

  export let result: PredictionResponse;
  export let topK: number = 5;

  let chartCanvas: HTMLCanvasElement;
  let chart: Chart | null = null;

  // Extract top-K classes with highest confidence
  $: topClasses =
    result.classes && result.probabilities
      ? result.classes
          .map((className, idx) => ({
            name: className,
            confidence: result.probabilities![idx],
          }))
          .sort((a, b) => b.confidence - a.confidence)
          .slice(0, topK)
      : [];

  $: hasClassificationData =
    result.classes && result.probabilities && result.classes.length > 0;

  onMount(() => {
    return () => {
      if (chart) {
        chart.destroy();
      }
    };
  });

  // Create or update chart when data changes
  $: if (chartCanvas && hasClassificationData && topClasses.length > 0) {
    if (chart) {
      chart.destroy();
    }

    const labels = topClasses.map((c) => c.name);
    const data = topClasses.map((c) => c.confidence);

    const config = getClassificationBarConfig(labels, data);
    chart = new Chart(chartCanvas, config);
  }

  function getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return "var(--color-success)";
    if (confidence >= 0.5) return "var(--color-warning)";
    return "var(--color-error)";
  }
</script>

<div class="classification-result">
  {#if hasClassificationData}
    <div class="header">
      <h3>Classification Results</h3>
      <span class="badge">Top {topK} Predictions</span>
    </div>

    <!-- Chart Visualization -->
    <div class="chart-container">
      <canvas bind:this={chartCanvas}></canvas>
    </div>

    <!-- Detailed List -->
    <div class="predictions-list">
      {#each topClasses as prediction, idx}
        <div class="prediction-item">
          <div class="rank">#{idx + 1}</div>
          <div class="class-info">
            <div class="class-name">{prediction.name}</div>
            <div class="confidence-bar">
              <div
                class="confidence-fill"
                style="width: {prediction.confidence *
                  100}%; background-color: {getConfidenceColor(
                  prediction.confidence
                )}"
              ></div>
            </div>
          </div>
          <div
            class="confidence-value"
            style="color: {getConfidenceColor(prediction.confidence)}"
          >
            {(prediction.confidence * 100).toFixed(2)}%
          </div>
        </div>
      {/each}
    </div>

    <!-- Top Prediction Highlight -->
    {#if topClasses.length > 0}
      <div class="top-prediction">
        <span class="label">Predicted Class:</span>
        <span class="value">{topClasses[0].name}</span>
        <span
          class="confidence"
          style="color: {getConfidenceColor(topClasses[0].confidence)}"
        >
          {(topClasses[0].confidence * 100).toFixed(2)}%
        </span>
      </div>
    {/if}
  {:else}
    <div class="no-data">
      <p>No classification data available</p>
    </div>
  {/if}
</div>

<style>
  .classification-result {
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
    background: var(--color-accent);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .chart-container {
    height: 300px;
    margin-bottom: 2rem;
  }

  .predictions-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .prediction-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    background: var(--color-light-gray);
    border-radius: 6px;
    transition:
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
  }

  .prediction-item:hover {
    transform: translateX(4px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .rank {
    font-weight: 700;
    color: var(--color-navy);
    font-size: 1.125rem;
    min-width: 2rem;
  }

  .class-info {
    flex: 1;
    min-width: 0;
  }

  .class-name {
    font-weight: 600;
    color: var(--color-navy);
    margin-bottom: 0.25rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .confidence-bar {
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
  }

  .confidence-fill {
    height: 100%;
    border-radius: 4px;
    transition: width var(--transition-base);
  }

  .confidence-value {
    font-weight: 700;
    font-size: 1rem;
    min-width: 4rem;
    text-align: right;
  }

  .top-prediction {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: linear-gradient(135deg, var(--color-navy) 0%, #2d4458 100%);
    border-radius: 8px;
    color: white;
  }

  .top-prediction .label {
    font-weight: 600;
    opacity: 0.9;
  }

  .top-prediction .value {
    flex: 1;
    font-weight: 700;
    font-size: 1.125rem;
  }

  .top-prediction .confidence {
    font-weight: 700;
    font-size: 1.25rem;
    padding: 0.25rem 0.75rem;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 6px;
  }

  .no-data {
    text-align: center;
    padding: 2rem;
    color: var(--color-gray);
  }

  .no-data p {
    margin: 0;
  }
</style>
