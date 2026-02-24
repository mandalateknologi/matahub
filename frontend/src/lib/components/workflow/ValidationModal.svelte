<script lang="ts">
  import type { Node } from "@xyflow/svelte";

  interface ValidationError {
    severity: "critical" | "warning";
    type: string;
    message: string;
    nodeIds: string[];
  }

  interface Props {
    errors: ValidationError[];
    nodes: Node[];
    onClose: () => void;
    onNodeClick?: (nodeId: string) => void;
    onExecuteAnyway?: () => void;
  }

  let { errors, nodes, onClose, onNodeClick, onExecuteAnyway }: Props = $props();

  // Separate errors by severity
  let criticalErrors = $derived(errors.filter((e) => e.severity === "critical"));
  let warnings = $derived(errors.filter((e) => e.severity === "warning"));
  let hasCriticalErrors = $derived(criticalErrors.length > 0);
  let hasOnlyWarnings = $derived(warnings.length > 0 && criticalErrors.length === 0);

  function getNodeLabel(nodeId: string): string {
    const node = nodes.find((n) => n.id === nodeId);
    return node?.data?.label || nodeId;
  }

  function handleNodeClick(nodeId: string) {
    if (onNodeClick) {
      onNodeClick(nodeId);
    }
  }

  function handleClose() {
    onClose();
  }

  function handleExecuteAnyway() {
    if (onExecuteAnyway && hasOnlyWarnings) {
      onExecuteAnyway();
    }
  }
</script>

<div class="modal-overlay" on:click={handleClose} role="button" tabindex="0">
  <div class="modal-content" on:click|stopPropagation>
    <div class="modal-header">
      <h2>⚠️ Workflow Validation</h2>
      <button class="close-btn" on:click={handleClose} title="Close">×</button>
    </div>

    <div class="modal-body">
      {#if hasCriticalErrors}
        <div class="error-section critical">
          <div class="section-header">
            <span class="severity-badge critical">🔴 Critical Errors</span>
            <span class="error-count">{criticalErrors.length}</span>
          </div>
          <div class="error-list">
            {#each criticalErrors as error}
              <div class="error-item critical">
                <div class="error-message">
                  <span class="error-icon">❌</span>
                  <span class="error-text">{error.message}</span>
                </div>
                {#if error.nodeIds.length > 0}
                  <div class="node-chips">
                    {#each error.nodeIds as nodeId}
                      <button
                        class="node-chip critical"
                        on:click={() => handleNodeClick(nodeId)}
                        title="Click to highlight node"
                      >
                        {getNodeLabel(nodeId)}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if warnings.length > 0}
        <div class="error-section warning">
          <div class="section-header">
            <span class="severity-badge warning">⚠️ Warnings</span>
            <span class="error-count">{warnings.length}</span>
          </div>
          <div class="error-list">
            {#each warnings as warning}
              <div class="error-item warning">
                <div class="error-message">
                  <span class="error-icon">⚠️</span>
                  <span class="error-text">{warning.message}</span>
                </div>
                {#if warning.nodeIds.length > 0}
                  <div class="node-chips">
                    {#each warning.nodeIds as nodeId}
                      <button
                        class="node-chip warning"
                        on:click={() => handleNodeClick(nodeId)}
                        title="Click to highlight node"
                      >
                        {getNodeLabel(nodeId)}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if hasCriticalErrors}
        <div class="help-text critical">
          <p>
            <strong>Cannot execute workflow:</strong> Please fix the critical errors
            above before running this workflow.
          </p>
        </div>
      {:else if hasOnlyWarnings}
        <div class="help-text warning">
          <p>
            <strong>Warnings detected:</strong> These issues won't prevent execution,
            but may cause unexpected behavior. You can execute anyway or fix them first.
          </p>
        </div>
      {/if}
    </div>

    <div class="modal-footer">
      <button class="btn btn-secondary" on:click={handleClose}>
        {hasCriticalErrors ? "Close" : "Cancel"}
      </button>
      {#if hasOnlyWarnings && onExecuteAnyway}
        <button class="btn btn-warning" on:click={handleExecuteAnyway}>
          Execute Anyway
        </button>
      {/if}
      {#if !hasCriticalErrors && !hasOnlyWarnings}
        <button class="btn btn-primary" on:click={handleClose}>Got It</button>
      {:else if hasCriticalErrors}
        <button class="btn btn-primary" on:click={handleClose}>Got It</button>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    backdrop-filter: blur(4px);
    animation: fadeIn 0.2s ease-out;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal-content {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 2px solid #e5e7eb;
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--color-navy);
    font-weight: 700;
  }

  .close-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #f3f4f6;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: #6b7280;
    transition: all 0.2s ease;
  }

  .close-btn:hover {
    background: #ef4444;
    color: white;
    transform: scale(1.1);
  }

  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }

  .error-section {
    margin-bottom: 1.5rem;
  }

  .error-section:last-child {
    margin-bottom: 0;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .severity-badge {
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .severity-badge.critical {
    background: #fee2e2;
    color: #991b1b;
    border: 2px solid #ef4444;
  }

  .severity-badge.warning {
    background: #fef3c7;
    color: #92400e;
    border: 2px solid #f59e0b;
  }

  .error-count {
    font-size: 0.875rem;
    font-weight: 600;
    color: #6b7280;
    background: #f3f4f6;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
  }

  .error-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .error-item {
    padding: 1rem;
    border-radius: 8px;
    border: 2px solid;
    background: white;
  }

  .error-item.critical {
    border-color: #ef4444;
    background: #fef2f2;
  }

  .error-item.warning {
    border-color: #f59e0b;
    background: #fffbeb;
  }

  .error-message {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .error-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .error-text {
    flex: 1;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: #1f2937;
    font-weight: 500;
  }

  .node-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .node-chip {
    padding: 0.375rem 0.75rem;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 600;
    border: 1px solid;
    cursor: pointer;
    transition: all 0.2s ease;
    background: white;
  }

  .node-chip.critical {
    border-color: #ef4444;
    color: #dc2626;
  }

  .node-chip.critical:hover {
    background: #ef4444;
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
  }

  .node-chip.warning {
    border-color: #f59e0b;
    color: #d97706;
  }

  .node-chip.warning:hover {
    background: #f59e0b;
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(245, 158, 11, 0.3);
  }

  .help-text {
    margin-top: 1.5rem;
    padding: 1rem;
    border-radius: 8px;
    border: 2px solid;
  }

  .help-text.critical {
    background: #fef2f2;
    border-color: #fca5a5;
  }

  .help-text.warning {
    background: #fffbeb;
    border-color: #fcd34d;
  }

  .help-text p {
    margin: 0;
    font-size: 0.9375rem;
    line-height: 1.5;
    color: #374151;
  }

  .help-text strong {
    font-weight: 700;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 2px solid #e5e7eb;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.9375rem;
    cursor: pointer;
    transition: all 0.2s ease;
    border: none;
  }

  .btn-secondary {
    background: #e5e7eb;
    color: #374151;
  }

  .btn-secondary:hover {
    background: #d1d5db;
  }

  .btn-primary {
    background: var(--color-primary);
    color: white;
  }

  .btn-primary:hover {
    background: var(--color-primary-dark);
    transform: translateY(-1px);
  }

  .btn-warning {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white;
  }

  .btn-warning:hover {
    background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
    transform: translateY(-1px);
  }
</style>
