<script lang="ts">
  /**
   * Badge Component - Unified badge styling across the application
   *
   * Variants: success, warning, error, info, neutral, running, pending, completed, failed, session, accent, secondary
   * Sizes: sm (small), md (medium - default)
   */

  export let variant:
    | "success"
    | "warning"
    | "error"
    | "info"
    | "neutral"
    | "running"
    | "pending"
    | "completed"
    | "failed"
    | "session"
    | "campaign"
    | "accent"
    | "secondary" = "neutral";
  export let size: "sm" | "md" = "md";
  export let icon: string = ""; // Optional icon/emoji to display before text
  export let customClass: string = ""; // Additional custom classes

  $: badgeClass = `badge badge-${variant} badge-${size} ${customClass}`.trim();
</script>

{#if icon}
  <span class={badgeClass}>
    <span class="badge-icon">{icon}</span>
    <slot />
  </span>
{:else}
  <span class={badgeClass}>
    <slot />
  </span>
{/if}

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    border-radius: 12px;
    font-weight: 600;
    text-transform: uppercase;
    white-space: nowrap;
    transition: all var(--transition-fast);
  }

  /* Sizes */
  .badge-sm {
    padding: 2px 6px;
    font-size: 0.625rem;
  }

  .badge-md {
    padding: 4px 8px;
    font-size: var(--font-size-xs);
  }

  /* Status Variants */
  .badge-success {
    background: var(--color-status-success);
    color: var(--color-white);
  }

  .badge-warning {
    background: var(--color-status-warning);
    color: var(--color-white);
  }

  .badge-error,
  .badge-failed {
    background: var(--color-status-error);
    color: var(--color-white);
  }

  .badge-info {
    background: var(--color-status-info);
    color: var(--color-white);
  }

  .badge-neutral {
    background: var(--color-status-neutral);
    color: var(--color-white);
  }

  .badge-running {
    background: var(--color-status-running);
    color: var(--color-white);
  }

  .badge-pending {
    background: var(--color-status-pending);
    color: var(--color-white);
  }

  .badge-completed {
    background: var(--color-status-completed);
    color: var(--color-white);
  }

  .badge-accent {
    background: var(--color-accent);
    color: var(--color-white);
  }

  .badge-session {
    background: #9333ea;
    color: var(--color-white);
  }

  .badge-campaign {
    background: #9333ea;
    color: var(--color-white);
  }

  .badge-secondary {
    background: #6c757d;
    color: var(--color-white);
  }

  .badge-icon {
    display: inline-flex;
    align-items: center;
    font-style: normal;
  }
</style>
