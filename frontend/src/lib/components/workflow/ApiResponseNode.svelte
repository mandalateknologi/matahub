<script lang="ts">
  import { Position, Handle } from "@xyflow/svelte";
  import type { NodeProps } from "@xyflow/svelte";

  type $$Props = NodeProps;

  let { data, selected = false }: $$Props = $props();

  // Check if this node has validation errors
  const hasError = $derived(data.hasError || false);
  const executionState = $derived(data.executionState);

  // Get connected input count from data
  const connectedInputCount = $derived(data.connectedInputCount || 0);

  // Get response mode configuration
  const responseMode = $derived(data.config?.response_mode || "array");

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
  class="api-response-node"
  class:selected
  class:error={hasError}
  class:no-inputs={connectedInputCount === 0}
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
    <div class="node-icon">📡</div>
  </div>

  <div class="node-label">{data.label}</div>

  <div class="node-info">
    {#if connectedInputCount > 0}
      <span class="input-count"
        >{connectedInputCount} input{connectedInputCount !== 1 ? "s" : ""} connected</span
      >
    {:else}
      <span class="no-inputs-warning">⚠ No inputs connected</span>
    {/if}
  </div>

  <div class="node-mode">
    <span class="mode-badge"
      >{responseMode === "array"
        ? "Array"
        : responseMode === "merged"
          ? "Merged"
          : "Custom"}</span
    >
  </div>

  <div class="node-actions">
    <button
      class="configure-btn"
      on:click={handleConfigure}
      title="Configure response format"
    >
      ⚙ Configure
    </button>
  </div>

  <!-- Input handle only (API response doesn't output to other nodes) -->
  <Handle type="target" position={Position.Left} />
</div>

<style>
  .api-response-node {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border-radius: 8px;
    padding: 0;
    width: 140px;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    transition: all 0.2s ease;
    border: 2px solid transparent;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .api-response-node.selected {
    border-color: #047857;
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.5);
    transform: scale(1.02);
  }

  .api-response-node.error,
  .api-response-node.no-inputs {
    border-color: #ef4444;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  }

  .delete-btn {
    position: absolute;
    top: -8px;
    right: -8px;
    background: white;
    border: 2px solid #10b981;
    color: #10b981;
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

  .api-response-node:hover .delete-btn {
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
    padding: 0 12px 6px;
    font-size: 10px;
    opacity: 0.9;
    text-align: center;
  }

  .input-count {
    background: rgba(255, 255, 255, 0.2);
    padding: 2px 6px;
    border-radius: 8px;
  }

  .no-inputs-warning {
    background: rgba(239, 68, 68, 0.3);
    color: #fecaca;
    padding: 2px 6px;
    border-radius: 8px;
    font-weight: 500;
  }

  .node-mode {
    padding: 0 12px 8px;
    font-size: 9px;
    opacity: 0.8;
  }

  .mode-badge {
    background: rgba(255, 255, 255, 0.15);
    padding: 1px 4px;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: 500;
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
  .api-response-node.pending {
    opacity: 0.7;
  }

  .api-response-node.running {
    animation: pulse-border 1.5s ease-in-out infinite;
  }

  .api-response-node.completed {
    border-color: #10b981;
  }

  .api-response-node.failed {
    border-color: #ef4444;
  }

  @keyframes pulse-border {
    0%,
    100% {
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }
    50% {
      box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
    }
  }
</style>
