<script lang="ts">
  export let show: boolean = false;
  export let projectName: string = "";
  export let modelsCount: number = 0;
  export let jobsCount: number = 0;
  export let onCancel: () => void;
  export let onConfirm: () => void;

  function handleOverlayClick() {
    onCancel();
  }

  function handleModalClick(event: MouseEvent) {
    event.stopPropagation();
  }
</script>

{#if show}
  <div
    class="modal-overlay"
    on:click={handleOverlayClick}
    on:keydown={(e) => e.key === "Escape" && onCancel()}
    role="button"
    tabindex="-1"
  >
    <div class="modal-content" on:click={handleModalClick} role="dialog">
      <div class="modal-header">
        <h3>⚠️ Confirm Deletion</h3>
        <button class="modal-close" on:click={onCancel} aria-label="Close">
          ✕
        </button>
      </div>

      <div class="modal-body">
        <p class="warning-text">
          Are you sure you want to delete the project <strong
            >"{projectName}"</strong
          >?
        </p>

        {#if modelsCount > 0 || jobsCount > 0}
          <div class="warning-box">
            <p class="warning-title">This action will permanently delete:</p>
            <ul>
              {#if modelsCount > 0}
                <li>
                  <strong>{modelsCount}</strong>
                  {modelsCount === 1 ? "model" : "models"}
                </li>
              {/if}
              {#if jobsCount > 0}
                <li>
                  <strong>{jobsCount}</strong> training
                  {jobsCount === 1 ? "job" : "jobs"}
                </li>
              {/if}
            </ul>
            <p class="warning-footer">
              All associated data and artifacts will be lost. This action cannot
              be undone.
            </p>
          </div>
        {/if}
      </div>

      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={onCancel}>Cancel</button>
        <button class="btn btn-danger" on:click={onConfirm}>
          Delete Permanently
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(8px);
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
    background: var(--color-bg-light1);
    border-radius: var(--border-radius-lg);
    box-shadow:
      0 25px 80px rgba(0, 0, 0, 0.6),
      0 0 0 3px rgba(225, 96, 76, 0.4);
    max-width: 500px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    animation: slideUp 0.3s ease-out;
    border: 3px solid rgba(225, 96, 76, 0.6);
  }

  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--spacing-lg);
    border-bottom: 3px solid rgba(225, 96, 76, 0.3);
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.08) 0%,
      rgba(225, 96, 76, 0.04) 100%
    );
  }

  .modal-header h3 {
    margin: 0;
    font-size: 1.75rem;
    color: var(--color-accent);
    font-weight: 700;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: var(--color-text-secondary);
    cursor: pointer;
    padding: 0.25rem;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--border-radius-sm);
    transition: all var(--transition-fast);
  }

  .modal-close:hover {
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
  }

  .modal-body {
    padding: var(--spacing-lg);
  }

  .warning-text {
    font-size: 1.15rem;
    margin-bottom: var(--spacing-md);
    color: var(--color-text-primary);
    font-weight: 500;
  }

  .warning-box {
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.15) 0%,
      rgba(225, 96, 76, 0.08) 100%
    );
    border: 3px solid var(--color-accent);
    border-radius: var(--border-radius-md);
    padding: var(--spacing-md);
    margin-top: var(--spacing-md);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.2);
  }

  .warning-title {
    font-weight: 700;
    margin-bottom: var(--spacing-sm);
    color: var(--color-accent);
    font-size: 1.05rem;
  }

  .warning-box ul {
    margin: var(--spacing-sm) 0;
    padding-left: var(--spacing-lg);
  }

  .warning-box li {
    margin: var(--spacing-xs) 0;
    color: var(--color-text-primary);
  }

  .warning-footer {
    margin-top: var(--spacing-sm);
    font-size: 0.9rem;
    color: var(--color-text-secondary);
  }

  .modal-actions {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-lg);
    border-top: 2px solid var(--color-border);
    justify-content: flex-end;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: var(--border-radius-md);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    border: none;
    font-size: 1rem;
  }

  .btn-secondary {
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    border: 2px solid var(--color-border);
  }

  .btn-secondary:hover {
    background: var(--color-bg-tertiary);
    border-color: var(--color-navy);
  }

  .btn-danger {
    background: var(--color-accent);
    color: white;
    font-size: 1.05rem;
    font-weight: 700;
    padding: 0.85rem 2rem;
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.4);
    position: relative;
    overflow: hidden;
  }

  .btn-danger::before {
    content: "";
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.2),
      transparent
    );
    transition: left 0.5s;
  }

  .btn-danger:hover::before {
    left: 100%;
  }

  .btn-danger:hover {
    background: #d14a37;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(225, 96, 76, 0.5);
  }

  .btn-danger:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(225, 96, 76, 0.4);
  }
</style>
