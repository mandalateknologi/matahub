<script lang="ts">
  /**
   * Button Component - Reusable button with variants and loading state
   *
   * Usage:
   * <Button variant="primary" size="md" loading={false} disabled={false} onclick={handleClick}>
   *   Click Me
   * </Button>
   */

  type ButtonVariant = "primary" | "secondary" | "danger" | "outline" | "ghost";
  type ButtonSize = "sm" | "md" | "lg";

  let {
    variant = "primary",
    size = "md",
    loading = false,
    disabled = false,
    type = "button",
    class: customClass = "",
    onclick,
    children,
  }: {
    variant?: ButtonVariant;
    size?: ButtonSize;
    loading?: boolean;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
    class?: string;
    onclick?: (event: MouseEvent) => void;
    children?: any;
  } = $props();

  const isDisabled = $derived(disabled || loading);
</script>

<button
  {type}
  class="btn btn-{variant} btn-{size} {loading
    ? 'btn-loading'
    : ''} {customClass}"
  disabled={isDisabled}
  {onclick}
>
  {#if loading}
    <span class="spinner"></span>
  {/if}
  <span class="btn-content" class:loading>
    {@render children?.()}
  </span>
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    font-family: var(--font-primary);
    font-weight: 600;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-base);
    outline: none;
    position: relative;
    white-space: nowrap;
  }

  .btn:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .btn:not(:disabled):hover {
    transform: translateY(-1px);
  }

  .btn:not(:disabled):active {
    transform: translateY(0);
  }

  /* Variants */
  .btn-primary {
    background: var(--color-accent);
    color: var(--color-white);
  }

  .btn-primary:not(:disabled):hover {
    background: #d45540;
    box-shadow: var(--shadow-md);
  }

  .btn-secondary {
    background: var(--color-navy);
    color: var(--color-white);
  }

  .btn-secondary:not(:disabled):hover {
    background: var(--color-navy-dark);
    box-shadow: var(--shadow-md);
  }

  .btn-danger {
    background: var(--color-status-error);
    color: var(--color-white);
  }

  .btn-danger:not(:disabled):hover {
    background: #dc2626;
    box-shadow: var(--shadow-md);
  }

  .btn-outline {
    background: transparent;
    border: 2px solid var(--color-navy);
    color: var(--color-navy);
  }

  .btn-outline:not(:disabled):hover {
    background: var(--color-navy);
    color: var(--color-white);
  }

  .btn-ghost {
    background: transparent;
    color: var(--color-navy);
  }

  .btn-ghost:not(:disabled):hover {
    background: var(--color-bg-hover);
  }

  /* Sizes */
  .btn-sm {
    padding: var(--spacing-xs) var(--spacing-md);
    font-size: var(--font-size-sm);
  }

  .btn-md {
    padding: var(--spacing-sm) var(--spacing-lg);
    font-size: var(--font-size-base);
  }

  .btn-lg {
    padding: var(--spacing-md) var(--spacing-xl);
    font-size: var(--font-size-lg);
  }

  /* Loading state */
  .btn-loading {
    pointer-events: none;
  }

  .btn-content.loading {
    opacity: 0.7;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: var(--radius-circle);
    animation: anim-spin 0.6s linear infinite;
  }

  /* Dark mode adjustments */
  [data-theme="dark"] .btn-primary {
    background: var(--color-accent);
  }

  [data-theme="dark"] .btn-secondary {
    background: #3a5a7f;
  }

  [data-theme="dark"] .btn-outline {
    border-color: var(--color-border);
    color: var(--color-navy);
  }

  [data-theme="dark"] .btn-outline:not(:disabled):hover {
    background: var(--color-border);
    color: var(--color-white);
  }

  [data-theme="dark"] .btn-ghost:not(:disabled):hover {
    background: var(--color-bg-hover);
  }
</style>
