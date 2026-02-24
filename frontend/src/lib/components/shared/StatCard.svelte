<script lang="ts">
  export let icon: string;
  export let value: number | string;
  export let label: string;
  export let breakdown: string = "";
  export let filterType: string = "";
  export let isActive: boolean = false;
  export let isClickable: boolean = false;
  export let animate: boolean = false;
  export let ariaLabel: string = "";

  function handleClick() {
    if (isClickable) {
      dispatch("click", filterType);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (isClickable && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      handleClick();
    }
  }

  import { createEventDispatcher } from "svelte";
  const dispatch = createEventDispatcher();
</script>

{#if isClickable}
  <button
    class="stat-card clickable"
    class:animate
    class:active={isActive}
    on:click={handleClick}
    on:keydown={handleKeydown}
    tabindex="0"
    aria-pressed={isActive}
    aria-label={ariaLabel || `Filter by ${label}`}
    title={ariaLabel || `Click to filter by ${label}`}
  >
    <div class="stat-icon">{icon}</div>
    <div class="stat-content">
      <div class="stat-value">{value}</div>
      <div class="stat-label">{label}</div>
      {#if breakdown}
        <div class="stat-breakdown">{breakdown}</div>
      {/if}
    </div>
  </button>
{:else}
  <div class="stat-card" class:animate role="status" aria-live="polite">
    <div class="stat-icon">{icon}</div>
    <div class="stat-content">
      <div class="stat-value">{value}</div>
      <div class="stat-label">{label}</div>
      {#if breakdown}
        <div class="stat-breakdown">{breakdown}</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .stat-card {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    transition:
      transform var(--transition-fast),
      box-shadow var(--transition-fast),
      border-color var(--transition-fast),
      background-color var(--transition-fast);
    opacity: 0;
    border: 3px solid transparent;
    text-align: left;
    width: 100%;
  }

  .stat-card.animate {
    animation: fadeInCard 0.6s ease-out forwards;
  }

  .stat-card.clickable {
    cursor: pointer;
  }

  .stat-card.clickable:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  .stat-card.clickable:active {
    transform: translateY(0);
  }

  .stat-card.active {
    border-color: var(--color-accent);
    background-color: rgba(225, 96, 76, 0.05);
  }

  .stat-icon {
    font-size: 2.5rem;
    flex-shrink: 0;
  }

  .stat-content {
    flex: 1;
  }

  .stat-value {
    font-size: var(--font-size-xxl);
    font-weight: 700;
    color: var(--color-navy);
    line-height: 1;
    margin-bottom: var(--spacing-xs);
  }

  .stat-card.animate .stat-value {
    animation: countUp 0.4s ease-out forwards;
    animation-delay: inherit;
  }

  .stat-label {
    font-size: var(--font-size-sm);
    color: var(--color-grey);
    font-weight: 500;
    margin-bottom: var(--spacing-xs);
  }

  .stat-breakdown {
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
  }

  @keyframes fadeInCard {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes countUp {
    from {
      opacity: 0;
      transform: scale(0.8);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }
</style>
