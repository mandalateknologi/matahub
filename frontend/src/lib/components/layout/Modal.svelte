<script lang="ts">
  import { uiStore } from "../../stores/uiStore";

  // Use Svelte's automatic subscription with $ prefix
  $: modal = $uiStore.modal;

  function getIconForType(type: string) {
    switch (type) {
      case "success":
        return "✓";
      case "error":
        return "✕";
      case "warning":
        return "⚠";
      case "info":
        return "ℹ";
      default:
        return "ℹ";
    }
  }

  function getColorForType(type: string) {
    switch (type) {
      case "success":
        return "var(--color-status-success)";
      case "error":
        return "var(--color-status-error)";
      case "warning":
        return "var(--color-status-warning)";
      case "info":
        return "var(--color-status-info)";
      default:
        return "var(--color-navy)";
    }
  }

  function handleClose() {
    if (modal?.onCancel) {
      modal.onCancel();
    }
    uiStore.closeModal();
  }

  function handleConfirm() {
    if (modal?.onConfirm) {
      modal.onConfirm();
    }
    uiStore.closeModal();
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && modal?.dismissible !== false) {
      handleClose();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && modal?.dismissible !== false) {
      handleClose();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if modal?.isOpen}
  <div class="modal-backdrop" on:click={handleBackdropClick}>
    <div
      class="modal-container"
      style="border-top-color: {getColorForType(modal.type)}"
    >
      <!-- Header -->
      <div class="modal-header">
        <div
          class="modal-icon"
          style="background-color: {getColorForType(
            modal.type
          )}20; color: {getColorForType(modal.type)}"
        >
          {getIconForType(modal.type)}
        </div>
        <h2 class="modal-title">{modal.title || "Alert"}</h2>
        {#if modal.dismissible !== false}
          <button
            class="modal-close"
            on:click={handleClose}
            aria-label="Close modal"
          >
            ×
          </button>
        {/if}
      </div>

      <!-- Content -->
      <div class="modal-alert-content">
        {#if typeof modal.message === "string"}
          <p class="modal-message">{modal.message}</p>
        {:else}
          {@html modal.message}
        {/if}
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        {#if modal.showCancel !== false}
          <button class="btn btn-secondary" on:click={handleClose}>
            {modal.cancelText || "Cancel"}
          </button>
        {/if}
        <button
          class="btn btn-primary"
          style="background-color: {getColorForType(modal.type)}"
          on:click={handleConfirm}
        >
          {modal.confirmText || "OK"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    animation: fadeIn var(--transition-base);
    padding: var(--spacing-lg);
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal-container {
    background: var(--color-white);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xl);
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    animation: slideUp var(--transition-base);
    border-top: 4px solid;
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
    gap: var(--spacing-md);
    padding: var(--spacing-lg);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-icon {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-2xl);
    font-weight: bold;
    flex-shrink: 0;
  }

  .modal-title {
    flex: 1;
    font-size: var(--font-size-xl);
    font-weight: 600;
    color: var(--color-navy);
    margin: 0;
  }

  .modal-close {
    background: transparent;
    color: var(--color-grey);
    font-size: 2rem;
    padding: 0;
    line-height: 1;
    opacity: 0.6;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    transition: all var(--transition-fast);
    flex-shrink: 0;
  }

  .modal-close:hover {
    opacity: 1;
    background: var(--color-light-grey);
  }

  .modal-alert-content {
    padding: var(--spacing-lg);
    overflow-y: auto;
    flex: 1;
  }

  .modal-message {
    color: var(--color-text-secondary);
    font-size: var(--font-size-base);
    line-height: 1.6;
    margin: 0;
  }

  .modal-footer {
    padding: var(--spacing-lg);
    border-top: 1px solid var(--color-border);
    display: flex;
    gap: var(--spacing-md);
    justify-content: flex-end;
  }

  .btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    border-radius: var(--radius-md);
    font-weight: 500;
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    border: none;
  }

  .btn-secondary {
    background: var(--color-light-grey);
    color: var(--color-navy);
  }

  .btn-secondary:hover {
    background: var(--color-border);
  }

  .btn-primary {
    color: var(--color-white);
  }

  .btn-primary:hover {
    opacity: 0.9;
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  /* Responsive */
  @media (max-width: 640px) {
    .modal-backdrop {
      padding: var(--spacing-md);
    }

    .modal-container {
      max-width: 100%;
    }

    .modal-header {
      padding: var(--spacing-md);
    }

    .modal-alert-content {
      padding: var(--spacing-md);
    }

    .modal-footer {
      padding: var(--spacing-md);
      flex-direction: column-reverse;
    }

    .btn {
      width: 100%;
    }
  }
</style>
