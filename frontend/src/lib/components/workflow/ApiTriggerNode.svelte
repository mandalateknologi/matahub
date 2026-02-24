<script lang="ts">
  import { Position, Handle } from "@xyflow/svelte";
  import type { NodeProps } from "@xyflow/svelte";

  type $$Props = NodeProps;

  let { data, selected = false }: $$Props = $props();

  // Check if this node has validation errors
  const hasError = $derived(data.hasError || false);
  const executionState = $derived(data.executionState);

  // Get fields configuration
  const fields = $derived(data.config?.fields || []);
  const fieldCount = $derived(fields.length);

  function handleDelete(e: MouseEvent) {
    e.stopPropagation();
    if (data.onDelete) {
      data.onDelete(data.id);
    }
  }

  function handleConfigure(e: MouseEvent) {
    e.stopPropagation();
    if (data.onConfigure) {
      data.onConfigure(data.id);
    }
  }
</script>

<div
  class="api-trigger-node"
  class:selected
  class:error={hasError}
  class:pending={executionState === "pending"}
  class:running={executionState === "running"}
  class:completed={executionState === "completed"}
  class:failed={executionState === "failed"}
  class:skipped={executionState === "skipped"}
>
  <button
    class="delete-btn"
    on:click={handleDelete}
    aria-label="Delete node"
    title="Delete node"
  >
    ×
  </button>

  {#if executionState}
    <div class="status-badge {executionState}">
      {#if executionState === "running"}
        <span class="spinner">⟳</span>
      {:else if executionState === "completed"}
        <span class="check">✓</span>
      {:else if executionState === "failed"}
        <span class="cross">✗</span>
      {:else if executionState === "pending"}
        <span class="dot">●</span>
      {/if}
    </div>
  {/if}

  <div class="node-content">
    <div class="node-icon">🔌</div>
  </div>

  <div class="node-label">{data.label}</div>

  <div class="node-info">
    {#if fieldCount > 0}
      <span class="field-count"
        >{fieldCount} field{fieldCount !== 1 ? "s" : ""}</span
      >
    {:else}
      <span class="no-fields">No fields configured</span>
    {/if}
  </div>

  <div class="node-actions">
    <button
      class="configure-btn"
      on:click={handleConfigure}
      title="Configure API fields"
    >
      ⚙ Configure
    </button>
  </div>

  <!-- Output handle only (triggers don't have inputs) -->
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .api-trigger-node {
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
    color: white;
    border-radius: 8px;
    padding: 0;
    width: 140px;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
    transition: all 0.2s ease;
    border: 2px solid transparent;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .api-trigger-node.selected {
    border-color: #d97706;
    box-shadow: 0 6px 16px rgba(245, 158, 11, 0.5);
    transform: scale(1.02);
  }

  .api-trigger-node.error {
    border-color: #ef4444;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  }

  .delete-btn {
    position: absolute;
    top: -8px;
    right: -8px;
    background: white;
    border: 2px solid #f59e0b;
    color: #f59e0b;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 18px;
    font-weight: bold;
    opacity: 0;
    transition: opacity 0.2s ease;
    z-index: 10;
  }

  .api-trigger-node:hover .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    background: #ef4444;
    border-color: #ef4444;
    color: white;
  }

  .status-badge {
    position: absolute;
    top: 8px;
    left: 8px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid white;
    z-index: 5;
  }

  .status-badge.pending {
    color: #6b7280;
  }

  .status-badge.running {
    color: #3b82f6;
    animation: pulse 1s ease-in-out infinite;
  }

  .status-badge.completed {
    color: #10b981;
  }

  .status-badge.failed {
    color: #ef4444;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  .spinner {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .node-content {
    padding: 16px 12px 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
  }

  .node-icon {
    font-size: 32px;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
  }

  .node-label {
    font-size: 12px;
    font-weight: 600;
    padding: 0 12px 8px;
    text-align: center;
    line-height: 1.2;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  }

  .node-info {
    padding: 0 12px 8px;
    font-size: 10px;
    opacity: 0.9;
    text-align: center;
  }

  .field-count {
    background: rgba(255, 255, 255, 0.2);
    padding: 2px 6px;
    border-radius: 8px;
  }

  .no-fields {
    opacity: 0.7;
    font-style: italic;
  }

  .node-actions {
    width: 100%;
    padding: 0 8px 8px;
  }

  .configure-btn {
    width: 100%;
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: white;
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-weight: 500;
  }

  .configure-btn:hover {
    background: rgba(255, 255, 255, 0.3);
    border-color: rgba(255, 255, 255, 0.5);
  }

  /* Execution states */
  .api-trigger-node.pending {
    opacity: 0.7;
  }

  .api-trigger-node.running {
    animation: pulse-border 1.5s ease-in-out infinite;
  }

  .api-trigger-node.completed {
    border-color: #10b981;
  }

  .api-trigger-node.failed {
    border-color: #ef4444;
  }

  @keyframes pulse-border {
    0%,
    100% {
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    50% {
      box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
  }
</style>
