<script lang="ts">
  import { uiStore } from "../../stores/uiStore";
  import { themeStore } from "../../stores/themeStore";
  
  function toggleTheme() {
    console.log('Toggle theme clicked, current:', $themeStore);
    themeStore.toggle();
  }
</script>

<nav class="navbar">
  <div class="navbar-container">
    <div class="navbar-left">
      <button class="menu-btn" on:click={() => uiStore.toggleSidebar()}>
        ☰
      </button>
      <h1 class="logo">ATVISION</h1>
    </div>

    <div class="navbar-right">
      <button class="icon-btn" aria-label="Notifications" title="Notifications">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
      </button>
      <button class="icon-btn" on:click={toggleTheme} aria-label="Toggle theme" title="Toggle theme">
        {#if $themeStore === 'dark'}
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        {:else if $themeStore === 'light'}
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
          </svg>
        {:else}
          <!-- Auto mode icon -->
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        {/if}
      </button>
    </div>
  </div>
</nav>

<style>
  .navbar {
    background-color: var(--color-navy);
    color: var(--color-white);
    padding: var(--spacing-xs) var(--spacing-md);
    box-shadow: var(--shadow-md);
    position: sticky;
    top: 0;
    z-index: 100;
    transition: background-color var(--transition-base);
  }

  :global([data-theme="dark"]) .navbar {
    background-color: #1a1a1a;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  :global([data-theme="dark"]) .navbar .logo,
  :global([data-theme="dark"]) .navbar .menu-btn,
  :global([data-theme="dark"]) .navbar .icon-btn {
    color: #ffffff;
  }

  :global([data-theme="dark"]) .navbar .icon-btn svg {
    stroke: #ffffff;
  }

  .navbar-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 100%;
  }

  .navbar-left {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }

  .menu-btn {
    background: transparent;
    color: var(--color-white);
    font-size: var(--font-size-xl);
    padding: var(--spacing-xs);
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
  }

  .logo {
    font-size: var(--font-size-xl);
    font-weight: 700;
    letter-spacing: 0.05em;
    margin: 0;
    color: var(--color-white);
  }

  .navbar-right {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
  }

  .icon-btn {
    background: transparent;
    color: var(--color-white);
    border: none;
    padding: var(--spacing-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    border-radius: var(--border-radius-sm);
    transition: background-color var(--transition-fast);
  }

  .icon-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }

  .icon-btn svg {
    display: block;
  }
</style>
