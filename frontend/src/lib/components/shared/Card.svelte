<script lang="ts">
  /**
   * Card Component - Reusable card container with variants
   *
   * Usage:
   * <Card variant="elevated" interactive={true} padding="lg">
   *   <slot />
   * </Card>
   */

  type CardVariant = "flat" | "elevated" | "outlined" | "interactive";
  type CardPadding = "none" | "sm" | "md" | "lg" | "xl";

  let {
    variant = "elevated",
    padding = "lg",
    interactive = false,
    class: customClass = "",
    children,
  }: {
    variant?: CardVariant;
    padding?: CardPadding;
    interactive?: boolean;
    class?: string;
    children?: any;
  } = $props();

  const paddingMap: Record<CardPadding, string> = {
    none: "",
    sm: "var(--spacing-sm)",
    md: "var(--spacing-md)",
    lg: "var(--spacing-lg)",
    xl: "var(--spacing-xl)",
  };
</script>

<div
  class="card card-{variant} {interactive
    ? 'card-interactive'
    : ''} {customClass}"
  style="padding: {paddingMap[padding]}"
>
  {@render children?.()}
</div>

<style>
  .card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    transition: all var(--transition-base);
  }

  /* Flat variant - minimal shadow */
  .card-flat {
    box-shadow: none;
    border: 1px solid var(--color-border-light);
  }

  /* Elevated variant - default with shadow */
  .card-elevated {
    box-shadow: var(--shadow-md);
  }

  .card-elevated:hover {
    box-shadow: var(--shadow-lg);
  }

  /* Outlined variant - border only */
  .card-outlined {
    box-shadow: none;
    border: 2px solid var(--color-border);
  }

  /* Interactive variant - hover effects and cursor */
  .card-interactive {
    cursor: pointer;
    transform-origin: center;
  }

  .card-interactive:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  .card-interactive:active {
    transform: translateY(0);
    box-shadow: var(--shadow-md);
  }

  /* Dark mode adjustments */
  [data-theme="dark"] .card {
    background: var(--color-bg-card);
  }

  [data-theme="dark"] .card-flat {
    border-color: var(--color-border);
  }

  [data-theme="dark"] .card-outlined {
    border-color: var(--color-border);
  }
</style>
