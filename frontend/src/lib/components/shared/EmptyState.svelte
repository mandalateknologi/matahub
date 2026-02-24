<script lang="ts">
  export let icon: string = "📭";
  export let title: string = "No items found";
  export let message: string = "";
  export let actionLabel: string = "";
  export let onAction: (() => void) | null = null;
</script>

<div class="empty-state">
  <div class="empty-icon">{icon}</div>
  <h3 class="empty-title">{title}</h3>
  {#if message}
    <p class="empty-message">{message}</p>
  {/if}
  {#if actionLabel && onAction}
    <button class="btn-primary" on:click={onAction}>
      {actionLabel}
    </button>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xl) var(--spacing-lg);
    text-align: center;
    min-height: 350px;
    background: var(--color-white);
    border-radius: 12px;
    box-shadow: var(--shadow-sm);
    margin: var(--spacing-lg) 0;
  }

  @media (min-width: 768px) {
    .empty-state {
      padding: var(--spacing-xxl);
      min-height: 400px;
    }
  }

  .empty-icon {
    font-size: 3.5rem;
    margin-bottom: var(--spacing-lg);
    opacity: 0.7;
    animation: float 3s ease-in-out infinite;
  }

  @keyframes float {
    0%,
    100% {
      transform: translateY(0px);
    }
    50% {
      transform: translateY(-10px);
    }
  }

  @media (min-width: 768px) {
    .empty-icon {
      font-size: 4.5rem;
    }
  }

  .empty-title {
    font-size: var(--font-size-lg);
    font-weight: 700;
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
    line-height: 1.3;
  }

  @media (min-width: 768px) {
    .empty-title {
      font-size: var(--font-size-2xl);
    }
  }

  .empty-message {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-xl);
    max-width: 450px;
    line-height: 1.6;
  }

  @media (min-width: 768px) {
    .empty-message {
      font-size: var(--font-size-base);
      max-width: 500px;
    }
  }

  .btn-primary {
    background: linear-gradient(135deg, var(--color-accent) 0%, #c74d3a 100%);
    color: var(--color-white);
    border: none;
    padding: var(--spacing-sm) var(--spacing-lg);
    border-radius: 8px;
    font-size: var(--font-size-sm);
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-base);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.2);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  @media (min-width: 768px) {
    .btn-primary {
      padding: var(--spacing-md) var(--spacing-xl);
      font-size: var(--font-size-base);
    }
  }

  .btn-primary:hover {
    background: linear-gradient(135deg, #c74d3a 0%, var(--color-accent) 100%);
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(225, 96, 76, 0.3);
  }

  .btn-primary:active {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.2);
  }

  .btn-primary:focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.2);
  }
</style>
