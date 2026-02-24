<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let visible: boolean = false;
  export let title: string = "Confirm Action";
  export let message: string = "Are you sure?";
  export let confirmText: string = "Confirm";
  export let cancelText: string = "Cancel";
  export let isDanger: boolean = false;

  const dispatch = createEventDispatcher();

  function handleConfirm() {
    dispatch("confirm");
    visible = false;
  }

  function handleCancel() {
    dispatch("cancel");
    visible = false;
  }

  function handleBackdropClick() {
    handleCancel();
  }
</script>

{#if visible}
  <div class="modal-overlay" on:click={handleBackdropClick}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h3>{title}</h3>
      </div>
      <div class="modal-body">
        <p>{message}</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" on:click={handleCancel}>
          {cancelText}
        </button>
        <button
          class="btn"
          class:btn-danger={isDanger}
          class:btn-primary={!isDanger}
          on:click={handleConfirm}
        >
          {confirmText}
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
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
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
    max-width: 480px;
    width: 90%;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease-out;
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
    padding: var(--spacing-lg);
    border-bottom: 1px solid #e5e7eb;
  }

  .modal-header h3 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-navy);
  }

  .modal-body {
    padding: var(--spacing-lg);
  }

  .modal-body p {
    margin: 0;
    color: var(--color-text);
    line-height: 1.6;
  }

  .modal-footer {
    padding: var(--spacing-lg);
    border-top: 1px solid #e5e7eb;
    display: flex;
    gap: var(--spacing-sm);
    justify-content: flex-end;
  }

  .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .btn-secondary {
    background: #f3f4f6;
    color: #374151;
  }

  .btn-secondary:hover {
    background: #e5e7eb;
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
  }

  .btn-primary:hover {
    background: #d14738;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.3);
  }

  .btn-danger {
    background: #dc2626;
    color: white;
  }

  .btn-danger:hover {
    background: #b91c1c;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
  }
</style>
