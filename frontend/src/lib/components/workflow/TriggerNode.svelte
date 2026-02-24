<script lang="ts">
  import { Position, Handle } from "@xyflow/svelte";
  import type { NodeProps } from "@xyflow/svelte";

  type $$Props = NodeProps;

  let { data, selected = false }: $$Props = $props();

  // Check if this node has validation errors
  const hasError = $derived(data.hasError || false);
  const executionState = $derived(data.executionState);

  // Check if this is a manual trigger
  const isManualTrigger = data.nodeType === "manual_trigger";

  function handleDelete(e: MouseEvent) {
    e.stopPropagation();
    if (data.onDelete) {
      data.onDelete(data.id);
    }
  }

  function handleExecute(e: MouseEvent) {
    e.stopPropagation();
    if (data.onExecute) {
      data.onExecute();
    }
  }
</script>

<div
  class="trigger-node"
  class:selected
  class:manual={isManualTrigger}
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
    <div class="node-icon">⚡</div>
  </div>

  <div class="node-label">{data.label}</div>

  {#if isManualTrigger}
    <div class="node-actions">
      <button
        class="execute-btn"
        on:click={handleExecute}
        title="Execute this workflow"
      >
        ▶ Execute Workflow
      </button>
    </div>
  {/if}

  <!-- Output handle only (triggers don't have inputs) -->
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .trigger-node {
    background: white;
    border-radius: 8px;
    padding: 0;
    width: 100px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: all 0.2s ease;
    border: 2px solid #e5e7eb;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .trigger-node.manual {
    width: 160px;
  }

  .delete-btn {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    color: #ef4444;
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: all 0.2s ease;
    z-index: 10;
  }

  .trigger-node:hover .delete-btn,
  .trigger-node.selected .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    background: #ef4444;
    color: white;
    transform: scale(1.1);
  }

  .trigger-node.selected {
    border-color: #f59e0b;
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
  }

  .trigger-node:hover {
    border-color: #f59e0b;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .trigger-node.error {
    border: 2px solid #ef4444 !important;
    animation: pulse-error 1.5s ease-in-out infinite;
  }

  @keyframes pulse-error {
    0%,
    100% {
      box-shadow:
        0 0 0 4px rgba(239, 68, 68, 0.4),
        0 0 20px rgba(239, 68, 68, 0.6);
    }
    50% {
      box-shadow:
        0 0 0 6px rgba(239, 68, 68, 0.6),
        0 0 20px rgba(239, 68, 68, 0.8);
    }
  }

  .node-content {
    width: 100%;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border-radius: 6px 6px 0 0;
  }

  .node-icon {
    font-size: 2rem;
  }

  .node-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #374151;
    padding: 0.5rem;
    text-align: center;
    width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .node-actions {
    width: 100%;
    padding: 0.5rem;
    border-top: 1px solid #e5e7eb;
    background: #fafafa;
    border-radius: 0 0 6px 6px;
  }

  .execute-btn {
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
  }

  .execute-btn:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
  }

  .execute-btn:active {
    transform: translateY(0);
    box-shadow: 0 1px 2px rgba(16, 185, 129, 0.2);
  }

  /* Execution States */
  .trigger-node.pending {
    border-color: #9ca3af;
    border-style: dashed;
  }

  .trigger-node.running {
    border-color: #3b82f6;
    animation: pulse-running 2s ease-in-out infinite;
    will-change: box-shadow;
  }

  .trigger-node.completed {
    border-color: #10b981;
    background: linear-gradient(
      135deg,
      rgba(240, 253, 244, 0.5) 0%,
      rgba(220, 252, 231, 0.5) 100%
    );
    animation: glow-success 1s ease-in-out;
  }

  .trigger-node.failed {
    border-color: #ef4444;
    background: linear-gradient(
      135deg,
      rgba(254, 242, 242, 0.5) 0%,
      rgba(254, 226, 226, 0.5) 100%
    );
  }

  .trigger-node.skipped {
    border-color: #d1d5db;
    opacity: 0.6;
  }

  @keyframes pulse-running {
    0%,
    100% {
      box-shadow:
        0 0 0 4px rgba(59, 130, 246, 0.4),
        0 0 12px rgba(59, 130, 246, 0.3);
    }
    50% {
      box-shadow:
        0 0 0 8px rgba(59, 130, 246, 0.2),
        0 0 16px rgba(59, 130, 246, 0.5);
    }
  }

  @keyframes glow-success {
    0% {
      box-shadow: 0 0 0 0px rgba(16, 185, 129, 0);
    }
    50% {
      box-shadow:
        0 0 0 8px rgba(16, 185, 129, 0.4),
        0 0 20px rgba(16, 185, 129, 0.6);
    }
    100% {
      box-shadow: 0 0 0 0px rgba(16, 185, 129, 0);
    }
  }

  .status-badge {
    position: absolute;
    top: -8px;
    right: -8px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: bold;
    border: 2px solid white;
    z-index: 20;
  }

  .status-badge.pending {
    background: #9ca3af;
    color: white;
  }

  .status-badge.running {
    background: #3b82f6;
    color: white;
  }

  .status-badge.completed {
    background: #10b981;
    color: white;
  }

  .status-badge.failed {
    background: #ef4444;
    color: white;
  }

  .status-badge.skipped {
    background: #d1d5db;
    color: #6b7280;
  }

  .status-badge .spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .status-badge .check,
  .status-badge .cross,
  .status-badge .dot {
    line-height: 1;
  }
</style>
