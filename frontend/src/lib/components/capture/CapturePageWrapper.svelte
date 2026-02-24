<script lang="ts">
  /**
   * CapturePageWrapper - Shared layout wrapper for capture pages
   * 
   * Used by both standalone predictions capture and campaigns capture routes.
   * Provides consistent header, breadcrumbs, badges, and content layout.
   */
  export let title: string;
  export let breadcrumbs: Array<{ label: string; href?: string }> = [];
  export let subtitle: string = "";
  export let badges: Array<{ label: string; variant: 'success' | 'warning' | 'info' | 'error' }> = [];
  export let campaignId: number | undefined = undefined;
  export let playbookId: number | undefined = undefined;
</script>

<div class="capture-wrapper">
  <header class="capture-header">
    {#if breadcrumbs.length > 0}
      <nav class="breadcrumb">
        {#each breadcrumbs as crumb, index}
          {#if crumb.href}
            <a href={crumb.href} class="breadcrumb-link">{crumb.label}</a>
          {:else}
            <span class="breadcrumb-current">{crumb.label}</span>
          {/if}
          {#if index < breadcrumbs.length - 1}
            <span class="breadcrumb-separator">/</span>
          {/if}
        {/each}
      </nav>
    {/if}
    
    <div class="header-content">
      <h1 class="header-title">{title}</h1>
      
      {#if badges.length > 0}
        <div class="header-badges">
          {#each badges as badge}
            <span class="badge badge-{badge.variant}">{badge.label}</span>
          {/each}
        </div>
      {/if}
    </div>
    
    {#if subtitle}
      <p class="header-subtitle">{subtitle}</p>
    {/if}
  </header>
  
  <main class="capture-content">
    <slot {campaignId} {playbookId} />
  </main>
</div>

<style>
  .capture-wrapper {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 100vh;
    background-color: var(--color-bg-primary, #f5f7fa);
  }

  .capture-header {
    padding: 1.5rem 2rem;
    background-color: var(--color-white, #ffffff);
    border-bottom: 1px solid var(--color-border, #e1e4e8);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--color-text-secondary, #6c757d);
  }

  .breadcrumb-link {
    color: var(--color-accent, #E1604C);
    text-decoration: none;
    transition: opacity var(--transition-fast, 150ms);
  }

  .breadcrumb-link:hover {
    opacity: 0.8;
    text-decoration: underline;
  }

  .breadcrumb-current {
    color: var(--color-text-primary, #1D2F43);
    font-weight: 500;
  }

  .breadcrumb-separator {
    color: var(--color-text-tertiary, #adb5bd);
  }

  .header-content {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .header-title {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--color-navy, #1D2F43);
    font-family: 'Montserrat', sans-serif;
  }

  .header-badges {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .badge-success {
    background-color: #d4edda;
    color: #155724;
  }

  .badge-warning {
    background-color: #fff3cd;
    color: #856404;
  }

  .badge-info {
    background-color: #d1ecf1;
    color: #0c5460;
  }

  .badge-error {
    background-color: #f8d7da;
    color: #721c24;
  }

  .header-subtitle {
    margin: 0.5rem 0 0 0;
    font-size: 0.95rem;
    color: var(--color-text-secondary, #6c757d);
    line-height: 1.5;
  }

  .capture-content {
    flex: 1;
    padding: 1.5rem 2rem;
    overflow-y: auto;
  }

  @media (max-width: 768px) {
    .capture-header {
      padding: 1rem 1.25rem;
    }

    .header-title {
      font-size: 1.5rem;
    }

    .capture-content {
      padding: 1rem 1.25rem;
    }

    .breadcrumb {
      font-size: 0.8rem;
    }
  }
</style>
