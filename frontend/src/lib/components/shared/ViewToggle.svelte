<script lang="ts">
  export let view: "card" | "list" = "card";
  export let onChange: (newView: "card" | "list") => void;

  function handleViewChange(newView: "card" | "list") {
    view = newView;
    onChange(newView);
  }
</script>

<div class="view-toggle">
  <button
    class="toggle-btn"
    class:active={view === "card"}
    on:click={() => handleViewChange("card")}
    aria-label="Card view"
    aria-pressed={view === "card"}
  >
    <span class="icon">⊞</span>
    <span class="label">Cards</span>
  </button>
  <button
    class="toggle-btn"
    class:active={view === "list"}
    on:click={() => handleViewChange("list")}
    aria-label="List view"
    aria-pressed={view === "list"}
  >
    <span class="icon">☰</span>
    <span class="label">List</span>
  </button>
</div>

<style>
  .view-toggle {
    display: flex;
    gap: var(--spacing-xs);
    background: var(--color-white);
    padding: var(--spacing-xs);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm) var(--spacing-md);
    border: none;
    background: transparent;
    color: var(--color-grey);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: 500;
    transition: all var(--transition-fast);
  }

  .toggle-btn:hover {
    background: var(--color-light-grey);
    color: var(--color-navy);
  }

  .toggle-btn.active {
    background: var(--color-navy);
    color: var(--color-white);
  }

  .icon {
    font-size: 1.2rem;
  }

  @media (max-width: 768px) {
    .label {
      display: none;
    }

    .toggle-btn {
      padding: var(--spacing-sm);
    }
  }
</style>
