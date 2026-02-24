<script lang="ts">
  import { Position, Handle } from "@xyflow/svelte";
  import type { NodeProps } from "@xyflow/svelte";

  type $$Props = NodeProps;

  let { data, selected = false }: $$Props = $props();

  // Check if this node has validation errors
  const hasError = $derived(data.hasError || false);
  const executionState = $derived(data.executionState);

  function handleDelete(e: MouseEvent) {
    e.stopPropagation();
    if (data.onDelete) {
      data.onDelete(data.id);
    }
  }
</script>

<div class="output-node" class:selected class:error={hasError} class:pending={executionState === 'pending'} class:running={executionState === 'running'} class:completed={executionState === 'completed'} class:failed={executionState === 'failed'} class:skipped={executionState === 'skipped'}>
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
      {#if executionState === 'running'}
        <span class="spinner">⟳</span>
      {:else if executionState === 'completed'}
        <span class="check">✓</span>
      {:else if executionState === 'failed'}
        <span class="cross">✗</span>
      {:else if executionState === 'pending'}
        <span class="dot">●</span>
      {/if}
    </div>
  {/if}

  <div class="node-content">
    <div class="node-icon">📤</div>
  </div>

  <div class="node-label">{data.label}</div>

  <!-- Input handle only (outputs are terminal nodes) -->
  <Handle type="target" position={Position.Left} />
</div>

<style>
  .output-node {
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

  .output-node:hover .delete-btn,
  .output-node.selected .delete-btn {
    opacity: 1;
  }

  .delete-btn:hover {
    background: #ef4444;
    color: white;
    transform: scale(1.1);
  }

  .output-node.selected {
    border-color: #10b981;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
  }

  .output-node:hover {
    border-color: #10b981;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .node-content {
    width: 100%;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
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

  .output-node.error {
    border: 2px solid #ef4444 !important;
    animation: pulse-error 1.5s ease-in-out infinite;
  }

  @keyframes pulse-error {
    0%,
    100% {
      box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.4), 0 0 20px rgba(239, 68, 68, 0.6);
    }
    50% {
      box-shadow: 0 0 0 6px rgba(239, 68, 68, 0.6), 0 0 20px rgba(239, 68, 68, 0.8);
    }
  }

  /* Execution States */
  .output-node.pending {
    border-color: #9ca3af;
    border-style: dashed;
  }

  .output-node.running {
    border-color: #3b82f6;
    animation: pulse-running 2s ease-in-out infinite;
    will-change: box-shadow;
  }

  .output-node.completed {
    border-color: #10b981;
    background: linear-gradient(135deg, rgba(240, 253, 244, 0.5) 0%, rgba(220, 252, 231, 0.5) 100%);
    animation: glow-success 1s ease-in-out;
  }

  .output-node.failed {
    border-color: #ef4444;
    background: linear-gradient(135deg, rgba(254, 242, 242, 0.5) 0%, rgba(254, 226, 226, 0.5) 100%);
  }

  .output-node.skipped {
    border-color: #d1d5db;
    opacity: 0.6;
  }

  @keyframes pulse-running {
    0%, 100% { box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.4), 0 0 12px rgba(59, 130, 246, 0.3); }
    50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.2), 0 0 16px rgba(59, 130, 246, 0.5); }
  }

  @keyframes glow-success {
    0% { box-shadow: 0 0 0 0px rgba(16, 185, 129, 0); }
    50% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0.4), 0 0 20px rgba(16, 185, 129, 0.6); }
    100% { box-shadow: 0 0 0 0px rgba(16, 185, 129, 0); }
  }

  .status-badge {
    position: absolute; top: -8px; right: -8px;
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: bold;
    border: 2px solid white; z-index: 20;
  }

  .status-badge.pending { background: #9ca3af; color: white; }
  .status-badge.running { background: #3b82f6; color: white; }
  .status-badge.completed { background: #10b981; color: white; }
  .status-badge.failed { background: #ef4444; color: white; }
  .status-badge.skipped { background: #d1d5db; color: #6b7280; }

  .status-badge .spinner { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .status-badge .check, .status-badge .cross, .status-badge .dot { line-height: 1; }
</style>
