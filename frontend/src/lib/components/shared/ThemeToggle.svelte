<script lang="ts">
  /**
   * ThemeToggle Component - Toggle between light/dark/auto themes
   *
   * Usage:
   * <ThemeToggle />
   */

  import { themeStore, type ThemeMode } from "$lib/stores/themeStore";

  let currentTheme = $state<ThemeMode>("auto");

  // Subscribe to theme store
  themeStore.subscribe((value) => {
    currentTheme = value;
  });

  function handleThemeChange(mode: ThemeMode) {
    themeStore.setTheme(mode);
  }

  // Icons (inline SVG for simplicity)
  const sunIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;

  const moonIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;

  const autoIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>`;
</script>

<div class="theme-toggle">
  <button
    class="toggle-btn"
    class:active={currentTheme === "light"}
    onclick={() => handleThemeChange("light")}
    title="Light mode"
    aria-label="Switch to light mode"
  >
    {@html sunIcon}
  </button>

  <button
    class="toggle-btn"
    class:active={currentTheme === "auto"}
    onclick={() => handleThemeChange("auto")}
    title="Auto (system) mode"
    aria-label="Switch to auto mode"
  >
    {@html autoIcon}
  </button>

  <button
    class="toggle-btn"
    class:active={currentTheme === "dark"}
    onclick={() => handleThemeChange("dark")}
    title="Dark mode"
    aria-label="Switch to dark mode"
  >
    {@html moonIcon}
  </button>
</div>

<style>
  .theme-toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-xs);
    background: var(--color-bg-card);
    padding: var(--spacing-xs);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--color-border-light);
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-sm);
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    outline: none;
  }

  .toggle-btn:hover {
    background: var(--color-bg-hover);
    color: var(--color-navy);
    transform: scale(1.05);
  }

  .toggle-btn:active {
    transform: scale(0.95);
  }

  .toggle-btn.active {
    background: var(--color-accent);
    color: var(--color-white);
    box-shadow: var(--shadow-sm);
  }

  .toggle-btn.active:hover {
    background: #d45540;
  }

  /* Dark mode adjustments */
  [data-theme="dark"] .theme-toggle {
    background: var(--color-bg-card);
    border-color: var(--color-border);
  }

  [data-theme="dark"] .toggle-btn {
    color: var(--color-text-secondary);
  }

  [data-theme="dark"] .toggle-btn:hover {
    background: var(--color-bg-hover);
    color: var(--color-navy);
  }

  [data-theme="dark"] .toggle-btn.active {
    background: var(--color-accent);
    color: var(--color-white);
  }

  /* Accessibility */
  .toggle-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
