<script lang="ts">
  import { uiStore } from '../../stores/uiStore';

  let toasts: any[] = [];

  uiStore.subscribe(state => {
    toasts = state.toasts;
  });

  function getToastColor(type: string) {
    switch (type) {
      case 'success': return 'var(--color-success)';
      case 'error': return 'var(--color-error)';
      case 'warning': return 'var(--color-warning)';
      default: return 'var(--color-navy)';
    }
  }
</script>

<div class="toast-container">
  {#each toasts as toast (toast.id)}
    <div 
      class="toast" 
      style="border-left-color: {getToastColor(toast.type)}"
      on:click={() => uiStore.removeToast(toast.id)}
    >
      <span class="toast-message">{toast.message}</span>
      <button class="toast-close">×</button>
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    top: 80px;
    right: var(--spacing-lg);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
    max-width: 400px;
  }

  .toast {
    background: var(--color-white);
    border-radius: var(--radius-md);
    padding: var(--spacing-md) var(--spacing-lg);
    box-shadow: var(--shadow-lg);
    border-left: 4px solid;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing-md);
    animation: slideIn var(--transition-base);
    cursor: pointer;
  }

  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }

  .toast-message {
    flex: 1;
    font-size: var(--font-size-sm);
  }

  .toast-close {
    background: transparent;
    color: var(--color-grey);
    font-size: var(--font-size-2xl);
    padding: 0;
    line-height: 1;
    opacity: 0.6;
  }

  .toast-close:hover {
    opacity: 1;
  }
</style>
